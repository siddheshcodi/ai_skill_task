# M10 — Error Handling and Reporting: Implementation Plan

| Item | Detail |
|---|---|
| Files | `actiontrack/report.py` (summary), error boundaries in `actiontrack/ingest.py`, exit mapping in `cli.py` (see M1 plan) |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-REP-001 … TC-REP-063 |
| Milestone | 8 (report); error boundaries are built in milestone 5 with the pipeline |
| Estimate | 0.75 dev-day |
| Depends on | M2 `SkippedFile`, M4 `OwnerResult`, M6 `DedupeStats` |
| Used by | M1 (`ingest`) |

## 1. Goal

Every ingest ends with an accurate, readable summary, and no single file or item can stop the run. This module also owns the end-to-end robustness and performance checks.

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Report object | `IngestReport` dataclass filled in by `ingest.py` as it goes | One object; easy to assert in tests |
| Counting scope | Counts are for **this run**: `unassigned`/`ambiguous`/`not_in_attendees` count distinct stored items touched in this run (new or merged) | QA-42 default; re-runs show stable numbers |
| Error boundaries | Two levels in `ingest.py`: per **file** (`try` around extract + resolve + dedupe for one note) and per **item** (`try` around resolve for one line). An item error is logged and the item skipped; a file error adds a `SkippedFile` | NFR-01; TC-REP-040/041 |
| Transactions | Store changes for one note are applied only after that note's items resolve without error | A failing note leaves no half-merged items |
| Fatal errors | Folder missing, store corrupt, store not writable → raise; no summary printed | TC-REP-042..044 |
| Formatting | Fixed label column, numbers right-aligned to width 4; sections omitted when empty; paths shown as `<folder>/<file>` | Matches the §5 M10 example (TC-REP-011/012) |
| Extra section | "Owners not in attendee list" with file, owner and item ID | E7 |
| Output stream | Summary to stdout; warnings to stderr | Scriptable |
| Debug | `--debug` logs the traceback for each skipped file/item | TC-REP-046 |

### Summary layout

```
Ingest complete
  Files read:                 31
  Files skipped:               3
  New items:                  42
  Duplicates merged:          11
  Unassigned items:            4
  Ambiguous owners:            2
  Owners not in attendees:     1

Skipped files:
  - notes/meeting_17.md: no meeting date found
  ...

Owners not in attendee list:
  - notes/meeting_05.md: "Vikram" (item 18)
```

## 3. Components

```python
@dataclass
class IngestReport:
    folder: str
    files_read: int = 0
    skipped: list[SkippedFile] = field(default_factory=list)
    new_items: int = 0
    duplicates_merged: int = 0
    unassigned: set[int] = field(default_factory=set)       # item ids
    ambiguous: set[int] = field(default_factory=set)
    not_in_attendees: list[tuple[str, str, int]] = field(default_factory=list)

def format_report(report: IngestReport) -> str: ...
```

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | `IngestReport` + filling it in `ingest.py` | 1 h | TC-REP-001..010 |
| 2 | Per-file and per-item error boundaries + per-note commit | 1.5 h | TC-REP-026, 040..041 |
| 3 | `format_report` + golden output for fixture **MIX** | 1 h | TC-REP-011..012, 021..025 |
| 4 | Fatal-error paths and messages (with M1 mapping) | 0.5 h | TC-REP-042..047 |
| 5 | Performance fixtures (30 / 50 generated notes) + `@perf` tests | 1 h | TC-REP-060..062 |
| 6 | Fuzz test (200 random notes) | 0.5 h | TC-REP-063 |
| 7 | Edge-case coverage check: a test index mapping E1–E11 to test functions | 0.5 h | NFR-06 |

## 5. Test approach

- Fixture **MIX** from `test_cases.md`, compared with `tests/golden/ingest_mix.txt`.
- Fault injection: monkeypatch `extract_items` / `resolve_owner` to raise for one specific file or line.
- Performance: a generator script builds realistic notes (≈ 100 lines, 10 items, 30% repeated tasks) into `tmp_path`. Ingest must finish in ≤ 5 s on CI runners (QA-43).
- Coverage check (NFR-06): every edge case E1–E11 has at least one test tagged `@pytest.mark.edge("E1")`, and a meta-test fails if any tag is missing.

## 6. Risks

| Risk | Mitigation |
|---|---|
| CI machines are slower than laptops, so perf tests are flaky | Perf threshold has 2× headroom on CI; the real target is measured locally and recorded in the README |
| Counts disagree between runs | Counts based on item-ID sets, not on raw lines |

## 7. Open questions

QA-42 (counting scope), QA-43 (performance target).

## 8. Definition of done

- [ ] The sample `notes/` folder ingests without crashing and lists every skipped file with a reason (Acceptance #1).
- [ ] Every edge case E1–E11 is tagged and its tests pass (Acceptance #8, NFR-06).
- [ ] Performance target met.
