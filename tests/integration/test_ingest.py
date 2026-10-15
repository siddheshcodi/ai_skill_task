"""Ingest pipeline integration tests (M2-M7, M10 working together).

Fixture ``tests/fixtures/dedupe`` holds three weekly meetings (N1 10-06,
N2 10-13, N3 10-20) designed to exercise every merge rule.
"""

from __future__ import annotations

import random
import shutil
import time
from datetime import date
from pathlib import Path

import pytest

from actiontrack import cli, ingest
from actiontrack.errors import EXIT_OK
from actiontrack.ingest import run_ingest
from actiontrack.report import format_report
from actiontrack.store import Store

FIXTURES = Path(__file__).parents[1] / "fixtures"
N1, N2, N3 = "2026-10-06-sales.md", "2026-10-13-sales.md", "2026-10-20-sales.md"


@pytest.fixture
def notes(tmp_path) -> Path:
    folder = tmp_path / "notes"
    shutil.copytree(FIXTURES / "dedupe", folder)
    return folder


@pytest.fixture
def store_path(tmp_path) -> Path:
    return tmp_path / "actiontrack.json"


def ingest_folder(folder: Path, store_path: Path):
    return run_ingest(folder, Store(store_path))


def items_by_task(store_path: Path) -> dict:
    return {item.task: item for item in Store(store_path).load_all()}


# ---------------------------------------------------------------- end-to-end merge rules


def test_three_meetings(notes, store_path):  # TC-DUP-050, TC-DUP-051, TC-DUP-073, TC-DAT-016
    report = ingest_folder(notes, store_path)
    items = items_by_task(store_path)

    assert [i.id for i in Store(store_path).load_all()] == [1, 2, 3, 4, 5, 6, 7]

    quote = items["send the revised quote"]  # E1: newest due date, all sources
    assert quote.owner == "Priya Shah"
    assert (quote.due_date, quote.due_phrase) == (date(2026, 10, 20), "by 2026-10-20")
    assert quote.source_files == [N1, N2, N3]
    assert quote.meeting_date == date(2026, 10, 6)

    crm = items["update the CRM"]  # E2: done in N2, stays done after "[ ]" in N3
    assert crm.status == "done"
    assert crm.due_date == date(2026, 10, 12)  # N2/N3 gave no date: kept

    deck = items["Share the slide deck with the client"]  # E3
    assert (deck.owner, deck.source_files) == ("unassigned", [N1, N2])

    contract = items["review the contract"]  # E7
    assert (contract.owner, contract.not_in_attendees) == ("Vikram", True)

    assert {"call Acme Corp", "call Beta Ltd"} <= items.keys()  # guard: two items

    demo = items["book the demo room"]
    assert demo.due_date == date(2026, 10, 15)  # Thursday after Tue 10-13
    assert demo.source_files == [N2, N3]

    assert (report.files_read, report.new_items, report.duplicates_merged) == (3, 7, 6)
    assert report.unassigned == {deck.id}
    assert list(report.flagged_owners) == [contract.id]


@pytest.mark.edge("E10")
def test_reingest_is_byte_identical(notes, store_path):  # TC-DUP-070/071, FR-ING-08
    ingest_folder(notes, store_path)
    first = store_path.read_bytes()
    for _ in range(3):
        report = ingest_folder(notes, store_path)
    assert store_path.read_bytes() == first
    assert report.new_items == 0
    assert report.duplicates_merged == 13  # every line (5 + 5 + 3) matched a stored item


@pytest.mark.edge("E10")
def test_new_note_keeps_old_ids(notes, store_path):  # TC-DUP-072, TC-STO-025/026
    (notes / N3).unlink()
    ingest_folder(notes, store_path)
    before = {i.task: i.id for i in Store(store_path).load_all()}
    shutil.copy(FIXTURES / "dedupe" / N3, notes / N3)
    (notes / "2026-10-27-sales.md").write_text(
        "Date: 2026-10-27\nAttendees: Priya Shah\n- [ ] Priya to draft the renewal plan\n",
        encoding="utf-8",
    )
    report = ingest_folder(notes, store_path)
    after = {i.task: i.id for i in Store(store_path).load_all()}
    assert {task: after[task] for task in before} == before
    assert after["draft the renewal plan"] == max(before.values()) + 1
    assert report.new_items == 1


def test_older_note_added_later_does_not_override(notes, store_path):  # TC-DUP-053
    (notes / N1).unlink()
    ingest_folder(notes, store_path)
    shutil.copy(FIXTURES / "dedupe" / N1, notes / N1)
    ingest_folder(notes, store_path)
    quote = items_by_task(store_path)["send the revised quote"]
    assert quote.due_date == date(2026, 10, 20)
    assert quote.source_files == [N2, N3, N1]


def test_manual_done_survives_reingest(notes, store_path):  # TC-DUP-059, TC-QRY-108
    ingest_folder(notes, store_path)
    store = Store(store_path)
    quote = next(i for i in store.load_all() if i.task == "send the revised quote")
    quote.status = "done"
    store.update(quote)
    store.save()
    ingest_folder(notes, store_path)
    assert items_by_task(store_path)["send the revised quote"].status == "done"


def test_deleted_note_keeps_items(notes, store_path):  # TC-DUP-076 (QA-31)
    ingest_folder(notes, store_path)
    (notes / N1).unlink()
    ingest_folder(notes, store_path)
    assert "call Acme Corp" in items_by_task(store_path)


