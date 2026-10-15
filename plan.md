# actiontrack — Solution Plan (Overview)

| Item | Detail |
|---|---|
| Project | actiontrack (command-line tool) |
| Document | Solution architecture and delivery plan |
| Inputs | `actiontrack-requirements.md` v1.1, `modules/*/spec.md`, `modules/*/test_cases.md` |
| Module plans | `modules/m01-cli/plan.md` … `modules/m10-error-reporting/plan.md` |
| Status | Draft for review |

---

## 1. Goals that drive the design

| Goal | Source | Design response |
|---|---|---|
| Never crash because of one bad file | NFR-01 | Each file is processed in its own error boundary; problems become "skipped" records (M2, M10) |
| Never send email | NFR-02 | The code has no send path; drafts go through one `DraftCreator` interface with only `create_draft`; a static test fails the build if send code appears (M9) |
| Safe to re-run | FR-ING-08, E10 | Stable IDs and `next_id` counter (M7); duplicate detection checks existing stored items (M6) |
| Every part testable alone | NFR-05, NFR-06 | Pure functions for parsing and resolving; dates and "today" passed in as arguments; no global state |
| Works on Windows, macOS and Linux | NFR-07 | Standard-library Python, `pathlib`, UTF-8 everywhere, one dependency (PyYAML), CI on all three OSes |
| Fast enough | NFR-03 | In-memory processing, one store write per command; target ≤ 5 s for 50 notes |

## 2. Architecture

The design has three layers. Dependencies only point downward.

```
┌──────────────────────────────────────────────────────────────┐
│  Interface layer       M1 cli.py  (argparse, exit codes)     │
├──────────────────────────────────────────────────────────────┤
│  Service layer         ingest.py (pipeline)  query.py (M8)   │
│                        followup.py (M9)      report.py (M10) │
├──────────────────────────────────────────────────────────────┤
│  Domain layer (pure)   reader.py (M2)  extractor.py (M3)     │
│                        owners.py (M4)  dates.py (M5)         │
│                        dedupe.py (M6)  models.py (shared)    │
├──────────────────────────────────────────────────────────────┤
│  Infrastructure        store.py (M7, JSON file)              │
│                        drafts.py (M9, DraftCreator adapters) │
│                        people.py (M9, people.yaml)           │
└──────────────────────────────────────────────────────────────┘
```

### Ingest data flow

```
folder ─▶ M2 read_notes ─▶ [Note…] + [SkippedFile…]
                │ sort notes by (meeting_date, file_name)
                ▼
        for each note (error boundary):
            M3 extract_items ─▶ [RawItem…]
            for each RawItem:
                M4 resolve_owner(owner_phrase, note.attendees)
                M5 resolve_due_date(due_phrase, note.meeting_date)
                ─▶ ResolvedItem
            M6 dedupe_into(store, resolved_items)  ─▶ stats
        M7 store.save()   (one atomic write)
        M10 format_report(report) ─▶ stdout
```

Notes are processed **oldest meeting first**. The newest meeting is then processed last, so its due date and done status win (M6 rules E1/E2) without extra bookkeeping.

## 3. Technology choices

| Concern | Choice | Why |
|---|---|---|
| Language | Python ≥ 3.10 | Suggested by requirements; `X \| None` type hints; available on all OSes |
| CLI | `argparse` (stdlib) | No dependency; built-in `--help`; exit code 2 for usage errors |
| Store | JSON file `actiontrack.json` | Small data (hundreds of items); human-readable; easy to test; atomic writes with `os.replace` |
| Similarity | `difflib.SequenceMatcher` | Stdlib, good enough for an 85% rule on short texts |
| People list | `people.yaml` via PyYAML | Requirement Q3 working assumption; the only third-party runtime dependency |
| Colour | Plain ANSI codes, off when not a TTY or `NO_COLOR` is set | No dependency; the `OVERDUE` text label always shows, so meaning never depends on colour |
| Tests | `pytest`, `pytest-cov`, golden files, `freezegun` optional (prefer passing `today`) | Standard |
| Quality | `ruff` (lint and format), `mypy` (optional) | Fast, one tool |
| CI | GitHub Actions matrix: ubuntu, windows, macos × Python 3.10, 3.12 | NFR-07 proof |
| Packaging | `pyproject.toml` with `[project.scripts] actiontrack = "actiontrack.cli:main"` | One-command install: `pip install .` |

