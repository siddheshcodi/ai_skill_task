# M1 — CLI (Command-Line Interface)

| Item | Detail |
|---|---|
| Module | M1 |
| Source file | `actiontrack/cli.py` |
| Depends on | M2–M10 (orchestrates all of them) |
| Milestone | 2 — Project setup + CLI skeleton |
| Source | Requirements §5 M1, §6, NFR-04, NFR-07 |

## 1. Purpose

The entry point. It reads the command the user typed, validates the arguments and calls the right modules. It holds no business logic of its own.

## 2. Responsibilities

- Provide a program named `actiontrack` with four sub-commands: `ingest`, `list`, `done`, `followup`.
- Provide `--help` for the program and for every sub-command.
- Validate user input (dates, status values, IDs) **before** calling other modules.
- Print clear error messages that say what went wrong and how to fix it.
- Return exit code `0` on success and non-zero on failure.

## 3. Commands

| Command | Arguments / options | Calls | Requirements |
|---|---|---|---|
| `actiontrack ingest <folder>` | `folder` (required, must exist and be a directory) | M2 → M3 → M4 → M5 → M6 → M7 → M10 | FR-ING-01..09 |
| `actiontrack list [filters]` | `--owner <name>`, `--status open\|done\|overdue`, `--due-before <YYYY-MM-DD>` | M7, M8 | FR-LST-01..07 |
| `actiontrack done <id>` | `id` (required, positive integer) | M7, M8 | FR-DON-01..03 |
| `actiontrack followup <owner>` | `owner` (required), `--dry-run` | M7, M8, M9 | FR-FUP-01..08 |

Global option (suggested): `--store <path>` to choose the store file (default `actiontrack.json` / `actiontrack.db` in the current folder).

## 4. Input validation

| Input | Rule | Error example |
|---|---|---|
| Unknown command | Reject | `Error: unknown command 'lst'. Run 'actiontrack --help' to see commands.` |
| `<folder>` | Must exist and be a directory | `Error: folder 'notes/' not found.` |
| `--status` | One of `open`, `done`, `overdue` | `Error: invalid status 'late'. Use open, done or overdue.` |
| `--due-before` | Valid `YYYY-MM-DD` date | `Error: invalid date '12-10-2026'. Use YYYY-MM-DD, e.g. 2026-10-12.` |
| `<id>` | Positive integer | `Error: ID must be a whole number, e.g. 'actiontrack done 12'.` |

## 5. Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (including "item already done" and "no open items, no draft created") |
| `1` | Runtime failure (e.g. ID not found, owner email unknown, Gmail draft failed) |
| `2` | Usage error (bad arguments; default for `argparse`/`click`) |

> Ingest with some skipped files is still a success (`0`); skipped files are reported, not fatal (NFR-01).

## 6. Design notes

- Suggested tools: Python with `argparse` or `click`.
- Keep each command handler thin: parse → validate → call module → print → return exit code.
- Catch expected exceptions from modules and convert them to friendly messages; do not show stack traces to users.
- Install via one command (e.g. `pip install .` with a `console_scripts` entry point in `pyproject.toml`) — NFR-07.

## 7. Tests

- `actiontrack --help` and `<command> --help` print usage and exit `0`.
- Unknown command → non-zero exit + helpful message.
- Invalid `--status` / `--due-before` → clear error (FR-LST-07).
- Non-integer `done` ID → clear error.
- Each command dispatches to the correct module (mock the modules).

## 8. Acceptance criteria

- [ ] `actiontrack --help` works (Milestone 2).
- [ ] All four sub-commands exist and have `--help`.
- [ ] Wrong input never produces a stack trace.
- [ ] Exit codes follow §5.
