"""`list` and `done` through the CLI (FR-LST-*, FR-DON-*, Acceptance #4-#6)."""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from actiontrack import cli
from actiontrack.errors import EXIT_FAILURE, EXIT_OK, EXIT_USAGE

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    """Ingest the three-meeting fixture, then run CLI commands on that store."""
    # quote due 10-20 and demo room due 10-15 are overdue; CRM (10-12) is done
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 10, 21))
    store = tmp_path / "actiontrack.json"
    notes = shutil.copytree(FIXTURES / "dedupe", tmp_path / "notes")
    assert cli.main(["--store", str(store), "ingest", str(notes)]) == EXIT_OK
    capsys.readouterr()

    def invoke(*argv: str) -> tuple[int, str, str]:
        code = cli.main(["--store", str(store), *argv])
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return invoke


def rows(out: str) -> dict[int, str]:
    """Table rows by ID (an ID is followed by the 2-space column gap; the footer is not)."""
    return {int(m[1]): line for line in out.splitlines() if (m := re.match(r"(\d+)\s{2}", line))}


def test_list_all(run):  # FR-LST-01, Acceptance #4
    code, out, _ = run("list")
    assert code == EXIT_OK
    table = rows(out)
    assert sorted(table) == [1, 2, 3, 4, 5, 6, 7]
    assert "unassigned" in table[3]  # no owner: visible (E3)
    assert "Vikram" in table[4]  # owner not in attendees: visible (E7)
    assert out.rstrip().endswith("7 items, 2 overdue")


def test_list_marks_overdue(run):  # FR-LST-03, FR-LST-06
    _, out, _ = run("list", "--status", "overdue")
    table = rows(out)
    assert list(table) == [1, 7]
    assert all("OVERDUE" in line for line in table.values())


def test_list_filters_combined(run):  # FR-LST-05, Acceptance #5
    _, out, _ = run("list", "--owner", "rahul", "--status", "open", "--due-before", "2026-12-31")
    assert list(rows(out)) == []  # Rahul's CRM item is done; Acme/Beta have no due date
    _, out, _ = run("list", "--owner", "rahul", "--status", "open")
    assert list(rows(out)) == [5, 6]


def test_list_invalid_filter(run):  # FR-LST-07
    code, _, err = run("list", "--status", "late")
    assert code == EXIT_USAGE
    assert "open, done or overdue" in err


def test_list_output_has_no_colour_when_piped(run):  # TC-QRY-030
    _, out, _ = run("list")
    assert "\033[" not in out


def test_done_then_list(run):  # FR-DON-01, Acceptance #6
    code, out, _ = run("done", "1")
    assert (code, out.strip()) == (EXIT_OK, "Item 1 marked as done: send the revised quote")
    _, out, _ = run("list", "--status", "done")
    assert list(rows(out)) == [1, 2]


def test_done_already_done(run):  # FR-DON-03
    code, out, _ = run("done", "2")
    assert code == EXIT_OK
    assert "already done" in out


def test_done_missing_id(run, tmp_path):  # FR-DON-02
    before = (tmp_path / "actiontrack.json").read_bytes()
    code, _, err = run("done", "99")
    assert code == EXIT_FAILURE
    assert "Item 99 not found" in err
    assert (tmp_path / "actiontrack.json").read_bytes() == before


def test_done_survives_reingest(run, tmp_path):  # TC-QRY-108
    run("done", "1")
    run("ingest", str(tmp_path / "notes"))
    _, out, _ = run("list", "--status", "done")
    assert 1 in rows(out)


def test_list_without_store(tmp_path, capsys):  # TC-CLI-060, TC-QRY-029
    assert cli.main(["--store", str(tmp_path / "none.json"), "list"]) == EXIT_OK
    assert capsys.readouterr().out.strip() == "No items found."


def test_done_without_store(tmp_path, capsys):  # TC-QRY-107
    assert cli.main(["--store", str(tmp_path / "none.json"), "done", "1"]) == EXIT_FAILURE
    assert not (tmp_path / "none.json").exists()
