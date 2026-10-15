"""The ``ingest`` pipeline: notes -> items -> store (M2 to M7, M10).

Each note is processed inside its own error boundary so one bad file
never stops the run (NFR-01). Notes are processed oldest meeting first so
the newest meeting decides due dates and status (M6). The store is saved
once, at the end.
"""

from __future__ import annotations

from pathlib import Path

from actiontrack.dates import resolve_due_date
from actiontrack.dedupe import DedupeIndex, dedupe_into
from actiontrack.extractor import extract_items
from actiontrack.models import Note, ResolvedItem, SkippedFile
from actiontrack.owners import resolve_owner
from actiontrack.reader import read_notes
from actiontrack.report import IngestReport, SkippedItem
from actiontrack.store import Store


def run_ingest(folder: Path, store: Store) -> IngestReport:
    notes, skipped = read_notes(folder)
    report = IngestReport(folder=folder, skipped=list(skipped))
    index = DedupeIndex(store.load_all())

    for note in sorted(notes, key=lambda n: (n.meeting_date, n.file_name)):
        try:
            resolved = resolve_note(note, report)
            outcomes = dedupe_into(store, resolved, index)
        except Exception as exc:  # one bad note must never stop the run
            report.skipped.append(SkippedFile(note.file_name, f"unexpected error: {exc}"))
            continue
        report.record(note.file_name, outcomes)

    store.save()
    return report


def resolve_note(note: Note, report: IngestReport) -> list[ResolvedItem]:
    """Resolve owner and due date for every item in ``note``."""
    resolved = []
    for raw in extract_items(note):
        try:
            resolved.append(
                ResolvedItem(
                    raw=raw,
                    owner=resolve_owner(raw.owner_phrase, note.attendees),
                    due_date=resolve_due_date(raw.due_phrase, note.meeting_date),
                    note=note,
                )
            )
        except Exception as exc:  # one bad line must not lose the rest of the note
            report.skipped_items.append(
                SkippedItem(note.file_name, raw.line_number, f"unexpected error: {exc}")
            )
    return resolved
