# M10 — Error Handling and Reporting: Test Cases

| Item | Detail |
|---|---|
| Module | M10 Error Handling and Reporting (`actiontrack/report.py`) |
| Covers | §5 M10, FR-ING-07, FR-ING-09, E7, E8, NFR-01, NFR-04, Acceptance #1 |
| Test levels | Unit (`format_report`) + Integration (`ingest` on fixture folders, golden output) |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

Fixture folder **MIX** (used unless stated otherwise):

| File | Content |
|---|---|
| `good-1.md` | Valid, 3 items (1 unassigned) |
| `good-2.md` | Valid, 2 items (1 duplicate of `good-1`, 1 ambiguous Priya) |
| `good-3.md` | Valid, 1 item owned by `Vikram` (not an attendee) |
| `meeting_17.md` | No date |
| `meeting_22.md` | Empty |
| `meeting_29.md` | Invalid UTF-8 |
| `readme.txt` | Not markdown |

---

## 1. Summary content

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-REP-001 | Summary printed | F | P1 | `ingest MIX/` | Starts with `Ingest complete` | FR-ING-09 |
| TC-REP-002 | Files read | F | P1 | Same | `Files read: 3` (`readme.txt` not counted) | E11 |
| TC-REP-003 | Files skipped | F | P1 | Same | `Files skipped: 3` | FR-ING-07 |
| TC-REP-004 | New items | F | P1 | Same, empty store | `New items: 5` | M6 |
| TC-REP-005 | Duplicates merged | F | P1 | Same | `Duplicates merged: 1` | M6 |
| TC-REP-006 | Unassigned count | F | P1 | Same | `Unassigned items: 1` | E3 |
| TC-REP-007 | Ambiguous count | F | P1 | Same | `Ambiguous owners: 1` | E6 |
| TC-REP-008 | Skipped list with reasons | F | P1 | Same | `- MIX/meeting_17.md: no meeting date found`, `- …meeting_22.md: file is empty`, `- …meeting_29.md: cannot read file (encoding error)` | FR-ING-07, Acceptance #1 |
| TC-REP-009 | Not-in-attendees flagged | F | P1 | Same | Section lists `good-3.md: "Vikram"` with item ID | E7 |
| TC-REP-010 | Counts are consistent | F | P2 | Same | `Files read + Files skipped` = number of `.md` files; `New + Merged` = extracted items | M10 |
| TC-REP-011 | Number alignment | F | P3 | Counts with 1, 2 and 3 digits | Right-aligned as in requirement example | M10 |
| TC-REP-012 | Matches requirement layout | F | P2 | Golden-file compare | Same labels and order as §5 M10 example | M10 |

## 2. Run variations

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-REP-020 | Second run (idempotent) | F | P1 | `ingest MIX/` twice | 2nd summary: `New items: 0`; merged/unassigned/ambiguous per QA-42 | E10 |
| TC-REP-021 | No problems | F | P1 | Folder with only good notes | Skipped count `0`; `Skipped files:` section omitted | M10 |
| TC-REP-022 | Empty folder | E | P1 | `ingest empty/` | All counts `0`; no crash; exit `0` | M10 |
| TC-REP-023 | All files skipped | E | P1 | Folder of 3 malformed files | `Files read: 0`, `Files skipped: 3`, list shown; exit `0` | E8, NFR-01 |
| TC-REP-024 | Notes with no action items | E | P2 | 2 valid notes without checkboxes | `Files read: 2`, `New items: 0` | E9 |
| TC-REP-025 | Long skip list | E | P3 | 100 malformed files | All 100 listed (or summarised with clear count) | M10 |
| TC-REP-026 | Skip reason for unknown error | N | P1 | Fixture that makes a module raise an unexpected exception (inject via mock) | File listed with `unexpected error: <message>`; other files processed | NFR-01 |

## 3. Error handling

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-REP-040 | One file error doesn't stop others | NF | P1 | Inject exception in M3 for `good-2.md` | `good-1.md`, `good-3.md` items still saved | NFR-01 |
| TC-REP-041 | Error in M4/M5/M6 for one item | NF | P1 | Inject exception for one item | That item/file reported; rest processed | NFR-01 |
| TC-REP-042 | Fatal: folder missing | N | P1 | `ingest nope/` | Clear error, non-zero exit; no summary with fake counts | NFR-04 |
| TC-REP-043 | Fatal: store corrupt | N | P1 | Corrupt store, `ingest MIX/` | Clear error; non-zero exit; store not overwritten | M7 |
| TC-REP-044 | Store saved once at end | E | P2 | Fail during save | Store unchanged (atomic); error reported | M7 |
| TC-REP-045 | No stack trace by default | NF | P1 | Any failure | No `Traceback` in output | NFR-04 |
| TC-REP-046 | Debug output (if supported) | NF | P3 | `--verbose` / `--debug` | Stack trace shown for developers | M10 |
| TC-REP-047 | Messages are actionable | NF | P1 | Review every reason/error text | Each says what went wrong **and** how to fix where possible | NFR-04 |

## 4. Non-functional

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-REP-060 | Ingest performance (30 notes) | NF | P1 | Ingest 30 realistic notes on clean store | Completes in ≤ 5 s ("a few seconds") — ❓QA-43 confirm target | NFR-03 |
| TC-REP-061 | Ingest performance (50 notes) | NF | P1 | Ingest 50 realistic notes | ≤ 5 s | NFR-03 |
| TC-REP-062 | Re-ingest performance | NF | P2 | Re-ingest 50 notes with 500 stored items | ≤ 5 s | NFR-03 |
| TC-REP-063 | Fuzz robustness | NF | P1 | 200 random/malformed `.md` files | Ingest finishes; every file counted as read or skipped | NFR-01 |

---

## Questions affecting this module

- **QA-42:** Do "Unassigned items" / "Ambiguous owners" in the summary count this run's items or the whole store? On a re-run, should "Duplicates merged" count every re-seen item?
- **QA-43:** What is the exact performance target for "a few seconds" — is ≤ 5 s on a normal laptop acceptable?