## 4. Project structure

Two files are added to the structure suggested in the requirements (§9): `models.py` and `ingest.py`. `drafts.py` and `people.py` are split out of `followup.py`.

```
actiontrack/
├── actiontrack/
│   ├── __init__.py
│   ├── cli.py         # M1  commands, arguments, exit codes
│   ├── ingest.py      # M1  ingest pipeline (calls M2–M7, M10)      [added]
│   ├── models.py      # shared dataclasses: Note, RawItem, Item … [added]
│   ├── reader.py      # M2
│   ├── extractor.py   # M3
│   ├── owners.py      # M4
│   ├── dates.py       # M5
│   ├── dedupe.py      # M6
│   ├── store.py       # M7
│   ├── query.py       # M8
│   ├── followup.py    # M9  collect + compose
│   ├── drafts.py      # M9  DraftCreator adapters (create only)    [split]
│   ├── people.py      # M9  people.yaml loader                     [split]
│   ├── errors.py      # shared exception types → exit codes        [added]
│   └── report.py      # M10
├── tests/
│   ├── fixtures/      # one folder per scenario (reader/, dedupe/, mix/ …)
│   ├── golden/        # expected CLI outputs
│   ├── unit/test_<module>.py
│   ├── integration/test_ingest.py, test_cli.py
│   └── safety/test_no_send.py
├── people.yaml.example
├── README.md
├── pyproject.toml
└── .github/workflows/ci.yml
```

## 5. Shared contracts (`models.py`)

```python
@dataclass(frozen=True)
class Note:            file_name: str; title: str | None; meeting_date: date; attendees: list[str]; text: str
@dataclass(frozen=True)
class SkippedFile:     file_name: str; reason: str
@dataclass(frozen=True)
class RawItem:         raw_text: str; owner_phrase: str | None; task: str; due_phrase: str | None; status: str; line_number: int
@dataclass(frozen=True)
class OwnerResult:     owner: str; candidates: list[str]; not_in_attendees: bool
@dataclass
class ResolvedItem:    raw: RawItem; owner: OwnerResult; due_date: date | None; note: Note
@dataclass
class Item:            id: int | None; owner: str; owner_candidates: list[str]; task: str; raw_text: str
                       due_date: date | None; due_phrase: str | None; status: str; source_files: list[str]
                       meeting_date: date; meeting_title: str | None; last_seen_meeting_date: date
                       not_in_attendees: bool; created_at: datetime | None; updated_at: datetime | None
```

Constants: `UNASSIGNED = "unassigned"`, `AMBIGUOUS = "ambiguous"`, `STATUS_OPEN = "open"`, `STATUS_DONE = "done"`.

## 6. Cross-cutting rules

| Topic | Rule |
|---|---|
| Errors | Domain code raises typed errors from `errors.py` (`UserInputError`, `NotFoundError`, `StoreError`, `DraftError`). Only `cli.py` turns them into messages and exit codes. No stack traces unless `--debug`. |
| Exit codes | `0` success · `1` runtime failure · `2` usage error |
| Time | `today` and `now` are parameters with defaults (`date.today()`) at the CLI edge only. Domain code never reads the clock. |
| Encoding | Read notes as `utf-8-sig`; write the store as UTF-8; reconfigure stdout to UTF-8 on Windows. |
| Paths | `pathlib.Path` only; store the file name relative to the ingest folder in `source_files`. |
| Determinism | Sort files and notes; dedupe picks the best match on a tie by lowest ID. |
| Logging | `logging` at WARNING by default; `--debug` sets DEBUG and shows tracebacks. |

## 7. Delivery plan

