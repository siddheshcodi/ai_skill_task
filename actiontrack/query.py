"""M8 Query and Status Update: filter items, show them, mark them done.

The overdue rule lives here only (``is_overdue``); M9 reuses it. "Today"
is always passed in, so results are testable and never stored.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from datetime import date
from enum import Enum

from actiontrack.errors import NotFoundError
from actiontrack.models import (
    AMBIGUOUS,
    STATUS_DONE,
    STATUS_OPEN,
    STATUS_OVERDUE,
    UNASSIGNED,
    Item,
)
from actiontrack.owners import clean_phrase, name_matches
from actiontrack.store import Store

OVERDUE_LABEL = "OVERDUE"
NO_ITEMS = "No items found."
TASK_WIDTH = 40
OWNER_WIDTH = 40
MIN_TASK_WIDTH = 16
_RED, _RESET = "\033[31m", "\033[0m"
_GAP = "  "


def is_overdue(item: Item, today: date) -> bool:
    """Open, has a due date, and that date is before today (E4: no date, never)."""
    return item.status == STATUS_OPEN and item.due_date is not None and item.due_date < today


def display_status(item: Item, today: date) -> str:
    return OVERDUE_LABEL if is_overdue(item, today) else item.status


# ---------------------------------------------------------------- filters


def owner_filter(query: str) -> Callable[[Item], bool]:
    """``--owner``: full or first name, any case; ambiguous items match a candidate."""
    wanted = clean_phrase(query)
    if wanted.casefold() in (UNASSIGNED, AMBIGUOUS):
        group = wanted.casefold()
        return lambda item: item.owner == group

    def matches(item: Item) -> bool:
        if item.owner == AMBIGUOUS:  # QA-33: show items that may be theirs
            return any(name_matches(wanted, name) for name in item.owner_candidates)
        return item.owner != UNASSIGNED and name_matches(wanted, item.owner)

    return matches


def status_filter(status: str, today: date) -> Callable[[Item], bool]:
    if status == STATUS_OVERDUE:
        return lambda item: is_overdue(item, today)
    return lambda item: item.status == status  # "open" includes overdue items


def filter_items(
    items: list[Item],
    *,
    today: date,
    owner: str | None = None,
    status: str | None = None,
    due_before: date | None = None,
) -> list[Item]:
    """Items matching every given filter (AND), sorted by ID."""
    checks: list[Callable[[Item], bool]] = []
    if owner is not None:
        checks.append(owner_filter(owner))
    if status is not None:
        checks.append(status_filter(status, today))
    if due_before is not None:
        checks.append(lambda item: item.due_date is not None and item.due_date < due_before)
    selected = [item for item in items if all(check(item) for check in checks)]
    return sorted(selected, key=lambda item: item.id or 0)


# ---------------------------------------------------------------- mark done


class DoneResult(Enum):
    DONE = "done"
    ALREADY_DONE = "already done"


def mark_done(store: Store, item_id: int) -> tuple[DoneResult, Item]:
    """Mark one item done. The caller saves the store when the result is DONE."""
    item = store.get(item_id)
    if item is None:
        raise NotFoundError(f"Item {item_id} not found. Run 'actiontrack list' to see item IDs.")
    if item.status == STATUS_DONE:
        return DoneResult.ALREADY_DONE, item
    item.status = STATUS_DONE
    store.update(item)
    return DoneResult.DONE, item


# ---------------------------------------------------------------- table


def format_table(
    items: list[Item],
    today: date,
    *,
    color: bool = False,
    max_width: int | None = None,
) -> str:
    """A readable table; overdue items are labelled (and red when ``color``)."""
    if not items:
        return NO_ITEMS

    headers = ["ID", "Owner", "Task", "Due", "Status", "Source"]
    rows = [
        [
            str(item.id),
            _truncate(_owner_text(item), OWNER_WIDTH),
            item.task,
            item.due_date.isoformat() if item.due_date else "-",
            display_status(item, today),
            _source_text(item),
        ]
        for item in items
    ]
    widths = [max(_width(row[col]) for row in [headers, *rows]) for col in range(len(headers))]
    widths[2] = min(widths[2], _task_width(widths, max_width))
    for row in rows:
        row[2] = _truncate(row[2], widths[2])

    lines = [_line(headers, widths), _line(["-" * w for w in widths], widths)]
    for row in rows:
        line = _line(row, widths)
        if color and row[4] == OVERDUE_LABEL:
            line = f"{_RED}{line}{_RESET}"
        lines.append(line)

    overdue = sum(1 for row in rows if row[4] == OVERDUE_LABEL)
    noun = "item" if len(rows) == 1 else "items"
    lines += ["", f"{len(rows)} {noun}, {overdue} overdue"]
    return "\n".join(lines)


def _owner_text(item: Item) -> str:
    if item.owner == AMBIGUOUS and item.owner_candidates:
        return f"ambiguous: {' / '.join(item.owner_candidates)}"
    return item.owner


def _source_text(item: Item) -> str:
    if not item.source_files:
        return "-"
    extra = len(item.source_files) - 1
    return item.source_files[0] + (f" (+{extra})" if extra else "")


def _task_width(widths: list[int], max_width: int | None) -> int:
    """Shrink only the task column so the table fits the terminal."""
    if max_width is None:
        return TASK_WIDTH
    others = sum(w for i, w in enumerate(widths) if i != 2) + len(_GAP) * (len(widths) - 1)
    return max(MIN_TASK_WIDTH, min(TASK_WIDTH, max_width - others))


def _line(cells: list[str], widths: list[int]) -> str:
    padded = [
        cell + " " * (width - _width(cell)) for cell, width in zip(cells, widths, strict=True)
    ]
    return _GAP.join(padded).rstrip()


def _width(text: str) -> int:
    """Terminal columns used by ``text`` (wide CJK = 2, combining marks = 0)."""
    total = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def _truncate(text: str, limit: int) -> str:
    if _width(text) <= limit:
        return text
    kept, used = [], 0
    for ch in text:
        if used + _width(ch) > limit - 3:
            break
        kept.append(ch)
        used += _width(ch)
    return "".join(kept).rstrip() + "..."
