# M10 — Error Handling and Reporting

| Item | Detail |
|---|---|
| Module | M10 |
| Source file | `actiontrack/report.py` |
| Used by | M1 (`ingest`) |
| Input from | M2 (skipped files), M4 (owner flags), M6 (counts) |
| Milestone | 8 — Reporting + tests |
| Source | Requirements §5 M10, FR-ING-07, FR-ING-09, E7, E8, NFR-01, Acceptance #1 |

## 1. Purpose

Make problems visible without crashing: collect counts and problems during `ingest`, and print a clear summary at the end.

## 2. Summary format

```
Ingest complete
  Files read:         31
  Files skipped:       3
  New items:          42
  Duplicates merged:  11
  Unassigned items:    4
  Ambiguous owners:    2
  Owners not in attendees: 1

Skipped files:
  - notes/meeting_17.md: no meeting date found
  - notes/meeting_22.md: file is empty
  - notes/meeting_29.md: cannot read file (encoding error)

Owners not in attendee list:
  - notes/meeting_05.md: "Vikram" (item 18)
```

- The "Owners not in attendees" line and section are additions required by E7 ("flag it in the summary"). Omit sections that are empty.
- Numbers right-aligned.

## 3. Counters

| Counter | Source | Meaning |
|---|---|---|
| `files_read` | M2 | `.md` files successfully read |
| `files_skipped` | M2 | Malformed files |
| `new_items` | M6 | Items added to the store in this run |
| `duplicates_merged` | M6 | Incoming items merged into an existing item |
| `unassigned` | M4 | Items in this run with owner `unassigned` |
| `ambiguous` | M4 | Items in this run with owner `ambiguous` |
| `not_in_attendees` | M4 | Items whose owner was not in the attendee list |

> **Open decision:** whether "Unassigned items" / "Ambiguous owners" count items from **this run** or **the whole store**. Working assumption: this run's extracted items (de-duplicated).

## 4. Error-handling rules

- Unexpected errors in one file must **never** stop processing of other files (NFR-01). Wrap per-file processing in a try/except that records `unexpected error: <message>` as a skip reason.
- Problems in a single **item** (e.g. unparseable line) are logged and skipped; the rest of the file is still processed.
- Fatal errors (store unreadable, folder missing) stop the command with a clear message and non-zero exit — they are not per-file problems.
- No stack traces for users; optional `--verbose` / `--debug` flag may show them.

## 5. Suggested interface

```python
@dataclass
class IngestReport:
    files_read: int = 0
    skipped: list[SkippedFile] = field(default_factory=list)
    new_items: int = 0
    duplicates_merged: int = 0
    unassigned: int = 0
    ambiguous: int = 0
    not_in_attendees: list[tuple[str, str, int]] = field(default_factory=list)

def format_report(report: IngestReport) -> str: ...
```

## 6. Edge cases

| # | Case | Behaviour |
|---|---|---|
| E7 | Owner not in attendee list | Listed in summary |
| E8 | Malformed note | Skipped and listed with reason; other files processed |

## 7. Tests

- Summary text for a known fixture folder (golden output).
- A file that raises an unexpected exception → reported, other files still ingested.
- Empty sections are omitted.

## 8. Acceptance criteria

- [ ] `ingest` processes the full sample folder without crashing and lists all skipped files with reasons (Acceptance #1).
- [ ] Summary printed at the end of every ingest (FR-ING-09).
