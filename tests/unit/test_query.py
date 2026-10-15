"""M8 Query and Status Update tests (modules/m08-query-status/test_cases.md).

Seed store = the 8-item table in that file; today = 2026-10-15.
"""

from __future__ import annotations

import time
from datetime import date

import pytest

from actiontrack.errors import NotFoundError
from actiontrack.models import Item
from actiontrack.query import (
    NO_ITEMS,
    DoneResult,
    _width,
    filter_items,
    format_table,
    is_overdue,
    mark_done,
)
from actiontrack.store import Store

TODAY = date(2026, 10, 15)
SEED = [
    # owner, task, due, status, sources, candidates
    ("Priya Shah", "send the revised quote", "2026-10-09", "open", ["sales-1006.md"], []),
    ("Rahul Mehta", "update the CRM", "2026-10-20", "open", ["sales-1006.md"], []),
    ("Anita Rao", "book the demo room", "2026-10-08", "done", ["sales-1006.md"], []),
    ("unassigned", "share the slide deck", None, "open", ["sales-1006.md"], []),
    (
        "ambiguous",
        "review contract",
        "2026-10-14",
        "open",
        ["legal-1008.md"],
        ["Priya Shah", "Priya Kumar"],
    ),
    ("Priya Kumar", "prepare invoice", "2026-10-15", "open", ["legal-1008.md"], []),
    (
        "Priya Shah",
        "update pricing sheet",
        None,
        "open",
        ["sales-1006.md", "sales-1013.md"],
        [],
    ),
    ("Rahul Mehta", "call the client", "2026-10-16", "open", ["sales-1013.md"], []),
]


def build_item(owner, task, due, status, sources, candidates) -> Item:
    meeting = date(2026, 10, 6)
    return Item(
        owner=owner,
        owner_candidates=list(candidates),
        task=task,
        raw_text=task,
        status=status,
        meeting_date=meeting,
        last_seen_meeting_date=meeting,
        due_date=date.fromisoformat(due) if due else None,
        source_files=list(sources),
    )


@pytest.fixture
def store(tmp_path) -> Store:
    store = Store(tmp_path / "actiontrack.json")
    for row in SEED:
        store.add(build_item(*row))
    store.save()
    return store


@pytest.fixture
def items(store) -> list[Item]:
    return store.load_all()


def ids(items: list[Item]) -> list[int]:
    return [item.id for item in items]


def select(items, **filters) -> list[int]:
    return ids(filter_items(items, today=TODAY, **filters))


# ---------------------------------------------------------------- overdue rule


def item_due(due: str | None, status: str = "open") -> Item:
    return build_item("Priya Shah", "t", due, status, [], [])


@pytest.mark.parametrize(
    ("due", "status", "expected"),
    [
        ("2026-10-09", "open", True),  # TC-QRY-001
        ("2026-10-14", "open", True),  # TC-QRY-002 yesterday
        ("2026-10-15", "open", False),  # TC-QRY-003 today
        ("2026-10-16", "open", False),  # TC-QRY-004 tomorrow
        ("2026-10-08", "done", False),  # TC-QRY-005
        (None, "open", False),  # TC-QRY-006
    ],
)
def test_overdue_rule(due, status, expected):
    assert is_overdue(item_due(due, status), TODAY) is expected


@pytest.mark.edge("E4")
def test_item_without_due_date_is_never_overdue():  # TC-QRY-006
    assert not is_overdue(item_due(None), date(2099, 1, 1))


def test_becomes_overdue_over_time():  # TC-QRY-009
    item = item_due("2026-10-16")
    assert not is_overdue(item, date(2026, 10, 16))
    assert is_overdue(item, date(2026, 10, 17))


def test_overdue_is_not_stored(store, items, tmp_path):  # TC-QRY-008, TC-QRY-122
    before = store.path.read_bytes()
    format_table(filter_items(items, today=TODAY, status="overdue"), TODAY)
    assert store.path.read_bytes() == before
    assert {item.status for item in Store(store.path).load_all()} == {"open", "done"}