def test_renamed_note_adds_source(notes, store_path):  # TC-DUP-077 (QA-31)
    ingest_folder(notes, store_path)
    (notes / N1).rename(notes / "sales-oct6.md")
    report = ingest_folder(notes, store_path)
    assert report.new_items == 0
    assert items_by_task(store_path)["call Acme Corp"].source_files == [N1, "sales-oct6.md"]


def test_same_notes_in_another_folder(notes, store_path, tmp_path):  # TC-DUP-078
    ingest_folder(notes, store_path)
    copy = shutil.copytree(notes, tmp_path / "copy")
    assert ingest_folder(copy, store_path).new_items == 0


# ---------------------------------------------------------------- robustness


@pytest.mark.edge("E8")
def test_malformed_notes_are_reported(notes, store_path):  # E8, FR-ING-07
    (notes / "empty.md").write_text("", encoding="utf-8")
    (notes / "readme.txt").write_text("ignored", encoding="utf-8")
    report = ingest_folder(notes, store_path)
    assert report.files_read == 3
    assert [(s.file_name, s.reason) for s in report.skipped] == [("empty.md", "file is empty")]


def test_one_failing_note_does_not_stop_others(notes, store_path, monkeypatch):  # TC-REP-040
    real = ingest.extract_items

    def extract(note):
        if note.file_name == N2:
            raise RuntimeError("boom")
        return real(note)

    monkeypatch.setattr(ingest, "extract_items", extract)
    report = ingest_folder(notes, store_path)
    assert report.files_read == 2
    assert report.skipped[0].reason == "unexpected error: boom"
    assert "call Acme Corp" in items_by_task(store_path)


def test_one_failing_item_does_not_lose_the_note(notes, store_path, monkeypatch):  # TC-REP-041
    real = ingest.resolve_owner

    def resolve(phrase, attendees):
        if phrase == "Vikram":
            raise RuntimeError("bad owner")
        return real(phrase, attendees)

    monkeypatch.setattr(ingest, "resolve_owner", resolve)
    report = ingest_folder(notes, store_path)
    assert report.files_read == 3
    assert [(s.file_name, s.line_number) for s in report.skipped_items] == [(N1, 9)]
    assert "review the contract" not in items_by_task(store_path)
    assert "call Acme Corp" in items_by_task(store_path)


@pytest.mark.fuzz
def test_random_notes_never_crash(tmp_path, store_path):  # TC-REP-063
    rng = random.Random(7)
    folder = tmp_path / "fuzz"
    folder.mkdir()
    words = ["- [ ]", "- [x]", "Date: 2026-10-06", "Attendees: Priya Shah", "by Friday", "to", "@"]
    for i in range(200):
        if i % 3 == 0:
            (folder / f"{i}.md").write_bytes(rng.randbytes(rng.randint(0, 300)))
        else:
            lines = [" ".join(rng.choices(words, k=rng.randint(1, 6))) for _ in range(20)]
            (folder / f"{i}.md").write_text("Date: 2026-10-06\n" + "\n".join(lines), "utf-8")
    report = ingest_folder(folder, store_path)
    assert report.files_read + len(report.skipped) == 200


@pytest.mark.perf
def test_fifty_notes_ingest_quickly(tmp_path, store_path):  # NFR-03, TC-REP-060..062, TC-DUP-090
    folder = tmp_path / "many"
    folder.mkdir()
    for n in range(50):
        items = [f"- [ ] Priya to finish deliverable {n * 10 + k} by Friday" for k in range(7)]
        items += [f"- [ ] Rahul will review shared document {k}" for k in range(3)]  # repeats
        body = "\n".join(f"Discussion line {i}" for i in range(90))
        (folder / f"{n:02}.md").write_text(
            f"Date: 2026-{1 + n // 28:02}-{1 + n % 28:02}\nAttendees: Priya Shah, Rahul Mehta\n"
            + body
            + "\n"
            + "\n".join(items),
            encoding="utf-8",
        )
    start = time.perf_counter()
    ingest_folder(folder, store_path)
    ingest_folder(folder, store_path)  # re-ingest with 353 stored items
    assert time.perf_counter() - start < 5.0
    assert len(Store(store_path).load_all()) == 353


# ---------------------------------------------------------------- CLI


def test_cli_ingest_prints_summary(notes, store_path, capsys):  # FR-ING-09
    assert cli.main(["--store", str(store_path), "ingest", str(notes)]) == EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith("Ingest complete")
    assert "  New items:                   7" in out.splitlines()
    assert "review the contract" not in out
    assert '"Vikram" (item 4)' in out


def test_cli_ingest_corrupt_store(notes, store_path, capsys):  # TC-REP-043
    store_path.write_text("{oops", encoding="utf-8")
    assert cli.main(["--store", str(store_path), "ingest", str(notes)]) == 1
    assert "corrupt" in capsys.readouterr().err
    assert store_path.read_text(encoding="utf-8") == "{oops"


def test_report_format(notes, store_path):  # TC-REP-011/012
    (notes / "meeting_22.md").write_text("", encoding="utf-8")
    text = format_report(ingest_folder(notes, store_path))
    assert text.splitlines()[:8] == [
        "Ingest complete",
        "  Files read:                  3",
        "  Files skipped:               1",
        "  New items:                   7",
        "  Duplicates merged:           6",
        "  Unassigned items:            1",
        "  Ambiguous owners:            0",
        "  Owners not in attendees:     1",
    ]
    assert f"  - {notes.as_posix()}/meeting_22.md: file is empty" in text
    assert f'  - {notes.as_posix()}/{N1}: "Vikram" (item 4)' in text
