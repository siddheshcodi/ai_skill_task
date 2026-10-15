"""M2 Note Reader tests (modules/m02-note-reader/test_cases.md)."""

from __future__ import annotations

import hashlib
import random
import time
from datetime import date
from pathlib import Path

import pytest

from actiontrack import reader
from actiontrack.reader import (
    REASON_EMPTY,
    REASON_ENCODING,
    REASON_NO_DATE,
    REASON_PERMISSION,
    list_note_files,
    parse_note,
    read_notes,
)

VALID = """\
# Weekly Sales Sync
Date: 2026-10-06
Attendees: Priya Shah, Rahul Mehta, Anita Rao

## Action items
- [ ] Priya to send the revised quote by Friday
"""


def write(folder: Path, name: str, content: str | bytes) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="")
    return path


def note_with_header(*header_lines: str) -> str:
    return "\n".join(["# Title", *header_lines, "", "- [ ] Priya to send quote"]) + "\n"


# ---------------------------------------------------------------- discovery


def test_reads_all_md_files(tmp_path):  # TC-RDR-001
    for name in ("a.md", "b.md", "c.md"):
        write(tmp_path, name, VALID)
    notes, skipped = read_notes(tmp_path)
    assert [n.file_name for n in notes] == ["a.md", "b.md", "c.md"]
    assert skipped == []


@pytest.mark.edge("E11")
def test_non_md_files_are_ignored_not_skipped(tmp_path):  # TC-RDR-002, TC-RDR-004
    write(tmp_path, "a.md", VALID)
    for name in ("b.txt", "c.pdf", "d.docx", "e.md.bak", "f.markdown"):
        write(tmp_path, name, VALID)
    notes, skipped = read_notes(tmp_path)
    assert [n.file_name for n in notes] == ["a.md"]
    assert skipped == []


def test_upper_case_extension_accepted(tmp_path):  # TC-RDR-003 (QA-3)
    write(tmp_path, "NOTES.MD", VALID)
    write(tmp_path, "Other.Md", VALID)
    assert len(list_note_files(tmp_path)) == 2


def test_sub_folders_are_not_read(tmp_path):  # TC-RDR-005 (QA-4)
    write(tmp_path, "2026/oct/a.md", VALID)
    assert read_notes(tmp_path) == ([], [])


def test_empty_folder(tmp_path):  # TC-RDR-006, TC-RDR-007
    assert read_notes(tmp_path) == ([], [])
    write(tmp_path, "a.txt", "x")
    assert read_notes(tmp_path) == ([], [])


def test_hidden_and_lock_files_ignored(tmp_path):  # TC-RDR-008
    write(tmp_path, ".a.md", VALID)
    write(tmp_path, "~$lock.md", VALID)
    assert read_notes(tmp_path) == ([], [])


def test_stable_sorted_order(tmp_path):  # TC-RDR-009
    for name in ("c.md", "a.md", "b.md"):
        write(tmp_path, name, VALID)
    assert [p.name for p in list_note_files(tmp_path)] == ["a.md", "b.md", "c.md"]


def test_unicode_file_names(tmp_path):  # TC-RDR-010
    write(tmp_path, "Sales sync – Oct.md", VALID)
    write(tmp_path, "réunion.md", VALID)
    notes, _ = read_notes(tmp_path)
    assert {n.file_name for n in notes} == {"Sales sync – Oct.md", "réunion.md"}


# ---------------------------------------------------------------- valid note


def test_valid_note_fields():  # TC-RDR-020, TC-RDR-040, TC-RDR-080
    note = parse_note("sales.md", VALID)
    assert note.file_name == "sales.md"
    assert note.title == "Weekly Sales Sync"
    assert note.meeting_date == date(2026, 10, 6)
    assert note.attendees == ["Priya Shah", "Rahul Mehta", "Anita Rao"]
    assert note.text == VALID


# ---------------------------------------------------------------- meeting date


@pytest.mark.parametrize(
    "line",
    [
        "Date: 2026-10-06",
        "date: 2026-10-06",  # TC-RDR-021
        "DATE: 2026-10-06",
        "**Date:** 2026-10-06",  # TC-RDR-022
        "**Date**: 2026-10-06",
        "Date:2026-10-06",  # TC-RDR-023
        "Date :   2026-10-06  ",
    ],
)
def test_date_label_variants(line):
    assert parse_note("a.md", note_with_header(line)).meeting_date == date(2026, 10, 6)


@pytest.mark.edge("E8")
@pytest.mark.parametrize(
    "value",
    ["06/10/2026", "Oct 6, 2026", "2026-02-30", "2026-13-01", "TBD"],
)
def test_unsupported_or_invalid_date_is_skipped(tmp_path, value):  # TC-RDR-024, TC-RDR-027
    write(tmp_path, "a.md", note_with_header(f"Date: {value}"))
    notes, skipped = read_notes(tmp_path)
    assert notes == []
    assert skipped[0].reason.startswith(f"invalid meeting date '{value}'")


