# M1 — CLI: Test Cases

| Item | Detail |
|---|---|
| Module | M1 CLI (`actiontrack/cli.py`) |
| Covers | §5 M1, §6 (command entry), FR-LST-07, NFR-01, NFR-04, NFR-07 |
| Test levels | Unit (argument parsing, dispatch with mocks), CLI/system (subprocess) |
| Default test data | Store file in a temp folder; `notes/` fixture folder from `tests/fixtures/` |

**Type key:** F = Functional (positive) · N = Negative · E = Edge case · NF = Non-functional
**Priority key:** P1 = must pass for release · P2 = important · P3 = nice to have
**❓QA-n** = depends on an open QA question (see end of file)

---

## 1. Help and usage

| ID | Scenario | Type | Pri | Steps / Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-CLI-001 | Top-level help | F | P1 | `actiontrack --help` | Usage shows all 4 sub-commands (`ingest`, `list`, `done`, `followup`) with one-line descriptions; exit `0` | M1, NFR-04 |
| TC-CLI-002 | `ingest` help | F | P1 | `actiontrack ingest --help` | Shows `<folder>` argument and description; exit `0` | NFR-04 |
| TC-CLI-003 | `list` help | F | P1 | `actiontrack list --help` | Shows `--owner`, `--status open\|done\|overdue`, `--due-before YYYY-MM-DD`; exit `0` | NFR-04 |
| TC-CLI-004 | `done` help | F | P1 | `actiontrack done --help` | Shows `<id>` argument; exit `0` | NFR-04 |
| TC-CLI-005 | `followup` help | F | P1 | `actiontrack followup --help` | Shows `<owner>` and `--dry-run`; text states drafts are never sent; exit `0` | NFR-04, NFR-02 |
| TC-CLI-006 | Short help flag | E | P3 | `actiontrack -h` | Same output as `--help` | NFR-04 |
| TC-CLI-007 | No command given | N | P2 | `actiontrack` | Usage/help printed; non-zero exit (usage error) | M1 |

## 2. Command dispatch (positive)

| ID | Scenario | Type | Pri | Steps / Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-CLI-010 | `ingest` dispatches to pipeline | F | P1 | `actiontrack ingest notes/` (modules mocked) | Reader → Extractor → Owner → Date → Dedupe → Store → Report called in order; exit `0` | FR-ING-01..09 |
| TC-CLI-011 | `list` dispatches to query | F | P1 | `actiontrack list` | Query module called with no filters; table printed; exit `0` | FR-LST-01 |
| TC-CLI-012 | `list` passes all filters | F | P1 | `actiontrack list --owner priya --status open --due-before 2026-10-20` | Query called with all three filters | FR-LST-05 |
| TC-CLI-013 | `done` dispatches | F | P1 | `actiontrack done 3` | `mark_done(3)` called; exit `0` | FR-DON-01 |
| TC-CLI-014 | `followup` dispatches | F | P1 | `actiontrack followup "Priya Shah"` | Follow-up module called with owner `Priya Shah`, `dry_run=False` | FR-FUP-01 |
| TC-CLI-015 | `followup --dry-run` flag passed | F | P1 | `actiontrack followup Rahul --dry-run` | Follow-up called with `dry_run=True` | FR-FUP-07 |
| TC-CLI-016 | Option order independence | E | P3 | `actiontrack list --status open --owner rahul` vs reversed | Same result | M1 |
| TC-CLI-017 | Owner with spaces (quoted) | E | P2 | `actiontrack followup "Priya Shah"` / `list --owner "Priya Shah"` | Full name passed as one value | FR-LST-02 |

## 3. Input validation (negative)

