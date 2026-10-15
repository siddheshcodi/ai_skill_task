# actiontrack

A command-line tool that reads markdown meeting notes, collects the action
items in them, tracks their status, and prepares follow-up emails as **Gmail
drafts**. It never sends email.

> **Status: milestone 4 of 9.** The CLI, note reader, item extractor and owner/date resolvers are in
> place. The commands parse and validate their input but report
> "not available yet" until their modules land (see [Roadmap](#roadmap)).

## Install

Requires Python 3.10 or newer.

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install .
actiontrack --help
```

## Commands

| Command | What it does |
|---|---|
| `actiontrack ingest <folder>` | Read every `.md` note in the folder and save its action items. Safe to run again. |
| `actiontrack list [--owner NAME] [--status open\|done\|overdue] [--due-before YYYY-MM-DD]` | Show items; filters can be combined. Overdue items are marked. |
| `actiontrack done <id>` | Mark an item as done. |
| `actiontrack followup <owner> [--dry-run]` | Prepare a reminder email as a Gmail draft (or print it with `--dry-run`). |

Options for every command: `--store PATH` (default `./actiontrack.json`) and
`--debug` (show full error details).

Exit codes: `0` success · `1` failure · `2` wrong usage · `130` cancelled.

## Meeting note format

```markdown
# Weekly Sales Sync
Date: 2026-10-06
Attendees: Priya Shah, Rahul Mehta, Anita Rao

## Action items
- [ ] Priya to send the revised quote by Friday
- [x] Anita to book the demo room
```

## Email addresses

Copy `people.yaml.example` to `people.yaml` and fill in each person's
address. `people.yaml` is git-ignored.

## Development

```bash
pip install -e ".[dev]"
pytest                     # all tests
pytest --cov               # with coverage
ruff check . && ruff format --check .
```

Project documents:

| File | Content |
|---|---|
| `actiontrack-requirements.md` | Requirements |
| `plan.md` | Architecture and delivery plan |
| `decisions.md` | Answers to all open questions |
| `modules/<module>/spec.md` | Module specification |
| `modules/<module>/plan.md` | Module implementation plan |
| `modules/<module>/test_cases.md` | Module test cases |

Code layout:

```
actiontrack/
  cli.py       M1  commands, validation, exit codes
  models.py        shared data types
  errors.py        error types -> exit codes
  reader.py    M2  find notes, read date and attendees
  extractor.py M3  find checkbox items, split owner / task / due
  owners.py    M4  match owner phrase to an attendee
  dates.py     M5  due phrase -> calendar date (relative to meeting)
tests/
  unit/            per-module tests
  safety/          never-send checks (NFR-02)
  fixtures/        sample notes
```

## Roadmap

| # | Milestone | Status |
|---|---|---|
| 1 | Explore sample notes | Done with assumed formats (no samples provided) |
| 2 | Project setup + CLI skeleton | Done |
| 3 | Note reader + item extractor | Done |
| 4 | Owner + date resolvers | **Done** |
| 5 | Dedupe + storage → `ingest` | Next |
| 6 | `list` and `done` | |
| 7 | `followup` | |
| 8 | Reporting + full test pass | |
| 9 | README + demo | |