@pytest.mark.edge("E8")
def test_missing_date_is_skipped(tmp_path):  # TC-RDR-026
    write(tmp_path, "meeting_17.md", note_with_header("Attendees: Priya Shah"))
    _, skipped = read_notes(tmp_path)
    assert (skipped[0].file_name, skipped[0].reason) == ("meeting_17.md", REASON_NO_DATE)


def test_date_in_file_name_is_not_used(tmp_path):  # TC-RDR-025 (QA-6)
    write(tmp_path, "2026-10-06-sales.md", note_with_header("Attendees: Priya Shah"))
    assert read_notes(tmp_path)[1][0].reason == REASON_NO_DATE


def test_empty_date_value_is_skipped(tmp_path):  # TC-RDR-028
    write(tmp_path, "a.md", note_with_header("Date:"))
    assert read_notes(tmp_path)[1][0].reason == "meeting date is empty"


def test_first_date_line_wins():  # TC-RDR-029 (QA-7)
    note = parse_note("a.md", note_with_header("Date: 2026-10-06", "Date: 2026-10-08"))
    assert note.meeting_date == date(2026, 10, 6)


def test_date_word_in_discussion_is_ignored():  # TC-RDR-030
    text = note_with_header("Date: 2026-10-06") + "\nNext Date: TBD\n"
    assert parse_note("a.md", text).meeting_date == date(2026, 10, 6)


def test_date_outside_header_area_is_not_found():
    text = "# Title\n" + "\n".join(f"line {i}" for i in range(40)) + "\nDate: 2026-10-06\n"
    with pytest.raises(reader.NoteReadError, match=REASON_NO_DATE):
        parse_note("a.md", text)


def test_leap_day():  # TC-RDR-031
    assert parse_note("a.md", note_with_header("Date: 2028-02-29")).meeting_date == date(
        2028, 2, 29
    )


# ---------------------------------------------------------------- attendees


def attendees(line: str) -> list[str]:
    return parse_note("a.md", note_with_header("Date: 2026-10-06", line)).attendees


@pytest.mark.parametrize(
    "line",
    [
        "attendees: Priya Shah, Rahul Mehta",  # TC-RDR-041
        "**Attendees:** Priya Shah, Rahul Mehta",
        "Attendees : Priya Shah, Rahul Mehta",
        "Attendees:  Priya Shah ,Rahul Mehta,  ,",  # TC-RDR-042
        "Attendees: Priya  Shah, Rahul Mehta",
    ],
)
def test_attendee_variants(line):
    assert attendees(line) == ["Priya Shah", "Rahul Mehta"]


def test_single_attendee():  # TC-RDR-043
    assert attendees("Attendees: Priya Shah") == ["Priya Shah"]


@pytest.mark.edge("E6")
def test_same_first_name_kept_separately():  # TC-RDR-044
    assert attendees("Attendees: Priya Shah, Priya Kumar, Rahul Mehta") == [
        "Priya Shah",
        "Priya Kumar",
        "Rahul Mehta",
    ]


def test_exact_duplicate_attendee_removed():  # TC-RDR-045
    assert attendees("Attendees: Priya Shah, priya shah") == ["Priya Shah"]


def test_missing_attendees_line_gives_empty_list():  # TC-RDR-048
    note = parse_note("a.md", note_with_header("Date: 2026-10-06"))
    assert note.attendees == []


def test_empty_attendees_value():
    assert attendees("Attendees:") == []


def test_unicode_attendees():  # TC-RDR-049
    assert attendees("Attendees: José Núñez, Zoë O'Brien") == ["José Núñez", "Zoë O'Brien"]


# ---------------------------------------------------------------- malformed files


@pytest.mark.edge("E8")
@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"", REASON_EMPTY),  # TC-RDR-060
        (b"  \n\n\t \r\n", REASON_EMPTY),  # TC-RDR-061
        (b"Date: 2026-10-06\n\xff\xfe\xfa bad bytes", REASON_ENCODING),  # TC-RDR-062
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00", REASON_ENCODING),  # TC-RDR-065
    ],
    ids=["empty", "whitespace", "bad-utf8", "binary"],
)
def test_malformed_files_are_skipped(tmp_path, content, reason):
    write(tmp_path, "bad.md", content)
    notes, skipped = read_notes(tmp_path)
    assert notes == []
    assert skipped[0].reason == reason


def test_utf8_bom_is_read(tmp_path):  # TC-RDR-063
    write(tmp_path, "a.md", "﻿" + VALID)
    notes, _ = read_notes(tmp_path)
    assert notes[0].meeting_date == date(2026, 10, 6)
    assert not notes[0].text.startswith("﻿")


def test_utf16_with_bom_is_read(tmp_path):  # TC-RDR-064 (QA-8)
    write(tmp_path, "a.md", VALID.encode("utf-16"))
    notes, _ = read_notes(tmp_path)
    assert notes[0].attendees[0] == "Priya Shah"


