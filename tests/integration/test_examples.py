"""The README quick start, checked against examples/ so the docs stay true."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from actiontrack import cli
from actiontrack.errors import EXIT_OK

EXAMPLES = Path(__file__).parents[2] / "examples"
README = Path(__file__).parents[2] / "README.md"


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    monkeypatch.chdir(tmp_path / "examples")
    monkeypatch.setattr(cli, "_today", lambda: date(2026, 10, 15))  # README date
    monkeypatch.delenv("ACTIONTRACK_SENDER", raising=False)

    def invoke(*argv: str) -> str:
        assert cli.main(list(argv)) == EXIT_OK
        return capsys.readouterr().out

    return invoke


def readme_block(after: str) -> str:
    """The output lines shown in the README right after the ``$ <after>`` line."""
    text = README.read_text(encoding="utf-8")
    start = text.index(f"$ {after}\n") + len(after) + 3
    return text[start : text.index("```", start)]


def test_quick_start_ingest(run):
    assert run("ingest", "notes") == readme_block("actiontrack ingest notes")


def test_quick_start_list(run):
    run("ingest", "notes")
    assert run("list") == readme_block("actiontrack list")


def test_quick_start_followup_dry_run(run):
    run("ingest", "notes")
    command = 'actiontrack followup "Priya Kumar" --people people.example.yaml --dry-run'
    out = run("followup", "Priya Kumar", "--people", "people.example.yaml", "--dry-run")
    assert readme_block(command).startswith(out)


def test_quick_start_done(run):
    run("ingest", "notes")
    assert run("done", "1") == readme_block("actiontrack done 1")