| ID | Scenario | Type | Pri | Steps / Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-CLI-020 | Unknown command | N | P1 | `actiontrack lst` | Error names the bad command and suggests `--help`; non-zero exit; no stack trace | M1, NFR-04 |
| TC-CLI-021 | Command wrong case | N | P3 | `actiontrack INGEST notes/` | Treated as unknown command (commands are lowercase) | M1 |
| TC-CLI-022 | Unknown option | N | P2 | `actiontrack list --colour red` | Error: unrecognised option; non-zero exit | M1 |
| TC-CLI-023 | `ingest` without folder | N | P1 | `actiontrack ingest` | Error: folder is required; non-zero exit | M1 |
| TC-CLI-024 | `ingest` folder does not exist | N | P1 | `actiontrack ingest no_such_dir/` | `Error: folder 'no_such_dir/' not found.`; non-zero exit; store untouched | M1, NFR-04 |
| TC-CLI-025 | `ingest` path is a file | N | P2 | `actiontrack ingest notes/a.md` | Error: path is not a folder; non-zero exit | M1 |
| TC-CLI-026 | `--status` invalid value | N | P1 | `actiontrack list --status late` | Error lists valid values `open, done, overdue`; non-zero exit | FR-LST-07 |
| TC-CLI-027 | `--status` empty | N | P2 | `actiontrack list --status ""` | Same error as TC-CLI-026 | FR-LST-07 |
| TC-CLI-028 | `--status` upper case | E | P3 | `actiontrack list --status OPEN` | ❓QA-1 Accepted as `open` (recommended) **or** clear error — must not crash | FR-LST-07 |
| TC-CLI-029 | `--due-before` wrong format | N | P1 | `--due-before 12-10-2026`, `--due-before 2026/10/12`, `--due-before tomorrow` | Error: `Use YYYY-MM-DD, e.g. 2026-10-12`; non-zero exit | FR-LST-07 |
| TC-CLI-030 | `--due-before` impossible date | N | P1 | `--due-before 2026-02-30`, `2026-13-01`, `2026-00-10` | Clear invalid-date error; non-zero exit | FR-LST-07 |
| TC-CLI-031 | `--due-before` valid leap day | E | P3 | `--due-before 2028-02-29` | Accepted | FR-LST-04 |
| TC-CLI-032 | `--due-before` non-leap Feb 29 | N | P3 | `--due-before 2027-02-29` | Invalid-date error | FR-LST-07 |
| TC-CLI-033 | `--due-before` value missing | N | P2 | `actiontrack list --due-before` | Error: option needs a value | M1 |
| TC-CLI-034 | `done` without ID | N | P1 | `actiontrack done` | Error: ID is required; non-zero exit | M1 |
| TC-CLI-035 | `done` non-numeric ID | N | P1 | `actiontrack done abc` | `Error: ID must be a whole number…`; non-zero exit | M1 |
| TC-CLI-036 | `done` zero / negative / decimal | N | P2 | `done 0`, `done -1`, `done 1.5` | Clear error; non-zero exit; store untouched | M1 |
| TC-CLI-037 | `done` very large ID | E | P3 | `done 99999999999999999999` | `Item … not found` (or invalid ID) — no overflow/crash | FR-DON-02 |
| TC-CLI-038 | `done` multiple IDs | N | P3 | `done 1 2` | ❓QA-2 Error (only one ID supported per requirements) | FR-DON-01 |
| TC-CLI-039 | `followup` without owner | N | P1 | `actiontrack followup` | Error: owner is required; non-zero exit | M1 |
| TC-CLI-040 | `followup` empty / blank owner | N | P2 | `actiontrack followup ""`, `followup "   "` | Clear error; no draft | FR-FUP-05 |

## 4. Exit codes and error presentation

| ID | Scenario | Type | Pri | Steps / Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-CLI-050 | Success exit code | F | P1 | Any successful command | Exit `0` | M1 |
| TC-CLI-051 | Usage error exit code | N | P1 | TC-CLI-020/026/035 | Non-zero exit (2 for argument errors) | M1 |
| TC-CLI-052 | Runtime failure exit code | N | P1 | `done 999` (missing ID) | Non-zero exit (1) | FR-DON-02 |
| TC-CLI-053 | Ingest with skipped files is success | E | P1 | Folder with 2 good + 1 malformed note | Summary shows skipped file; exit `0` | NFR-01, FR-ING-07 |
| TC-CLI-054 | "Already done" is success | E | P1 | `done 3` twice | 2nd run: "already done" message; exit `0` | FR-DON-03 |
| TC-CLI-055 | "No open items" is success | E | P1 | `followup` for owner with only done items | Message, no draft; exit `0` | FR-FUP-06 |
| TC-CLI-056 | No stack traces shown | NF | P1 | Run every negative case above | Output never contains `Traceback`; message explains problem **and** fix | NFR-04 |
| TC-CLI-057 | Errors go to stderr | NF | P3 | Any error case | Error text on stderr, normal output on stdout | NFR-04 |

## 5. Store file handling at CLI level

| ID | Scenario | Type | Pri | Steps / Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-CLI-060 | First run, no store | F | P1 | `actiontrack list` with no store file | `No items found.`; exit `0`; no crash | M7 |
| TC-CLI-061 | Custom store path (if supported) | F | P3 | `actiontrack --store tmp/at.json list` | Uses that file | M1 §3 |
| TC-CLI-062 | Store path with spaces / unicode | E | P3 | Store in `C:\My Notes\Action track\` | Works | NFR-07 |
| TC-CLI-063 | Store file read-only | N | P2 | Make store read-only, run `done 1` | Clear "cannot write store" error; non-zero exit; file not corrupted | NFR-01, NFR-04 |
| TC-CLI-064 | Interrupt during ingest | E | P2 | Ctrl+C mid-ingest | Store is either unchanged or fully written (never half-written) | M7 atomic write |

## 6. Non-functional

| ID | Scenario | Type | Pri | Steps / Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-CLI-070 | Install with one command — Windows | NF | P1 | Fresh venv, `pip install .` | `actiontrack --help` works | NFR-07 |
| TC-CLI-071 | Install with one command — macOS | NF | P1 | Same as above | Works | NFR-07 |
| TC-CLI-072 | Install with one command — Linux | NF | P1 | Same as above | Works | NFR-07 |
| TC-CLI-073 | Windows path separators | NF | P2 | `actiontrack ingest notes\` and `notes/` on Windows | Both work | NFR-07 |
| TC-CLI-074 | Help response time | NF | P3 | `actiontrack --help` | Returns in < 1 s | NFR-03 |
| TC-CLI-075 | Non-ASCII terminal output | NF | P3 | Item owner `José Núñez`, run `list` on Windows console | Prints without `UnicodeEncodeError` | NFR-07 |

---

## Questions affecting this module

- **QA-1:** Should `--status` be case-insensitive (`OPEN` = `open`)?
- **QA-2:** Should `done` accept more than one ID (`done 1 2 3`)? Requirements say one ID.
