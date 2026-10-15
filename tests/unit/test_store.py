"""M7 Storage tests (modules/m07-storage/test_cases.md)."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from actiontrack import store as store_module
from actiontrack.errors import NotFoundError, StoreError
from actiontrack.models import Item
from actiontrack.store import Store, item_from_dict, item_to_dict

MEETING = date(2026, 10, 6)


class Clock:
    """Deterministic ``now``: each call is one minute later."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 15, 9, 0, 0)

    def __call__(self) -> datetime:
        self.current += timedelta(minutes=1)
        return self.current


def make_item(task: str = "send the revised quote", **changes) -> Item:
    fields = dict(
        owner="Priya Shah",
        task=task,
        raw_text=f"Priya to {task} by Friday",
        status="open",
        meeting_date=MEETING,
        last_seen_meeting_date=MEETING,
        due_date=date(2026, 10, 9),
        due_phrase="by Friday",
        source_files=["2026-10-06-sales.md"],
        meeting_title="Weekly Sales Sync",
    )
    fields.update(changes)
    return Item(**fields)


@pytest.fixture
def path(tmp_path) -> Path:
    return tmp_path / "actiontrack.json"


@pytest.fixture
def store(path) -> Store:
    return Store(path, now=Clock())


# ---------------------------------------------------------------- CRUD


def test_add_assigns_id_and_timestamps(store):  # TC-STO-001
    item = store.add(make_item())
    assert item.id == 1
    assert item.created_at == item.updated_at is not None


def test_ids_increase(store):  # TC-STO-002
    assert [store.add(make_item(f"task {i}")).id for i in range(3)] == [1, 2, 3]


def test_get_by_id(store):  # TC-STO-003
    store.add(make_item("a"))
    store.add(make_item("b"))
    assert store.get(2).task == "b"


def test_get_missing_id_returns_none(store):  # TC-STO-004
    assert store.get(99) is None


def test_update_refreshes_updated_at_only(store):  # TC-STO-005
    item = store.add(make_item())
    created = item.created_at
    item.status = "done"
    store.update(item)
    assert item.updated_at > created
    assert item.created_at == created


def test_update_unknown_item(store):  # TC-STO-006
    with pytest.raises(NotFoundError):
        store.update(make_item(id=42))


def test_load_all_in_id_order(store):  # TC-STO-007
    for task in ("c", "a", "b"):
        store.add(make_item(task))
    assert [i.id for i in store.load_all()] == [1, 2, 3]


def test_caller_cannot_choose_id(store):  # TC-STO-008
    assert store.add(make_item(id=50)).id == 1


# ---------------------------------------------------------------- persistence


def test_survives_restart(store, path):  # TC-STO-020
    store.add(make_item("a"))
    store.add(make_item("b"))
    store.save()
    reloaded = Store(path)
    assert [(i.id, i.task) for i in reloaded.load_all()] == [(1, "a"), (2, "b")]


def test_round_trip_every_field(store, path):  # TC-STO-021..023, TC-STO-027, TC-STO-028
    original = store.add(
        make_item(
            'review "José Núñez" contract \\ 🚀',
            owner="ambiguous",
            owner_candidates=["Priya Shah", "Priya Kumar"],
            source_files=["a.md", "b.md"],
            due_date=None,
            due_phrase="soon",
            not_in_attendees=True,
            last_seen_meeting_date=date(2026, 10, 13),
        )
    )
    other = store.add(make_item(owner_candidates=[], meeting_title=None))
    store.save()
    reloaded = Store(path)
    assert reloaded.get(1) == original
    assert reloaded.get(2) == other
    assert reloaded.get(1).due_date is None


def test_ids_never_reused(store, path):  # TC-STO-024
    for task in ("a", "b", "c"):
        store.add(make_item(task))
    store.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["items"] = data["items"][:2]  # item 3 removed by hand
    path.write_text(json.dumps(data), encoding="utf-8")
    assert Store(path).add(make_item("d")).id == 4