def test_permission_denied_is_skipped(tmp_path, monkeypatch):  # TC-RDR-066
    write(tmp_path, "locked.md", VALID)
    write(tmp_path, "ok.md", VALID)
    real_read_bytes = Path.read_bytes

    def read_bytes(self):
        if self.name == "locked.md":
            raise PermissionError(13, "Permission denied")
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    notes, skipped = read_notes(tmp_path)
    assert [n.file_name for n in notes] == ["ok.md"]
    assert skipped[0].reason == REASON_PERMISSION


def test_file_deleted_during_run(tmp_path, monkeypatch):  # TC-RDR-067
    write(tmp_path, "gone.md", VALID)

    def read_bytes(self):
        raise FileNotFoundError(2, "No such file")

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    assert "no longer exists" in read_notes(tmp_path)[1][0].reason


def test_unexpected_error_is_contained(tmp_path, monkeypatch):  # NFR-01
    write(tmp_path, "a.md", VALID)
    write(tmp_path, "b.md", VALID)
    real_parse = reader.parse_note

    def parse(file_name, text):
        if file_name == "a.md":
            raise RuntimeError("boom")
        return real_parse(file_name, text)

    monkeypatch.setattr(reader, "parse_note", parse)
    notes, skipped = read_notes(tmp_path)
    assert [n.file_name for n in notes] == ["b.md"]
    assert skipped[0].reason == "unexpected error: boom"


@pytest.mark.edge("E8")
def test_bad_files_do_not_stop_good_ones(tmp_path):  # TC-RDR-068
    for name in ("good1.md", "good2.md", "good3.md"):
        write(tmp_path, name, VALID)
    write(tmp_path, "empty.md", "")
    write(tmp_path, "nodate.md", note_with_header("Attendees: Priya Shah"))
    write(tmp_path, "encoding.md", b"\xff\xfa\xfb")
    notes, skipped = read_notes(tmp_path)
    assert len(notes) == 3
    assert {(s.file_name, s.reason) for s in skipped} == {
        ("empty.md", REASON_EMPTY),
        ("nodate.md", REASON_NO_DATE),
        ("encoding.md", REASON_ENCODING),
    }


def test_all_files_malformed(tmp_path):  # TC-RDR-069
    for name in ("a.md", "b.md", "c.md"):
        write(tmp_path, name, "")
    notes, skipped = read_notes(tmp_path)
    assert (len(notes), len(skipped)) == (0, 3)


def test_header_only_note_is_read(tmp_path):  # TC-RDR-070
    write(tmp_path, "a.md", "Date: 2026-10-06\nAttendees: Priya Shah\n")
    notes, skipped = read_notes(tmp_path)
    assert len(notes) == 1
    assert skipped == []


# ---------------------------------------------------------------- content handling


def test_no_title():  # TC-RDR-081
    assert parse_note("a.md", "Date: 2026-10-06\n").title is None


def test_level_two_heading_is_not_a_title():
    assert parse_note("a.md", "## Notes\nDate: 2026-10-06\n").title is None


@pytest.mark.parametrize("newline", ["\r\n", "\n", "\r"])
def test_line_endings(tmp_path, newline):  # TC-RDR-082, TC-RDR-083
    write(tmp_path, "a.md", VALID.replace("\n", newline))
    note = read_notes(tmp_path)[0][0]
    assert note.attendees == ["Priya Shah", "Rahul Mehta", "Anita Rao"]
    assert note.title == "Weekly Sales Sync"


@pytest.mark.edge("E9")
def test_very_long_note(tmp_path):  # TC-RDR-084
    body = "\n".join(f"Discussion line {i} with some text." for i in range(10_000))
    write(tmp_path, "long.md", VALID + body)
    notes, _ = read_notes(tmp_path)
    assert len(notes[0].text.splitlines()) > 10_000


@pytest.mark.edge("E9")
def test_messy_markdown(tmp_path):  # TC-RDR-085
    messy = VALID + "\n| a | b |\n|---|---|\n```\ncode: here\n```\n[link](http://x) 🚀\n"
    write(tmp_path, "messy.md", messy)
    assert len(read_notes(tmp_path)[0]) == 1


# ---------------------------------------------------------------- non-functional


@pytest.mark.perf
def test_fifty_notes_are_fast(tmp_path):  # TC-RDR-090
    body = VALID + "\n".join(f"Discussion line {i}" for i in range(100))
    for i in range(50):
        write(tmp_path, f"note-{i:02}.md", body)
    start = time.perf_counter()
    notes, _ = read_notes(tmp_path)
    assert len(notes) == 50
    assert time.perf_counter() - start < 1.0


@pytest.mark.fuzz
def test_random_files_never_crash(tmp_path):  # TC-RDR-092
    rng = random.Random(1234)
    for i in range(100):
        write(tmp_path, f"f{i:03}.md", rng.randbytes(rng.randint(0, 400)))
    notes, skipped = read_notes(tmp_path)
    assert len(notes) + len(skipped) == 100


def test_notes_are_not_modified(tmp_path):  # TC-RDR-093
    path = write(tmp_path, "a.md", VALID)
    before = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
    read_notes(tmp_path)
    assert (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) == before