# ---------------------------------------------------------------- filters


def test_no_filters_shows_everything(items):  # TC-QRY-020, FR-LST-01
    assert select(items) == [1, 2, 3, 4, 5, 6, 7, 8]


@pytest.mark.parametrize(
    ("owner", "expected"),
    [
        ("Priya Shah", [1, 5, 7]),  # TC-QRY-040 (+ ambiguous #5, QA-33)
        ("rahul", [2, 8]),  # TC-QRY-041
        ("RAHUL", [2, 8]),  # TC-QRY-042
        ("rAhUl mEhTa", [2, 8]),
        ("priya", [1, 5, 6, 7]),  # TC-QRY-043
        ("Priya Kumar", [5, 6]),  # TC-QRY-044
        ("unassigned", [4]),  # TC-QRY-045
        ("Unassigned", [4]),
        ("ambiguous", [5]),  # TC-QRY-046
        ("Vikram", []),  # TC-QRY-047
        ("Pri", []),  # TC-QRY-048 (QA-34)
        ("Shah", []),  # TC-QRY-049
        ("  Priya   Shah ", [1, 5, 7]),  # TC-QRY-050
    ],
)
def test_owner_filter(items, owner, expected):  # FR-LST-02
    assert select(items, owner=owner) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("open", [1, 2, 4, 5, 6, 7, 8]),  # TC-QRY-060 includes overdue
        ("done", [3]),  # TC-QRY-061
        ("overdue", [1, 5]),  # TC-QRY-062
    ],
)
def test_status_filter(items, status, expected):  # FR-LST-03
    assert select(items, status=status) == expected


@pytest.mark.parametrize(
    ("due_before", "expected"),
    [
        ("2026-10-15", [1, 3, 5]),  # TC-QRY-070/071 strict: #6 (10-15) excluded
        ("2030-01-01", [1, 2, 3, 5, 6, 8]),  # TC-QRY-072 no-date items excluded
        ("2026-10-10", [1, 3]),  # TC-QRY-073 done items included
        ("2000-01-01", []),  # TC-QRY-074
    ],
)
def test_due_before_filter(items, due_before, expected):  # FR-LST-04
    assert select(items, due_before=date.fromisoformat(due_before)) == expected


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"owner": "Priya Shah", "status": "overdue"}, [1, 5]),  # TC-QRY-080
        ({"owner": "rahul", "due_before": date(2026, 10, 18)}, [8]),  # TC-QRY-081
        ({"status": "open", "due_before": date(2026, 10, 16)}, [1, 5, 6]),  # TC-QRY-082
        (
            {"owner": "Priya Shah", "status": "open", "due_before": date(2026, 10, 31)},
            [1, 5],
        ),  # TC-QRY-083
        ({"status": "done", "due_before": date(2000, 1, 1)}, []),  # TC-QRY-084
        ({"status": "overdue", "due_before": date(2026, 10, 10)}, [1]),  # TC-QRY-085
    ],
)
def test_combined_filters(items, filters, expected):  # FR-LST-05
    assert select(items, **filters) == expected


# ---------------------------------------------------------------- table


def test_table_layout(items):  # TC-QRY-021..025, TC-QRY-028, FR-LST-06
    lines = format_table(items, TODAY).splitlines()
    assert lines[0].split() == ["ID", "Owner", "Task", "Due", "Status", "Source"]
    assert set(lines[1].replace(" ", "")) == {"-"}
    row = {int(line.split()[0]): line for line in lines[2:10]}
    assert "OVERDUE" in row[1] and "OVERDUE" in row[5]
    assert "OVERDUE" not in row[6]  # due today
    assert " - " in row[4]  # no due date shown as "-"
    assert "ambiguous: Priya Shah / Priya Kumar" in row[5]
    assert "sales-1006.md (+1)" in row[7]
    assert lines[-1] == "8 items, 2 overdue"


