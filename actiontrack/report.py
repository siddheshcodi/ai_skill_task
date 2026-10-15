"""M10 Reporting: the summary printed at the end of ``ingest``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from actiontrack.dedupe import DedupeOutcome
from actiontrack.models import AMBIGUOUS, UNASSIGNED, SkippedFile

_LABEL_WIDTH = 26
_NUMBER_WIDTH = 4


@dataclass(frozen=True)
class SkippedItem:
    """A single action item line that could not be processed."""

    file_name: str
    line_number: int
    reason: str


@dataclass(frozen=True)
class FlaggedOwner:
    """An owner that is not in the meeting's attendee list (E7)."""

    file_name: str
    owner: str
    item_id: int


@dataclass
class IngestReport:
    """Counts and problems for one ingest run (counts cover this run; QA-42)."""

    folder: Path
    files_read: int = 0
    skipped: list[SkippedFile] = field(default_factory=list)
    skipped_items: list[SkippedItem] = field(default_factory=list)
    new_items: int = 0
    duplicates_merged: int = 0
    unassigned: set[int] = field(default_factory=set)
    ambiguous: set[int] = field(default_factory=set)
    flagged_owners: dict[int, FlaggedOwner] = field(default_factory=dict)

    def record(self, file_name: str, outcomes: list[DedupeOutcome]) -> None:
        self.files_read += 1
        for outcome in outcomes:
            item = outcome.item
            assert item.id is not None
            if outcome.created:
                self.new_items += 1
            else:
                self.duplicates_merged += 1
            if item.owner == UNASSIGNED:
                self.unassigned.add(item.id)
            elif item.owner == AMBIGUOUS:
                self.ambiguous.add(item.id)
            elif item.not_in_attendees and item.id not in self.flagged_owners:
                self.flagged_owners[item.id] = FlaggedOwner(file_name, item.owner, item.id)


def format_report(report: IngestReport) -> str:
    lines = [
        "Ingest complete",
        _count("Files read", report.files_read),
        _count("Files skipped", len(report.skipped)),
        _count("New items", report.new_items),
        _count("Duplicates merged", report.duplicates_merged),
        _count("Unassigned items", len(report.unassigned)),
        _count("Ambiguous owners", len(report.ambiguous)),
        _count("Owners not in attendees", len(report.flagged_owners)),
    ]
    if report.skipped_items:
        lines.append(_count("Items skipped", len(report.skipped_items)))

    if report.skipped:
        lines += ["", "Skipped files:"]
        lines += [f"  - {_path(report, s.file_name)}: {s.reason}" for s in report.skipped]
    if report.skipped_items:
        lines += ["", "Skipped items:"]
        lines += [
            f"  - {_path(report, s.file_name)} line {s.line_number}: {s.reason}"
            for s in report.skipped_items
        ]
    if report.flagged_owners:
        lines += ["", "Owners not in attendee list:"]
        lines += [
            f'  - {_path(report, f.file_name)}: "{f.owner}" (item {f.item_id})'
            for f in sorted(report.flagged_owners.values(), key=lambda f: f.item_id)
        ]
    return "\n".join(lines)


def _count(label: str, value: int) -> str:
    return f"  {label + ':':<{_LABEL_WIDTH}}{value:>{_NUMBER_WIDTH}}"


def _path(report: IngestReport, file_name: str) -> str:
    return (report.folder / file_name).as_posix()