| # | Milestone (req §12) | Modules | Est. (dev-days) | Exit criterion |
|---|---|---|---|---|
| 1 | Explore sample notes | M2/M3 input | 0.5 | Formats and malformed patterns written into `tests/fixtures/README.md`; QA-5 closed |
| 2 | Setup + CLI skeleton | M1, `models.py`, `errors.py`, CI | 1.0 | `actiontrack --help` works; CI green on 3 OSes |
| 3 | Reader + Extractor | M2, M3 | 1.75 | Items printed from one note; TC-RDR, TC-EXT P1 pass |
| 4 | Owner + Date resolvers | M4, M5 | 1.5 | TC-OWN, TC-DAT P1 pass |
| 5 | Dedupe + Storage + ingest pipeline | M6, M7, `ingest.py` | 2.0 | `ingest` on full folder; re-run adds nothing |
| 6 | `list` and `done` | M8 | 0.75 | TC-QRY P1 pass |
| 7 | `followup` | M9 | 1.25 | Draft visible in Gmail; nothing sent; TC-FUP-120 green |
| 8 | Reporting + full test pass | M10 | 0.75 | Summary golden test; all E1–E11 tests pass |
| 9 | README + demo | — | 0.5 | Someone else installs and runs it from README |
| | **Total** | | **≈ 10 dev-days** | |

Parallel work is possible after milestone 2. M4 and M5 have no dependency on each other. M7 can start alongside M2/M3, since it depends only on `models.py`.

```
M1 skeleton ─┬─▶ M2 ─▶ M3 ─┬─▶ M4 ─┐
             │             └─▶ M5 ─┼─▶ M6 ─▶ ingest ─▶ M10
             └─▶ M7 ───────────────┘          │
                                M7 ─▶ M8 ─▶ M9┘
```

## 8. Test strategy

| Level | Scope | Tooling | Where |
|---|---|---|---|
| Unit | M2–M9 pure functions (≈ 80% of the 514 cases) | pytest parametrize | `tests/unit/` |
| Integration | `ingest` pipeline on fixture folders, store round-trips | pytest + `tmp_path` | `tests/integration/` |
| CLI / system | Subprocess runs, exit codes, golden output | pytest + `subprocess` | `tests/integration/test_cli.py` |
| Safety | No-send static scan, MCP spy | pytest | `tests/safety/` |
| Non-functional | Performance (50 notes ≤ 5 s), fuzz, OS matrix | pytest marks `@perf`, `@fuzz`; CI matrix | CI |
| Manual | Real Gmail draft (TC-FUP-081/082) | Test Gmail account | Release checklist |

Quality gates: all P1 tests pass, line coverage ≥ 90% on domain modules, CI green on all OSes, safety test green.

## 9. Key decisions

All open questions (Q1–Q6, QA-1 … QA-43) were **accepted with the recommended defaults on 2026-10-15**. The full list is in [`decisions.md`](decisions.md). Every ❓QA tag in the module test cases resolves to the answer recorded there.

| # | Decision | Status | Linked |
|---|---|---|---|
| D1 | JSON store, not SQLite | Accepted | QA-32 |
| D2 | argparse, not click | Accepted | — |
| D3 | Draft creation behind `DraftCreator`. Default = **hand-off** (CLI writes the draft payload; the Claude session's Gmail connector calls `create_draft`). Direct MCP client is an optional adapter. | Accepted | Q2 |
| D4 | DD/MM/YYYY for slash dates | Accepted | QA-23 |
| D5 | "by <weekday>" = strictly after the meeting date | Accepted | Q6 |
| D6 | Ingest never changes `done` back to `open` | Accepted | QA-29 |
| D7 | Newest meeting with no due date keeps the old date | Accepted | QA-28 |
| D8 | `--due-before` is strictly before | Accepted | QA-35 |
| D9 | Top-level folder only, `.md` case-insensitive | Accepted | QA-3, QA-4 |

## 10. Top risks

| Risk | Impact | Mitigation |
|---|---|---|
| Real notes differ from assumed format (Q1) | Parser misses items or dates | Milestone 1 first; patterns kept in one table per module; fixtures from real samples |
| 85% similarity merges different tasks (QA-26) | Data loss (two tasks become one) | Extra guard: differing proper nouns or numbers block a merge; threshold is a constant; merges are listed in debug output |
| The CLI cannot reach the Gmail MCP connector directly (Q2) | `followup` cannot create drafts | Hand-off adapter as default; `--dry-run` always works |
| Windows console encoding | Crashes on non-ASCII names | `sys.stdout.reconfigure(encoding="utf-8")`; CI on Windows |
| Store corruption | Loss of all tracked items | Atomic write; never overwrite a store that can't be parsed; optional `.bak` on save |
