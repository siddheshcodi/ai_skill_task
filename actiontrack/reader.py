"""M2 Note Reader: find .md notes in a folder and read their header.

``read_notes`` never raises because of one file (NFR-01). A file that cannot
be read or has no valid meeting date becomes a ``SkippedFile`` with a reason
(E8), and the next file is processed.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from actiontrack.models import Note, SkippedFile

NOTE_SUFFIX = ".md"
HEADER_LINES = 30  # the date and attendees are searched in the first N non-empty lines

REASON_EMPTY = "file is empty"
REASON_NO_DATE = "no meeting date found"
REASON_ENCODING = "cannot read file (encoding error)"
REASON_PERMISSION = "cannot read file (permission denied)"
REASON_VANISHED = "cannot read file (file no longer exists)"

_EMPHASIS = r"[*_]*"
_DATE_LINE_RE = re.compile(
    rf"^\s*{_EMPHASIS}date{_EMPHASIS}\s*:{_EMPHASIS}\s*(?P<value>.*?)\s*$", re.I
)
_ATTENDEES_LINE_RE = re.compile(
    rf"^\s*{_EMPHASIS}attendees{_EMPHASIS}\s*:{_EMPHASIS}\s*(?P<value>.*?)\s*$", re.I
)
_TITLE_RE = re.compile(r"^\s*#\s+(?P<value>.+?)\s*#*\s*$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


class NoteReadError(Exception):
    """A note was skipped; ``str(exc)`` is the reason shown to the user."""


def read_notes(folder: Path) -> tuple[list[Note], list[SkippedFile]]:
    """Read every note in ``folder`` (top level only, sorted by file name)."""
    notes: list[Note] = []
    skipped: list[SkippedFile] = []
    for path in list_note_files(folder):
        try:
            notes.append(parse_note(path.name, read_text(path)))
        except NoteReadError as exc:
            skipped.append(SkippedFile(path.name, str(exc)))
        except Exception as exc:  # one bad file must never stop the run
            skipped.append(SkippedFile(path.name, f"unexpected error: {exc}"))
    return notes, skipped


def list_note_files(folder: Path) -> list[Path]:
    """``.md`` files (any case) directly inside ``folder``; hidden/lock files excluded."""
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.suffix.lower() == NOTE_SUFFIX
            and not path.name.startswith((".", "~"))
            and path.is_file()
        ),
        key=lambda path: path.name,
    )


def read_text(path: Path) -> str:
    """Decode a note as UTF-8 (BOM allowed) or BOM-marked UTF-16."""
    try:
        data = path.read_bytes()
    except PermissionError as exc:
        raise NoteReadError(REASON_PERMISSION) from exc
    except FileNotFoundError as exc:
        raise NoteReadError(REASON_VANISHED) from exc
    except OSError as exc:
        raise NoteReadError(f"cannot read file ({exc.strerror or exc})") from exc

    encoding = "utf-16" if data.startswith(_UTF16_BOMS) else "utf-8-sig"
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise NoteReadError(REASON_ENCODING) from exc
    if "\x00" in text:  # binary content that happens to decode
        raise NoteReadError(REASON_ENCODING)
    return text


def parse_note(file_name: str, text: str) -> Note:
    """Build a ``Note`` from file text; raises ``NoteReadError`` if malformed."""
    if not text.strip():
        raise NoteReadError(REASON_EMPTY)
    header = _header_lines(text)
    return Note(
        file_name=file_name,
        title=parse_title(text),
        meeting_date=parse_meeting_date(header),
        attendees=parse_attendees(header),
        text=text,
    )


def parse_meeting_date(header: list[str]) -> date:
    """The first ``Date:`` line in the header wins (QA-7)."""
    for line in header:
        match = _DATE_LINE_RE.match(line)
        if match:
            value = match.group("value").strip("*_ ")
            if not value:
                raise NoteReadError("meeting date is empty")
            if _ISO_DATE_RE.match(value):
                try:
                    return date.fromisoformat(value)
                except ValueError:
                    pass
            raise NoteReadError(f"invalid meeting date '{value}' (use YYYY-MM-DD)")
    raise NoteReadError(REASON_NO_DATE)


def parse_attendees(header: list[str]) -> list[str]:
    """Comma-separated names from the first ``Attendees:`` line; [] if none."""
    for line in header:
        match = _ATTENDEES_LINE_RE.match(line)
        if match:
            names: list[str] = []
            seen: set[str] = set()
            for part in match.group("value").split(","):
                name = " ".join(part.strip("*_ ").split())
                if name and name.casefold() not in seen:
                    seen.add(name.casefold())
                    names.append(name)
            return names
    return []


def parse_title(text: str) -> str | None:
    """The first level-1 heading, if any."""
    for line in text.splitlines():
        match = _TITLE_RE.match(line)
        if match:
            return match.group("value")
    return None


def _header_lines(text: str) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[:HEADER_LINES]
