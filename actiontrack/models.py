"""Data types shared between modules (see plan.md section 5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

UNASSIGNED = "unassigned"
AMBIGUOUS = "ambiguous"

STATUS_OPEN = "open"
STATUS_DONE = "done"
STATUS_OVERDUE = "overdue"  # computed for display and filtering, never stored

STORED_STATUSES = (STATUS_OPEN, STATUS_DONE)
FILTER_STATUSES = (STATUS_OPEN, STATUS_DONE, STATUS_OVERDUE)


@dataclass(frozen=True)
class Note:
    """One meeting note that was read successfully (M2)."""

    file_name: str
    title: str | None
    meeting_date: date
    attendees: list[str]
    text: str


@dataclass(frozen=True)
class SkippedFile:
    """A note that could not be read, with the reason (M2, M10)."""

    file_name: str
    reason: str


@dataclass(frozen=True)
class RawItem:
    """A checkbox line split into parts, before resolution (M3)."""

    raw_text: str
    owner_phrase: str | None
    task: str
    due_phrase: str | None
    status: str
    line_number: int


@dataclass(frozen=True)
class OwnerResult:
    """Outcome of matching an owner phrase to attendees (M4)."""

    owner: str
    candidates: list[str] = field(default_factory=list)
    not_in_attendees: bool = False


@dataclass(frozen=True)
class ResolvedItem:
    """A raw item with its owner and due date resolved (M4 + M5)."""

    raw: RawItem
    owner: OwnerResult
    due_date: date | None
    note: Note


@dataclass(frozen=True)
class Email:
    """A composed follow-up email (M9). Only ever saved as a draft."""

    to: str
    subject: str
    body: str


@dataclass
class Item:
    """One stored action item (M7 data model)."""

    owner: str
    task: str
    raw_text: str
    status: str
    meeting_date: date
    last_seen_meeting_date: date
    id: int | None = None
    owner_candidates: list[str] = field(default_factory=list)
    due_date: date | None = None
    due_phrase: str | None = None
    source_files: list[str] = field(default_factory=list)
    meeting_title: str | None = None
    not_in_attendees: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
