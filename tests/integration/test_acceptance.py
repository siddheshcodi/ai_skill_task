"""Acceptance and cross-module tests (milestone 8).

Covers the M10 report cases on fixture MIX (modules/m10-error-reporting/
test_cases.md), exit codes, error-message quality, determinism,
portability and the remaining follow-up checks.
"""

from __future__ import annotations

import io
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import pytest

from actiontrack import cli, ingest
from actiontrack.dates import resolve_due_date
from actiontrack.drafts import HandoffDraftCreator
from actiontrack.errors import EXIT_FAILURE, EXIT_OK, EXIT_USAGE
from actiontrack.followup import run_followup
from actiontrack.models import Email, Item
from actiontrack.reader import parse_note, read_notes
from actiontrack.store import Store

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDEN = Path(__file__).parents[1] / "golden"


@pytest.fixture
def ws(tmp_path, monkeypatch, capsys):
    """Workspace: tmp dir as cwd with ``mix/`` (+ generated bad-encoding note)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 10, 15))
    monkeypatch.delenv("ACTIONTRACK_SENDER", raising=False)
    shutil.copytree(FIXTURES / "mix", tmp_path / "mix")
    (tmp_path / "mix" / "meeting_29.md").write_bytes(b"Date: 2026-10-06\n\xff\xfe\xfa\n")

    class Workspace:
        root = tmp_path
        store = tmp_path / "actiontrack.json"

        def run(self, *argv: str) -> tuple[int, str, str]:
            code = cli.main(["--store", str(self.store), *argv])
            out = capsys.readouterr()
            return code, out.out, out.err

    return Workspace()


def ingest_mix(ws) -> str:
    code, out, _ = ws.run("ingest", "mix")
    assert code == EXIT_OK
    return out


# ---------------------------------------------------------------- M10 summary on MIX


def test_summary_matches_golden(ws):  # TC-REP-001..009, 011, 012, TC-OWN-082, 083, TC-CLI-053
    expected = (GOLDEN / "ingest_mix.txt").read_text(encoding="utf-8")
    assert ingest_mix(ws) == expected


def test_counts_are_consistent(ws):  # TC-REP-010
    report = ingest.run_ingest(Path("mix"), Store(ws.store))
    md_files = len(list(Path("mix").glob("*.md")))
    lines = sum(len(ingest.extract_items(note)) for note in read_notes(Path("mix"))[0])
    assert report.files_read + len(report.skipped) == md_files == 6
    assert report.new_items + report.duplicates_merged == lines == 6


def test_second_run(ws):  # TC-REP-020
    ingest_mix(ws)
    lines = ingest_mix(ws).splitlines()
    assert lines[3:8] == [
        "  New items:                   0",
        "  Duplicates merged:           6",
        "  Unassigned items:            1",
        "  Ambiguous owners:            1",
        "  Owners not in attendees:     1",
    ]


def test_no_problems_omits_sections(ws):  # TC-REP-021
    for name in ("meeting_17.md", "meeting_22.md", "meeting_29.md", "good-3.md"):
        (ws.root / "mix" / name).unlink()
    out = ingest_mix(ws)
    assert "Skipped files:" not in out
    assert "Owners not in attendee list:" not in out


def test_empty_folder(ws):  # TC-REP-022
    (ws.root / "empty").mkdir()
    code, out, _ = ws.run("ingest", "empty")
    assert code == EXIT_OK
    assert all(line.endswith(" 0") for line in out.splitlines()[1:8])


def test_all_files_skipped(ws):  # TC-REP-023
    bad = ws.root / "bad"
    bad.mkdir()
    for name in ("a.md", "b.md", "c.md"):
        (bad / name).write_text("", encoding="utf-8")
    code, out, _ = ws.run("ingest", "bad")
    assert code == EXIT_OK
    assert "  Files read:                  0" in out
    assert "  Files skipped:               3" in out


def test_notes_without_action_items(ws):  # TC-REP-024
    quiet = ws.root / "quiet"
    quiet.mkdir()
    for name in ("a.md", "b.md"):
        (quiet / name).write_text("Date: 2026-10-06\nJust discussion.\n", encoding="utf-8")
    out = ws.run("ingest", "quiet")[1]
    assert "  Files read:                  2" in out
    assert "  New items:                   0" in out


def test_long_skip_list(ws):  # TC-REP-025
    many = ws.root / "many"
    many.mkdir()
    for i in range(100):
        (many / f"{i:03}.md").write_text("", encoding="utf-8")
    out = ws.run("ingest", "many")[1]
    assert sum(line.startswith("  - many/") for line in out.splitlines()) == 100


def test_unexpected_error_reason(ws, monkeypatch):  # TC-REP-026
    real = ingest.extract_items

    def extract(note):
        if note.file_name == "good-2.md":
            raise ValueError("parser exploded")
        return real(note)

    monkeypatch.setattr(ingest, "extract_items", extract)
    out = ingest_mix(ws)
    assert "  - mix/good-2.md: unexpected error: parser exploded" in out


def test_store_saved_once(ws, monkeypatch):  # TC-REP-044
    calls = []
    real_save = Store.save
    monkeypatch.setattr(Store, "save", lambda self: (calls.append(1), real_save(self)))
    ingest_mix(ws)
    assert calls == [1]


# ---------------------------------------------------------------- unassigned / ambiguous


def test_unassigned_and_ambiguous_visible_in_list(ws):  # TC-OWN-080, TC-OWN-081
    ingest_mix(ws)
    out = ws.run("list")[1]
    assert "unassigned" in out and "Book a room for the offsite" in out
    assert "ambiguous: Priya Shah / Priya Kumar" in out


def test_initial_resolves_to_full_name(ws):  # TC-OWN-021 end to end
    ingest_mix(ws)
    out = ws.run("list", "--owner", "Priya Shah")[1]
    assert "Priya Shah" in out and "send the pricing deck" in out


@pytest.mark.parametrize("group", ["unassigned", "ambiguous"])
def test_no_followup_for_groups(ws, group):  # TC-OWN-084
    ingest_mix(ws)
    code, _, err = ws.run("followup", group, "--outbox", "outbox")
    assert code == EXIT_FAILURE
    assert "no follow-up email" in err
    assert not (ws.root / "outbox").exists()


# ---------------------------------------------------------------- exit codes


def test_exit_codes(ws):  # TC-CLI-050..052, TC-CLI-054, TC-CLI-055
    ingest_mix(ws)
    assert ws.run("list")[0] == EXIT_OK
    assert ws.run("list", "--status", "late")[0] == EXIT_USAGE
    assert ws.run("done", "99")[0] == EXIT_FAILURE
    assert ws.run("done", "1")[0] == EXIT_OK
    assert ws.run("done", "1")[0] == EXIT_OK  # already done
    assert ws.run("done", "2")[0] == EXIT_OK
    assert ws.run("followup", "Priya Shah", "--outbox", "outbox")[0] == EXIT_OK  # nothing open


def test_error_messages_say_how_to_fix(ws):  # TC-REP-047, NFR-04
    ingest_mix(ws)
    (ws.root / "people.yaml").write_text("Rahul Mehta: rahul@example.com\n", encoding="utf-8")
    failing = [
        ("list", "--status", "late"),
        ("list", "--due-before", "15/10/2026"),
        ("ingest", "missing-folder"),
        ("done", "99"),
        ("done", "abc"),
        ("followup", "Bob"),
        ("followup", "Vikram", "--people", "people.yaml"),
        ("followup", "Rahul", "--people", "nowhere.yaml"),
    ]
    hints = ("Use ", "Run ", "Check ", "Add ", "Copy ", "Fix ", "Try ", "Give ")
    for argv in failing:
        code, _, err = ws.run(*argv)
        assert code != EXIT_OK, argv
        assert "Traceback" not in err, argv
        assert any(hint in err for hint in hints), (argv, err)


# ---------------------------------------------------------------- store location & portability


def test_store_path_with_spaces_and_unicode(ws):  # TC-CLI-062
    store = ws.root / "My Notes ü" / "action track.json"
    assert cli.main(["--store", str(store), "ingest", "mix"]) == EXIT_OK
    assert len(Store(store).load_all()) == 5


def test_read_only_store_via_cli(ws, monkeypatch):  # TC-CLI-063
    ingest_mix(ws)
    before = ws.store.read_bytes()

    def denied(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", denied)
    code, _, err = ws.run("done", "1")
    assert code == EXIT_FAILURE
    assert "read-only" in err
    assert ws.store.read_bytes() == before


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path separators")
def test_windows_backslash_folder(ws):  # TC-CLI-073
    assert ws.run("ingest", "mix\\")[0] == EXIT_OK


def test_store_file_is_portable(ws):  # TC-STO-081
    ingest_mix(ws)
    raw = ws.store.read_bytes()
    assert b"\r\n" not in raw
    data = json.loads(raw.decode("utf-8"))
    for item in data["items"]:
        assert all("/" not in f and "\\" not in f for f in item["source_files"])


def test_store_is_separate_from_notes(ws):  # TC-STO-082, TC-RDR-093
    before = {p.name: p.read_bytes() for p in (ws.root / "mix").iterdir()}
    ingest_mix(ws)
    ingest_mix(ws)
    after = {p.name: p.read_bytes() for p in (ws.root / "mix").iterdir()}
    assert after == before
    assert sorted(p.name for p in ws.root.glob("actiontrack.json*")) == [
        "actiontrack.json",
        "actiontrack.json.bak",
    ]


# ---------------------------------------------------------------- determinism & re-ingest edits


def snapshot(store_path: Path) -> list[dict]:
    items = json.loads(store_path.read_text(encoding="utf-8"))["items"]
    return [{k: v for k, v in i.items() if k not in ("created_at", "updated_at")} for i in items]


def test_deterministic_regardless_of_file_creation_order(tmp_path):  # TC-DUP-091
    names = sorted(p.name for p in (FIXTURES / "dedupe").glob("*.md"))
    for folder, order in (("a", names), ("b", names[::-1])):
        (tmp_path / folder).mkdir()
        for name in order:
            shutil.copy(FIXTURES / "dedupe" / name, tmp_path / folder / name)
        ingest.run_ingest(tmp_path / folder, Store(tmp_path / f"{folder}.json"))
    assert snapshot(tmp_path / "a.json") == snapshot(tmp_path / "b.json")


def test_note_edited_slightly_merges(ws):  # TC-DUP-074
    ingest_mix(ws)
    note = ws.root / "mix" / "good-1.md"
    note.write_text(
        note.read_text(encoding="utf-8").replace("pricing deck", "pricing decks"),
        encoding="utf-8",
    )
    assert "  New items:                   0" in ingest_mix(ws)


def test_note_edited_heavily_adds_item(ws):  # TC-DUP-075
    ingest_mix(ws)
    note = ws.root / "mix" / "good-1.md"
    note.write_text(
        note.read_text(encoding="utf-8").replace(
            "send the pricing deck", "organise the customer workshop"
        ),
        encoding="utf-8",
    )
    assert "  New items:                   1" in ingest_mix(ws)
    tasks = [i.task for i in Store(ws.store).load_all()]
    assert "send the pricing deck" in tasks and "organise the customer workshop" in tasks


# ---------------------------------------------------------------- dates and reader extras


def test_due_dates_do_not_depend_on_timezone(monkeypatch):  # TC-DAT-091
    results = []
    for zone in ("Asia/Kolkata", "America/Los_Angeles", "UTC"):
        monkeypatch.setenv("TZ", zone)
        if hasattr(time, "tzset"):
            time.tzset()
        results.append(
            [resolve_due_date(p, date(2026, 10, 6)) for p in ("by Friday", "EOM", "Oct 12")]
        )
    assert results[0] == results[1] == results[2]


def test_attendees_as_bullet_list_not_supported(tmp_path):  # TC-RDR-046 (QA-5 default)
    note = parse_note("a.md", "Date: 2026-10-06\nAttendees:\n- Priya Shah\n- Rahul Mehta\n")
    assert note.attendees == []  # read normally; owners then flagged, never guessed


def test_other_separators_kept_as_one_name(tmp_path):  # TC-RDR-047 (QA-5 default)
    note = parse_note("a.md", "Date: 2026-10-06\nAttendees: Priya Shah; Rahul Mehta\n")
    assert note.attendees == ["Priya Shah; Rahul Mehta"]


def test_front_matter_header(tmp_path):  # TC-RDR-086
    note = parse_note("a.md", "---\ndate: 2026-10-06\nattendees: Priya Shah\n---\n# Sync\n")
    assert (note.meeting_date, note.attendees, note.title) == (
        date(2026, 10, 6),
        ["Priya Shah"],
        "Sync",
    )


@pytest.mark.perf
def test_large_folder(tmp_path):  # TC-RDR-091
    for i in range(500):
        (tmp_path / f"{i:03}.md").write_text(
            f"Date: 2026-10-06\nAttendees: Priya Shah\n- [ ] Priya to do task {i}\n",
            encoding="utf-8",
        )
    start = time.perf_counter()
    notes, _ = read_notes(tmp_path)
    assert len(notes) == 500
    assert time.perf_counter() - start < 5.0


# ---------------------------------------------------------------- query extras


def test_today_is_the_system_date():  # TC-QRY-007
    assert cli._today() == date.today()


def test_repeated_option_last_wins(ws):  # TC-QRY-086 (QA-36)
    ingest_mix(ws)
    out = ws.run("list", "--status", "done", "--status", "open")[1]
    assert "5 items" in out


# ---------------------------------------------------------------- follow-up extras


def open_item(item_id: int, task: str, **changes) -> Item:
    fields = dict(
        id=item_id,
        owner="Rahul Mehta",
        task=task,
        raw_text=task,
        status="open",
        meeting_date=date(2026, 10, 6),
        last_seen_meeting_date=date(2026, 10, 6),
        source_files=["a.md"],
        meeting_title="Sync",
    )
    fields.update(changes)
    return Item(**fields)


def people(tmp_path: Path) -> Path:
    path = tmp_path / "people.yaml"
    path.write_text("Rahul Mehta: rahul@example.com\n", encoding="utf-8")
    return path


class SpyCreator:
    """Records every attribute the follow-up code touches on the creator."""

    def __init__(self) -> None:
        self.touched: list[str] = []
        self.emails: list[Email] = []

    def __getattribute__(self, name: str):
        if not name.startswith("_") and name not in ("touched", "emails"):
            object.__getattribute__(self, "touched").append(name)
        return object.__getattribute__(self, name)

    def create_draft(self, email: Email) -> str:
        self.emails.append(email)
        return "spy"


def test_only_create_draft_is_called(tmp_path):  # TC-FUP-121, NFR-02
    spy = SpyCreator()
    run_followup(
        "Rahul",
        [open_item(1, "call the client")],
        people(tmp_path),
        lambda: spy,
        dry_run=False,
        today=date(2026, 10, 15),
        out=io.StringIO(),
    )
    assert spy.touched == ["create_draft"]


def test_many_items(tmp_path):  # TC-FUP-007
    spy = SpyCreator()
    items = [open_item(i, f"task number {i}") for i in range(1, 31)]
    run_followup(
        "Rahul",
        items,
        people(tmp_path),
        lambda: spy,
        dry_run=False,
        today=date(2026, 10, 15),
        out=io.StringIO(),
    )
    (email,) = spy.emails
    assert email.subject.endswith("(30)")
    assert email.body.count("  • ") == 30


def test_item_from_several_meetings_listed_once(tmp_path):  # TC-FUP-054
    store = Store(tmp_path / "s.json")
    ingest.run_ingest(FIXTURES / "dedupe", store)
    spy = SpyCreator()
    path = tmp_path / "people.yaml"
    path.write_text("Priya Shah: priya@example.com\n", encoding="utf-8")
    run_followup(
        "Priya Shah",
        store.load_all(),
        path,
        lambda: spy,
        dry_run=False,
        today=date(2026, 10, 15),
        out=io.StringIO(),
    )
    assert spy.emails[0].body.count("Send the revised quote") == 1


def test_transports_produce_the_same_email(tmp_path):  # TC-FUP-141
    spy = SpyCreator()
    items = [open_item(1, "call the client", due_date=date(2026, 10, 9))]
    for make in (lambda: spy, lambda: HandoffDraftCreator(tmp_path / "outbox")):
        run_followup(
            "Rahul",
            items,
            people(tmp_path),
            make,
            dry_run=False,
            today=date(2026, 10, 15),
            out=io.StringIO(),
        )
    (draft_file,) = (tmp_path / "outbox").glob("*.json")
    handoff = json.loads(draft_file.read_text(encoding="utf-8"))
    email = spy.emails[0]
    assert (handoff["to"], handoff["subject"], handoff["body"]) == (
        email.to,
        email.subject,
        email.body,
    )


@pytest.mark.perf
def test_dry_run_is_fast(tmp_path):  # TC-FUP-140
    rng = random.Random(3)
    items = [
        open_item(i, f"task {i}", owner=rng.choice(["Rahul Mehta", "Anita Rao"]))
        for i in range(1, 1001)
    ]
    start = time.perf_counter()
    run_followup(
        "Rahul",
        items,
        people(tmp_path),
        lambda: SpyCreator(),
        dry_run=True,
        today=date(2026, 10, 15),
        out=io.StringIO(),
    )
    assert time.perf_counter() - start < 1.0


# ---------------------------------------------------------------- real process


def run_process(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONIOENCODING"}
    return subprocess.run(
        [sys.executable, "-m", "actiontrack", *args],
        capture_output=True,
        cwd=cwd,
        env=env,
        check=False,
    )


@pytest.mark.perf
def test_help_is_quick(tmp_path):  # TC-CLI-074 (1 s target, x2 headroom for CI)
    start = time.perf_counter()
    assert run_process("--help", cwd=tmp_path).returncode == EXIT_OK
    assert time.perf_counter() - start < 2.0


def test_non_ascii_output_in_a_real_process(tmp_path):  # TC-CLI-075
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "a.md").write_text(
        "Date: 2026-10-06\nAttendees: José Núñez\n- [ ] José to revisar el contrato 🚀\n",
        encoding="utf-8",
    )
    assert run_process("ingest", "notes", cwd=tmp_path).returncode == EXIT_OK
    result = run_process("list", cwd=tmp_path)
    assert result.returncode == EXIT_OK
    assert "José Núñez" in result.stdout.decode("utf-8")