def test_next_id_repaired_if_too_low(store, path):
    store.add(make_item("a"))
    store.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["next_id"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    assert Store(path).add(make_item("b")).id == 2


# ---------------------------------------------------------------- format


def test_file_format(store, path):  # TC-STO-040..045
    store.add(make_item())
    store.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["next_id"] == 2
    item = data["items"][0]
    assert list(item) == [
        "id",
        "owner",
        "owner_candidates",
        "task",
        "raw_text",
        "due_date",
        "due_phrase",
        "status",
        "source_files",
        "meeting_date",
        "meeting_title",
        "last_seen_meeting_date",
        "not_in_attendees",
        "created_at",
        "updated_at",
    ]
    assert item["due_date"] == "2026-10-09"
    assert item["created_at"] == "2026-10-15T09:01:00"
    assert item["status"] in ("open", "done")


def test_unicode_is_stored_readably(store, path):  # TC-STO-027
    store.add(make_item(owner="José Núñez"))
    store.save()
    assert "José Núñez" in path.read_text(encoding="utf-8")


def test_saving_twice_is_byte_identical(store, path):
    store.add(make_item())
    store.save()
    first = path.read_bytes()
    Store(path).save()
    assert path.read_bytes() == first


# ---------------------------------------------------------------- file problems


def test_missing_file_is_empty_store(path):  # TC-STO-060
    store = Store(path)
    assert store.load_all() == []
    store.save()
    assert path.exists()


def test_zero_byte_file_is_empty_store_with_warning(path):  # TC-STO-061 (QA-32)
    path.write_text("", encoding="utf-8")
    store = Store(path)
    assert store.load_all() == []
    assert "empty" in store.warnings[0]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('{"items": [', "corrupt (line 1"),  # TC-STO-062
        ('["not", "an", "object"]', "'items' list"),  # TC-STO-063
        ('{"items": "nope"}', "'items' list"),
        ('{"version": 99, "items": []}', "unsupported version"),
        ('{"items": [{"id": 1}]}', "item #1"),
        ('{"next_id": "x", "items": []}', "next_id"),
    ],
)
def test_bad_store_raises_and_is_not_overwritten(path, content, message):
    path.write_text(content, encoding="utf-8")
    store = Store(path)
    with pytest.raises(StoreError, match=re.escape(message)):
        store.load_all()
    with pytest.raises(StoreError):
        store.save()
    assert path.read_text(encoding="utf-8") == content


def test_duplicate_ids_rejected(store, path):  # TC-STO-070
    store.add(make_item("a"))
    store.add(make_item("b"))
    store.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["items"][1]["id"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StoreError, match="more than once"):
        Store(path).load_all()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "overdue", "status 'overdue'"),
        ("id", 0, "id 0"),
        ("id", True, "'id' must be int"),
        ("due_date", "09/10/2026", "YYYY-MM-DD"),
        ("source_files", "a.md", "list of text"),
        ("created_at", "yesterday", "ISO timestamp"),
    ],
)
def test_bad_item_fields(field, value, message):
    data = item_to_dict(make_item(id=1))
    data[field] = value
    with pytest.raises(ValueError, match=message):
        item_from_dict(data)


def test_manually_edited_store_loads(store, path):  # TC-STO-069
    store.add(make_item())
    store.save()
    text = path.read_text(encoding="utf-8").replace("send the revised quote", "send the new quote")
    path.write_text(text, encoding="utf-8")
    assert Store(path).get(1).task == "send the new quote"


def test_store_folder_is_created(tmp_path):  # TC-STO-065
    store = Store(tmp_path / "new" / "dir" / "at.json")
    store.add(make_item())
    store.save()
    assert (tmp_path / "new" / "dir" / "at.json").exists()


def test_previous_version_kept_as_backup(store, path):
    store.add(make_item("a"))
    store.save()
    first = path.read_bytes()
    store.add(make_item("b"))
    store.save()
    assert path.with_name("actiontrack.json.bak").read_bytes() == first


# ---------------------------------------------------------------- atomic writes


@pytest.mark.parametrize("failing", ["replace", "dump"])
def test_crash_during_save_keeps_old_store(store, path, monkeypatch, failing):  # TC-STO-066/067
    store.add(make_item("a"))
    store.save()
    before = path.read_bytes()
    store.add(make_item("b"))

    def boom(*args, **kwargs):
        raise OSError(28, "No space left on device")  # also TC-STO-068

    if failing == "replace":
        monkeypatch.setattr(os, "replace", boom)
    else:
        monkeypatch.setattr(store_module.json, "dump", boom)
    with pytest.raises(StoreError, match="No space left"):
        store.save()
    assert path.read_bytes() == before
    assert not path.with_name("actiontrack.json.tmp").exists()


def test_read_only_store(store, path, monkeypatch):  # TC-STO-064
    store.save()
    before = path.read_bytes()

    def denied(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(StoreError, match="read-only"):
        store.save()
    assert path.read_bytes() == before


# ---------------------------------------------------------------- performance


@pytest.mark.perf
def test_thousand_items_load_and_save_fast(path):  # TC-STO-080
    store = Store(path)
    for i in range(1_000):
        store.add(make_item(f"task {i}"))
    start = time.perf_counter()
    store.save()
    assert len(Store(path).load_all()) == 1_000
    assert time.perf_counter() - start < 0.5
