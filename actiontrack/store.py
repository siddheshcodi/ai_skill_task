"""M7 Storage: one JSON file holding every action item.

Layout::

    {"version": 1, "next_id": 13, "items": [{"id": 1, ...}, ...]}

* IDs come from ``next_id`` so they are never reused, and never change
  after re-ingesting (E10).
* ``save`` writes a temp file and swaps it in with ``os.replace``, so a
  crash leaves either the old or the new store, never half a file.
* A store that cannot be parsed raises ``StoreError`` and is never
  overwritten.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from actiontrack.errors import NotFoundError, StoreError
from actiontrack.models import STORED_STATUSES, Item

STORE_VERSION = 1


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Store:
    """Items kept in memory after the first access; written by ``save``."""

    def __init__(self, path: Path, now: Callable[[], datetime] = _now) -> None:
        self.path = path
        self._now = now
        self._items: dict[int, Item] = {}
        self._next_id = 1
        self._loaded = False
        self.warnings: list[str] = []

    # ------------------------------------------------------------ queries

    def load_all(self) -> list[Item]:
        self._ensure_loaded()
        return [self._items[item_id] for item_id in sorted(self._items)]

    def get(self, item_id: int) -> Item | None:
        self._ensure_loaded()
        return self._items.get(item_id)

    # ------------------------------------------------------------ changes

    def add(self, item: Item) -> Item:
        """Store a new item; the store assigns its ID and timestamps."""
        self._ensure_loaded()
        item.id = self._next_id
        self._next_id += 1
        item.created_at = item.updated_at = self._now()
        self._items[item.id] = item
        return item

    def update(self, item: Item) -> None:
        """Record that ``item`` changed (refreshes ``updated_at``)."""
        self._ensure_loaded()
        if item.id is None or item.id not in self._items:
            raise NotFoundError(f"Item {item.id} not found.")
        item.updated_at = self._now()
        self._items[item.id] = item

    def save(self) -> None:
        """Write the store atomically, keeping the previous file as ``.bak``."""
        self._ensure_loaded()
        data = {
            "version": STORE_VERSION,
            "next_id": self._next_id,
            "items": [item_to_dict(item) for item in self.load_all()],
        }
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if self.path.exists():
                shutil.copyfile(self.path, self.path.with_name(self.path.name + ".bak"))
            os.replace(tmp, self.path)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise StoreError(
                f"cannot write store file '{self.path}' ({exc.strerror or exc}). "
                "Check the file is not read-only or open in another program."
            ) from exc

    # ------------------------------------------------------------ loading

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load()
        self._loaded = True

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise StoreError(f"cannot read store file '{self.path}' ({exc}).") from exc
        if not text.strip():
            self.warnings.append(f"store file '{self.path}' was empty; starting a new store.")
            return
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StoreError(
                f"store file '{self.path}' is corrupt (line {exc.lineno}, column {exc.colno}: "
                f"{exc.msg}). Fix it or restore '{self.path.name}.bak', then try again."
            ) from exc
        self._items, self._next_id = _parse_store(data, self.path)


# ---------------------------------------------------------------- serialisation


def item_to_dict(item: Item) -> dict[str, Any]:
    return {
        "id": item.id,
        "owner": item.owner,
        "owner_candidates": list(item.owner_candidates),
        "task": item.task,
        "raw_text": item.raw_text,
        "due_date": _iso(item.due_date),
        "due_phrase": item.due_phrase,
        "status": item.status,
        "source_files": list(item.source_files),
        "meeting_date": _iso(item.meeting_date),
        "meeting_title": item.meeting_title,
        "last_seen_meeting_date": _iso(item.last_seen_meeting_date),
        "not_in_attendees": item.not_in_attendees,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def item_from_dict(data: Any) -> Item:
    """Rebuild an item; raises ``ValueError`` describing the first bad field."""
    if not isinstance(data, dict):
        raise ValueError("item is not an object")
    status = _field(data, "status", str)
    if status not in STORED_STATUSES:
        raise ValueError(f"status '{status}' is not one of {', '.join(STORED_STATUSES)}")
    item_id = _field(data, "id", int)
    if item_id < 1:
        raise ValueError(f"id {item_id} must be 1 or more")
    meeting_date = _date(data, "meeting_date")
    return Item(
        id=item_id,
        owner=_field(data, "owner", str),
        owner_candidates=_str_list(data, "owner_candidates"),
        task=_field(data, "task", str),
        raw_text=_field(data, "raw_text", str),
        due_date=_date(data, "due_date", optional=True),
        due_phrase=_field(data, "due_phrase", str, optional=True),
        status=status,
        source_files=_str_list(data, "source_files"),
        meeting_date=meeting_date,
        meeting_title=_field(data, "meeting_title", str, optional=True),
        last_seen_meeting_date=_date(data, "last_seen_meeting_date", optional=True) or meeting_date,
        not_in_attendees=bool(data.get("not_in_attendees", False)),
        created_at=_timestamp(data, "created_at"),
        updated_at=_timestamp(data, "updated_at"),
    )


def _parse_store(data: Any, path: Path) -> tuple[dict[int, Item], int]:
    def bad(problem: str) -> StoreError:
        return StoreError(f"store file '{path}' is invalid: {problem}. Fix it or restore the .bak.")

    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise bad("expected an object with an 'items' list")
    version = data.get("version", STORE_VERSION)
    if not isinstance(version, int) or version > STORE_VERSION:
        raise bad(f"unsupported version {version!r} (this program reads version {STORE_VERSION})")

    items: dict[int, Item] = {}
    for position, raw in enumerate(data["items"], start=1):
        try:
            item = item_from_dict(raw)
        except ValueError as exc:
            raise bad(f"item #{position}: {exc}") from exc
        if item.id in items:
            raise bad(f"item ID {item.id} appears more than once")
        items[item.id] = item

    next_id = data.get("next_id", 1)
    if not isinstance(next_id, int) or isinstance(next_id, bool):
        raise bad("'next_id' must be a whole number")
    return items, max(next_id, max(items, default=0) + 1)


def _iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _field(data: dict, key: str, kind: type, optional: bool = False) -> Any:
    value = data.get(key)
    if value is None and optional:
        return None
    if not isinstance(value, kind) or isinstance(value, bool) is not (kind is bool):
        raise ValueError(f"'{key}' must be {kind.__name__}, got {value!r}")
    return value


def _str_list(data: dict, key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"'{key}' must be a list of text")
    return list(value)


def _date(data: dict, key: str, optional: bool = False) -> date | None:
    value = _field(data, key, str, optional)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"'{key}' is not a YYYY-MM-DD date: {value!r}") from exc


def _timestamp(data: dict, key: str) -> datetime | None:
    value = _field(data, key, str, optional=True)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"'{key}' is not an ISO timestamp: {value!r}") from exc
