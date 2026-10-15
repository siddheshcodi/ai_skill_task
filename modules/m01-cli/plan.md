# M1 — CLI: Implementation Plan

| Item | Detail |
|---|---|
| Files | `actiontrack/cli.py`, `actiontrack/ingest.py`, `actiontrack/errors.py`, `pyproject.toml` |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-CLI-001 … TC-CLI-075 |
| Milestone | 2 (skeleton), extended in 5–7 as commands get wired |
| Estimate | 1.0 dev-day (skeleton 0.5 + ingest pipeline 0.25 + wiring/tests 0.25) |
| Depends on | `models.py`, `errors.py`; at runtime all modules M2–M10 |

## 1. Goal

A thin, predictable entry point. M1 parses and validates arguments, calls one service function per command, and maps results and errors to messages and exit codes. It holds no business logic. That logic lives in the services (`ingest.py`, `query.py`, `followup.py`).

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Parser | `argparse` with sub-parsers | Stdlib; auto `--help`; exit `2` on usage errors (TC-CLI-051) |
| Entry point | `main(argv: list[str] \| None = None) -> int` | Directly callable in tests without subprocess |
| Global options | `--store PATH` (default `./actiontrack.json`), `--debug` | Testability (temp store) and support |
| Validation | Custom argparse `type=` functions: `iso_date`, `positive_int`, `choice_ci` | Errors come out before any service runs, with the hint text from the spec |
| Error mapping | Single `try/except` in `main()` around the dispatched command | One place for NFR-04 behaviour; no tracebacks unless `--debug` |
| Ingest pipeline | `ingest.run_ingest(folder, store, today) -> IngestReport` in `ingest.py` | Keeps `cli.py` thin; pipeline can be tested without the CLI |
| Console encoding | `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at startup | TC-CLI-075 on Windows |

### Error → exit code mapping (`errors.py`)

| Exception | Raised by | Exit | Example message |
|---|---|---|---|
| argparse error | parser | 2 | `Error: invalid status 'late'. Use open, done or overdue.` |
| `UserInputError` | services | 2 | `Error: folder 'nope/' not found.` |
| `NotFoundError` | M8, M9 | 1 | `Item 99 not found.` |
| `AmbiguousOwnerError` | M9 | 1 | `'priya' matches more than one person: …` |
| `StoreError` | M7 | 1 | `Store file is corrupt: … Fix or move it, then retry.` |
| `ConfigError` | M9 people.yaml | 1 | `No email address for Rahul Mehta in people.yaml.` |
| `DraftError` | M9 | 1 | `Could not create Gmail draft: … Try --dry-run.` |
| `KeyboardInterrupt` | — | 130 | `Cancelled. No changes were saved.` |
| any other `Exception` | — | 1 | `Unexpected error: … (run with --debug for details)` |

## 3. Components

```python
# cli.py
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: list[str] | None = None) -> int: ...
def _cmd_ingest(args) -> int     # store = Store(args.store); report = run_ingest(...); print(format_report(report))
def _cmd_list(args) -> int       # items = filter_items(...); print(format_table(...))
def _cmd_done(args) -> int       # result = mark_done(store, args.id)
def _cmd_followup(args) -> int   # run_followup(..., creator=make_creator(args), dry_run=args.dry_run)

# ingest.py
def run_ingest(folder: Path, store: Store, today: date) -> IngestReport: ...
```

`run_ingest` steps:

1. `notes, skipped = read_notes(folder)` (M2).
2. Sort notes by `(meeting_date, file_name)`.
3. For each note, inside `try/except Exception`: extract (M3) → resolve owner (M4) and date (M5) → `dedupe_into(store, resolved, stats)` (M6). On an exception, add `SkippedFile(name, "unexpected error: …")`.
4. `store.save()` once (M7, atomic).
5. Return the `IngestReport` (M10).

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | `pyproject.toml` (name, Python ≥ 3.10, PyYAML, script entry, pytest/ruff config) | 1 h | TC-CLI-070..072 |
| 2 | `errors.py` exception hierarchy | 0.5 h | — |
| 3 | `build_parser()` with 4 sub-commands, help text, global options | 1.5 h | TC-CLI-001..007 |
| 4 | Validators `iso_date`, `positive_int`, `status_choice` | 1 h | TC-CLI-026..038 |
| 5 | `main()` dispatch + error mapping + UTF-8 stdout | 1 h | TC-CLI-020..057 |
| 6 | `ingest.py` pipeline with per-file error boundary | 2 h | TC-CLI-010, TC-REP-040 |
| 7 | Wire `list`, `done`, `followup` as M8/M9 land | 1 h | TC-CLI-011..017 |
| 8 | Subprocess smoke tests + golden help output | 1 h | TC-CLI-050..057 |

## 5. Test approach

- **Unit:** call `main([...])` with services monkeypatched and check the calls and return code.
- **System:** `subprocess.run([sys.executable, "-m", "actiontrack", ...])` for exit codes, stderr and the absence of tracebacks.
- **CI matrix:** run TC-CLI-070..073 on Windows, macOS and Linux.

## 6. Risks

| Risk | Mitigation |
|---|---|
| argparse error messages are not friendly enough | Override `ArgumentParser.error()` to add the "Run --help" hint |
| Ctrl+C mid-ingest leaves a half-written store | Store saves only once at the end, atomically (M7) |

## 7. Open questions

- QA-1 (case-insensitive `--status`). Default: accept any case.
- QA-2 (multiple IDs for `done`). Default: one ID only.

## 8. Definition of done

- [ ] All P1 TC-CLI cases pass on 3 OSes.
- [ ] `actiontrack --help` and every `<cmd> --help` are reviewed for wording.
- [ ] No traceback appears in any negative test.
