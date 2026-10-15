"""M1 CLI tests (modules/m01-cli/test_cases.md)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date

import pytest

from actiontrack import cli
from actiontrack.errors import EXIT_FAILURE, EXIT_INTERRUPTED, EXIT_OK, EXIT_USAGE


@pytest.fixture
def calls(monkeypatch):
    """Replace every command handler with a recorder that returns success."""
    recorded: list[tuple[str, argparse.Namespace]] = []

    def make(name):
        def handler(args):
            recorded.append((name, args))
            return EXIT_OK

        return handler

    for name in ("ingest", "list", "done", "followup"):
        monkeypatch.setattr(cli, f"_cmd_{name}", make(name))
    return recorded


# ---------------------------------------------------------------- help


def test_top_level_help_lists_all_commands(capsys):  # TC-CLI-001
    assert cli.main(["--help"]) == EXIT_OK
    out = capsys.readouterr().out
    for command in ("ingest", "list", "done", "followup"):
        assert command in out


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("ingest", "folder"),  # TC-CLI-002
        ("list", "--due-before"),  # TC-CLI-003
        ("done", "id"),  # TC-CLI-004
        ("followup", "never sent"),  # TC-CLI-005
    ],
)
def test_command_help(capsys, command, expected):
    assert cli.main([command, "--help"]) == EXIT_OK
    assert expected in capsys.readouterr().out


def test_list_help_shows_all_filters(capsys):  # TC-CLI-003
    cli.main(["list", "--help"])
    out = capsys.readouterr().out
    for option in ("--owner", "--status", "--due-before"):
        assert option in out


def test_short_help_flag(capsys):  # TC-CLI-006
    assert cli.main(["-h"]) == EXIT_OK
    assert "followup" in capsys.readouterr().out


def test_no_command_prints_usage(capsys):  # TC-CLI-007
    assert cli.main([]) == EXIT_USAGE
    assert "usage:" in capsys.readouterr().err


def test_version(capsys):
    assert cli.main(["--version"]) == EXIT_OK
    assert "actiontrack" in capsys.readouterr().out


# ---------------------------------------------------------------- dispatch


def test_ingest_dispatch(calls, tmp_path):  # TC-CLI-010
    assert cli.main(["ingest", str(tmp_path)]) == EXIT_OK
    name, args = calls[0]
    assert name == "ingest"
    assert args.folder == tmp_path


def test_list_dispatch_without_filters(calls):  # TC-CLI-011
    assert cli.main(["list"]) == EXIT_OK
    _, args = calls[0]
    assert (args.owner, args.status, args.due_before) == (None, None, None)


def test_list_passes_all_filters(calls):  # TC-CLI-012
    cli.main(["list", "--owner", "priya", "--status", "open", "--due-before", "2026-10-20"])
    _, args = calls[0]
    assert args.owner == "priya"
    assert args.status == "open"
    assert args.due_before == date(2026, 10, 20)


def test_done_dispatch(calls):  # TC-CLI-013
    assert cli.main(["done", "3"]) == EXIT_OK
    assert calls[0][1].id == 3


def test_followup_dispatch(calls):  # TC-CLI-014, TC-CLI-017
    cli.main(["followup", "Priya Shah"])
    _, args = calls[0]
    assert args.owner == "Priya Shah"
    assert args.dry_run is False


def test_followup_dry_run(calls):  # TC-CLI-015
    cli.main(["followup", "Rahul", "--dry-run"])
    assert calls[0][1].dry_run is True


def test_option_order_does_not_matter(calls):  # TC-CLI-016
    cli.main(["list", "--status", "open", "--owner", "rahul"])
    cli.main(["list", "--owner", "rahul", "--status", "open"])
    first, second = calls[0][1], calls[1][1]
    assert (first.owner, first.status) == (second.owner, second.status)


@pytest.mark.parametrize(
    "argv",
    [
        ["--store", "custom.json", "list"],
        ["list", "--store", "custom.json"],
    ],
)
def test_store_option_before_or_after_command(calls, argv):  # TC-CLI-061
    cli.main(argv)
    assert str(cli._store_path(calls[0][1])) == "custom.json"


def test_default_store_path(calls):
    cli.main(["list"])
    assert str(cli._store_path(calls[0][1])) == cli.DEFAULT_STORE


# ---------------------------------------------------------------- validation


def _error(capsys) -> str:
    err = capsys.readouterr().err
    assert "Traceback" not in err  # TC-CLI-056, TC-REP-045
    return err


def test_unknown_command(capsys):  # TC-CLI-020
    assert cli.main(["lst"]) == EXIT_USAGE
    err = _error(capsys)
    assert "lst" in err
    assert "--help" in err


def test_command_is_case_sensitive(capsys):  # TC-CLI-021
    assert cli.main(["INGEST", "notes"]) == EXIT_USAGE


def test_unknown_option(capsys):  # TC-CLI-022
    assert cli.main(["list", "--colour", "red"]) == EXIT_USAGE
    assert "--colour" in _error(capsys)


def test_ingest_requires_folder(capsys):  # TC-CLI-023
    assert cli.main(["ingest"]) == EXIT_USAGE
    assert "folder" in _error(capsys)


def test_ingest_folder_not_found(capsys, tmp_path):  # TC-CLI-024, TC-REP-042
    missing = tmp_path / "no_such_dir"
    assert cli.main(["ingest", str(missing)]) == EXIT_USAGE
    assert "not found" in _error(capsys)


def test_ingest_path_is_a_file(capsys, tmp_path):  # TC-CLI-025
    note = tmp_path / "a.md"
    note.write_text("x", encoding="utf-8")
    assert cli.main(["ingest", str(note)]) == EXIT_USAGE
    assert "not a folder" in _error(capsys)


@pytest.mark.parametrize("value", ["late", "", "closed"])
def test_invalid_status(capsys, value):  # TC-CLI-026, TC-CLI-027, TC-QRY-063
    assert cli.main(["list", "--status", value]) == EXIT_USAGE
    assert "open, done or overdue" in _error(capsys)


@pytest.mark.parametrize(("value", "expected"), [("OPEN", "open"), ("Overdue", "overdue")])
def test_status_is_case_insensitive(calls, value, expected):  # TC-CLI-028 (QA-1)
    cli.main(["list", "--status", value])
    assert calls[0][1].status == expected


@pytest.mark.parametrize(
    "value",
    [
        "12-10-2026",  # TC-CLI-029, TC-QRY-075
        "2026/10/12",
        "tomorrow",
        "20261012",
        "2026-02-30",  # TC-CLI-030
        "2026-13-01",
        "2026-00-10",
        "2027-02-29",  # TC-CLI-032
    ],
)
def test_invalid_due_before(capsys, value):
    assert cli.main(["list", "--due-before", value]) == EXIT_USAGE
    assert "YYYY-MM-DD" in _error(capsys)


def test_due_before_leap_day(calls):  # TC-CLI-031
    cli.main(["list", "--due-before", "2028-02-29"])
    assert calls[0][1].due_before == date(2028, 2, 29)


def test_due_before_missing_value(capsys):  # TC-CLI-033
    assert cli.main(["list", "--due-before"]) == EXIT_USAGE


def test_done_requires_id(capsys):  # TC-CLI-034
    assert cli.main(["done"]) == EXIT_USAGE


@pytest.mark.parametrize("value", ["abc", "0", "1.5", " "])
def test_done_invalid_id(capsys, value):  # TC-CLI-035, TC-CLI-036
    assert cli.main(["done", value]) == EXIT_USAGE
    assert "whole number" in _error(capsys)


def test_done_negative_id(capsys):  # TC-CLI-036
    assert cli.main(["done", "--", "-1"]) == EXIT_USAGE


def test_done_very_large_id(calls):  # TC-CLI-037
    cli.main(["done", "99999999999999999999"])
    assert calls[0][1].id == 99999999999999999999


def test_done_takes_one_id(capsys):  # TC-CLI-038 (QA-2)
    assert cli.main(["done", "1", "2"]) == EXIT_USAGE


def test_followup_requires_owner(capsys):  # TC-CLI-039
    assert cli.main(["followup"]) == EXIT_USAGE


@pytest.mark.parametrize("value", ["", "   "])
def test_followup_blank_owner(capsys, value):  # TC-CLI-040
    assert cli.main(["followup", value]) == EXIT_USAGE
    assert "empty" in _error(capsys)


def test_owner_whitespace_is_collapsed(calls):  # TC-QRY-050
    cli.main(["list", "--owner", "  Priya   Shah "])
    assert calls[0][1].owner == "Priya Shah"


# ---------------------------------------------------------------- error mapping


def test_expected_error_is_reported_without_traceback(tmp_path, capsys):
    missing_store = tmp_path / "none.json"
    assert cli.main(["--store", str(missing_store), "followup", "Priya"]) == EXIT_FAILURE
    assert "No items found for 'Priya'" in _error(capsys)


def test_unexpected_error_is_reported_without_traceback(monkeypatch, capsys):
    def boom(args):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(cli, "_cmd_list", boom)
    assert cli.main(["list"]) == EXIT_FAILURE
    err = _error(capsys)
    assert "disk on fire" in err
    assert "--debug" in err


def test_debug_shows_traceback(monkeypatch, capsys):  # TC-REP-046
    def boom(args):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(cli, "_cmd_list", boom)
    assert cli.main(["--debug", "list"]) == EXIT_FAILURE
    assert "Traceback" in capsys.readouterr().err


def test_keyboard_interrupt(monkeypatch, capsys):  # TC-CLI-064
    def interrupted(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_cmd_ingest", interrupted)
    assert cli.main(["ingest", "."]) == EXIT_INTERRUPTED
    assert "No changes were saved" in capsys.readouterr().err


# ---------------------------------------------------------------- as a real process


def test_module_entry_point_help():  # TC-CLI-070..072 (smoke; CI runs on 3 OSes)
    result = subprocess.run(
        [sys.executable, "-m", "actiontrack", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == EXIT_OK
    assert "followup" in result.stdout


def test_process_usage_error_goes_to_stderr():  # TC-CLI-057
    result = subprocess.run(
        [sys.executable, "-m", "actiontrack", "lst"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == EXIT_USAGE
    assert result.stdout == ""
    assert "Error:" in result.stderr


def test_no_color_env_disables_colour(monkeypatch):  # TC-QRY-030
    monkeypatch.setenv("NO_COLOR", "1")
    assert cli._color_enabled() is False
