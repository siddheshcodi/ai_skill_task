"""`followup` through the CLI (FR-FUP-*, Acceptance #7)."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from actiontrack import cli
from actiontrack.errors import EXIT_FAILURE, EXIT_OK, EXIT_USAGE

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def workspace(tmp_path, monkeypatch, capsys):
    """Three-meeting store (today 2026-10-21: quote and demo room overdue)."""
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 10, 21))
    monkeypatch.delenv("ACTIONTRACK_SENDER", raising=False)
    notes = shutil.copytree(FIXTURES / "dedupe", tmp_path / "notes")
    (tmp_path / "people.yaml").write_text(
        "sender: Team Lead\n"
        "Priya Shah: priya.shah@example.com\n"
        "Rahul Mehta: rahul.mehta@example.com\n"
        "Anita Rao: anita.rao@example.com\n",
        encoding="utf-8",
    )
    store = tmp_path / "actiontrack.json"
    assert cli.main(["--store", str(store), "ingest", str(notes)]) == EXIT_OK
    capsys.readouterr()
    return tmp_path


def followup(workspace: Path, capsys, *args: str) -> tuple[int, str, str]:
    code = cli.main(
        [
            "--store",
            str(workspace / "actiontrack.json"),
            "followup",
            *args,
            "--people",
            str(workspace / "people.yaml"),
            "--outbox",
            str(workspace / "outbox"),
        ]
    )
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def drafts(workspace: Path) -> list[dict]:
    outbox = workspace / "outbox"
    if not outbox.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(outbox.glob("*.json"))]


def test_followup_writes_one_draft(workspace, capsys):  # Acceptance #7, FR-FUP-01..03
    code, out, _ = followup(workspace, capsys, "priya")
    assert code == EXIT_OK
    (draft,) = drafts(workspace)
    assert draft["action"] == "create_draft"
    assert draft["to"] == "priya.shah@example.com"
    assert draft["subject"] == "Follow-up: your open action items (1)"
    assert (
        "Overdue\n  • Send the revised quote (due 2026-10-20, from Weekly Sales Sync)"
        in (draft["body"])
    )
    assert "nothing is sent" in out


def test_overdue_listed_before_open(workspace, capsys):
    followup(workspace, capsys, "Anita Rao")
    assert "Overdue\n  • Book the demo room (due 2026-10-15" in drafts(workspace)[0]["body"]


def test_rahul_gets_open_items_only(workspace, capsys):  # CRM is done
    followup(workspace, capsys, "rahul")
    body = drafts(workspace)[0]["body"]
    assert "Update the CRM" not in body
    assert "Call Acme Corp" in body and "Call Beta Ltd" in body


def test_dry_run_creates_no_file(workspace, capsys):  # FR-FUP-07
    code, out, _ = followup(workspace, capsys, "priya", "--dry-run")
    assert code == EXIT_OK
    assert out.startswith("To: priya.shah@example.com")
    assert drafts(workspace) == []


def test_owner_without_email(workspace, capsys):  # FR-FUP-08, E7 owner
    code, _, err = followup(workspace, capsys, "Vikram")
    assert code == EXIT_FAILURE
    assert "No email address for Vikram" in err
    assert drafts(workspace) == []


def test_unassigned_refused(workspace, capsys):  # Q5
    code, _, err = followup(workspace, capsys, "unassigned")
    assert code == EXIT_FAILURE
    assert "no follow-up email" in err


def test_no_open_items(workspace, capsys, tmp_path):  # FR-FUP-06
    store = str(workspace / "actiontrack.json")
    for item_id in ("1",):
        cli.main(["--store", store, "done", item_id])
    capsys.readouterr()
    code, out, _ = followup(workspace, capsys, "priya")
    assert code == EXIT_OK
    assert "no open action items" in out
    assert drafts(workspace) == []


def test_followup_does_not_change_store(workspace, capsys):  # TC-FUP-086
    store = workspace / "actiontrack.json"
    before = store.read_bytes()
    followup(workspace, capsys, "priya")
    assert store.read_bytes() == before


def test_there_is_no_send_option(workspace, capsys):  # TC-FUP-123, NFR-02
    code, _, err = followup(workspace, capsys, "priya", "--send")
    assert code == EXIT_USAGE
    assert "--send" in err
    assert drafts(workspace) == []