def test_columns_are_aligned(items):
    lines = format_table(items, TODAY).splitlines()[:10]
    status_column = lines[0].index("Status")
    assert all(line[status_column - 2 : status_column] == "  " for line in lines)


def test_long_task_is_truncated():  # TC-QRY-026
    item = build_item("Priya Shah", "x" * 200, None, "open", ["a.md"], [])
    item.id = 1
    task_cell = format_table([item], TODAY).splitlines()[2].split()[3]
    assert task_cell.endswith("...")
    assert len(task_cell) == 40


def task_column_width(table: str) -> int:
    header = table.splitlines()[0]
    return header.index("Due") - header.index("Task") - 2


def test_task_column_shrinks_to_terminal_width(items):  # TC-QRY-121
    assert task_column_width(format_table(items, TODAY)) == 22  # longest task
    narrow = format_table(items, TODAY, max_width=102)
    assert task_column_width(narrow) == 20  # other columns + gaps use 82
    assert max(len(line) for line in narrow.splitlines()) <= 102
    assert task_column_width(format_table(items, TODAY, max_width=40)) == 16  # minimum


def test_unicode_alignment():  # TC-QRY-027
    a = build_item("José Núñez", "revisar 契約", None, "open", ["a.md"], [])
    b = build_item("Rahul Mehta", "call the client", None, "open", ["b.md"], [])
    a.id, b.id = 1, 2
    lines = format_table([a, b], TODAY).splitlines()

    def due_column(line: str) -> int:  # display columns before the "-" due cell
        return _width(line[: line.index("  -  ") + 2])

    assert due_column(lines[2]) == due_column(lines[3])


def test_single_item_footer():
    item = build_item("Priya Shah", "t", None, "open", ["a.md"], [])
    item.id = 1
    assert format_table([item], TODAY).splitlines()[-1] == "1 item, 0 overdue"


def test_empty_result():  # TC-QRY-029, TC-QRY-047
    assert format_table([], TODAY) == NO_ITEMS


def test_colour_only_on_overdue_rows(items):  # FR-LST-06, TC-QRY-030
    coloured = format_table(items, TODAY, color=True).splitlines()
    red = [line for line in coloured if line.startswith("\033[31m")]
    assert len(red) == 2 and all("OVERDUE" in line for line in red)
    assert "\033[" not in format_table(items, TODAY, color=False)


# ---------------------------------------------------------------- done


def test_mark_done(store):  # TC-QRY-100, FR-DON-01
    result, item = mark_done(store, 2)
    assert (result, item.status) == (DoneResult.DONE, "done")


def test_mark_overdue_item_done(store):  # TC-QRY-102
    mark_done(store, 1)
    assert select(store.load_all(), status="overdue") == [5]


def test_already_done(store):  # TC-QRY-103, FR-DON-03
    stamp = store.get(3).updated_at
    result, _ = mark_done(store, 3)
    assert result is DoneResult.ALREADY_DONE
    assert store.get(3).updated_at == stamp


def test_missing_id(store):  # TC-QRY-104, FR-DON-02
    with pytest.raises(NotFoundError, match="Item 99 not found"):
        mark_done(store, 99)


@pytest.mark.parametrize("item_id", [4, 5])
def test_done_on_unassigned_and_ambiguous(store, item_id):  # TC-QRY-105/106
    assert mark_done(store, item_id)[0] is DoneResult.DONE


# ---------------------------------------------------------------- performance


@pytest.mark.perf
def test_list_thousand_items_fast():  # TC-QRY-120
    many = []
    for n in range(1_000):
        item = build_item(*SEED[n % len(SEED)])
        item.id = n + 1
        many.append(item)
    start = time.perf_counter()
    for filters in ({}, {"owner": "priya"}, {"status": "overdue"}):
        format_table(filter_items(many, today=TODAY, **filters), TODAY)
    assert time.perf_counter() - start < 1.0
