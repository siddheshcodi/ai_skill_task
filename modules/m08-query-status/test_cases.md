# M8 — Query and Status Update: Test Cases

| Item | Detail |
|---|---|
| Module | M8 Query and Status Update (`actiontrack/query.py`) |
| Covers | §5 M8, §6.2 FR-LST-01..07, §6.3 FR-DON-01..03, E3, E4, Acceptance #4/#5/#6 |
| Test levels | Unit (`filter_items`, `is_overdue`, `mark_done` with fixed `today`) + CLI (`list`, `done`) |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

**Fixed "today" for all tests: 2026-10-15.**

Seed store (used unless stated otherwise):

| ID | Owner | Task | Due date | Status | Source |
|---|---|---|---|---|---|
| 1 | Priya Shah | send the revised quote | 2026-10-09 | open | sales-1006.md |
| 2 | Rahul Mehta | update the CRM | 2026-10-20 | open | sales-1006.md |
| 3 | Anita Rao | book the demo room | 2026-10-08 | done | sales-1006.md |
| 4 | unassigned | share the slide deck | null | open | sales-1006.md |
| 5 | ambiguous [Priya Shah, Priya Kumar] | review contract | 2026-10-14 | open | legal-1008.md |
| 6 | Priya Kumar | prepare invoice | 2026-10-15 | open | legal-1008.md |
| 7 | Priya Shah | update pricing sheet | null | open | sales-1006.md, sales-1013.md |
| 8 | Rahul Mehta | call the client | 2026-10-16 | open | sales-1013.md |

---

## 1. Overdue rule

| ID | Scenario | Type | Pri | Item | Expected overdue? | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-001 | Open, due in past | F | P1 | #1 (10-09) | Yes | M8 rule |
| TC-QRY-002 | Open, due yesterday | E | P1 | open, due 2026-10-14 | Yes | M8 rule |
| TC-QRY-003 | Open, due today | E | P1 | #6 (10-15) | **No** (`due_date < today` is strict) | M8 rule |
| TC-QRY-004 | Open, due tomorrow | E | P1 | #8 (10-16) | No | M8 rule |
| TC-QRY-005 | Done, due in past | F | P1 | #3 | No | M8 rule |
| TC-QRY-006 | Open, no due date | F | P1 | #4, #7 | Never | E4 |
| TC-QRY-007 | Uses real system date | F | P2 | Do not mock today; item due yesterday | Overdue | §11 |
| TC-QRY-008 | Overdue not stored | F | P1 | Inspect store after `list` | Status still `open` | M7 |
| TC-QRY-009 | Becomes overdue over time | E | P2 | Item #8; run with today = 10-16, then 10-17 | Not overdue, then overdue — without re-ingest | M8 |

## 2. `list` — no filters and display

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-020 | All items | F | P1 | `list` | 8 rows, all statuses, incl. unassigned & ambiguous | FR-LST-01, Acceptance #4 |
| TC-QRY-021 | Table columns | F | P1 | `list` | Columns: ID, Owner, Task, Due date, Status, Source file | M8 |
| TC-QRY-022 | Overdue marked | F | P1 | `list` | #1 and #5 show `OVERDUE` label (red when colour supported) | FR-LST-06 |
| TC-QRY-023 | No due date display | F | P2 | `list` | #4, #7 show `-` (or `none`) — not `null`/`None` | E4 |
| TC-QRY-024 | Ambiguous display | F | P2 | `list` | #5 shows `ambiguous` and both candidate names | E6 |
| TC-QRY-025 | Multiple source files | F | P3 | `list` | #7 shows first file + `(+1)` | M8 |
| TC-QRY-026 | Long task truncated | E | P3 | Task of 200 chars | Truncated with `...`; table aligned | M8 |
| TC-QRY-027 | Unicode alignment | E | P3 | Owner `José Núñez` | Columns still aligned | NFR-07 |
| TC-QRY-028 | Sorted by ID | F | P3 | `list` | Rows in ascending ID | M8 |
| TC-QRY-029 | Empty store | E | P1 | `list` on empty store | `No items found.`; exit `0` | FR-LST-01 |
| TC-QRY-030 | Colour off when piped | NF | P3 | `list > out.txt`, or `NO_COLOR=1` | No ANSI codes in output; `OVERDUE` text still present | FR-LST-06, NFR-07 |

## 3. `--owner`

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-040 | Full name | F | P1 | `list --owner "Priya Shah"` | #1, #7 (+ #5 per QA-33) | FR-LST-02 |
| TC-QRY-041 | First name, one person | F | P1 | `list --owner rahul` | #2, #8 | FR-LST-02 |
| TC-QRY-042 | Case-insensitive | F | P1 | `--owner RAHUL`, `--owner rAhUl mEhTa` | #2, #8 | FR-LST-02 |
| TC-QRY-043 | First name, two people | E | P1 | `list --owner priya` | Items of Priya Shah **and** Priya Kumar (#1, #6, #7, #5) — ❓QA-33 | FR-LST-02 |
| TC-QRY-044 | Ambiguous item matched by candidate | E | P2 | `list --owner "Priya Kumar"` | #6 and #5 (candidate) — ❓QA-33 | E6 |
| TC-QRY-045 | Unassigned | F | P2 | `list --owner unassigned` | #4 | E3 |
| TC-QRY-046 | Ambiguous | F | P2 | `list --owner ambiguous` | #5 | E6 |
| TC-QRY-047 | Unknown owner | N | P1 | `list --owner Vikram` | `No items found.`; exit `0` | FR-LST-02 |
| TC-QRY-048 | Partial name | N | P2 | `list --owner Pri` | ❓QA-34 Recommended: no match (only full/first name) | FR-LST-02 |
| TC-QRY-049 | Last name only | E | P3 | `list --owner Shah` | ❓QA-34 Recommended: no match | FR-LST-02 |
| TC-QRY-050 | Extra spaces | E | P3 | `list --owner "  Priya   Shah "` | Same as `Priya Shah` | FR-LST-02 |

## 4. `--status`

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-060 | Open | F | P1 | `list --status open` | #1, #2, #4, #5, #6, #7, #8 (includes overdue) | FR-LST-03 |
| TC-QRY-061 | Done | F | P1 | `list --status done` | #3 | FR-LST-03 |
| TC-QRY-062 | Overdue | F | P1 | `list --status overdue` | #1, #5 only | FR-LST-03 |
| TC-QRY-063 | Invalid status | N | P1 | `list --status late` | Clear error listing valid values; non-zero exit | FR-LST-07 |

## 5. `--due-before`

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-070 | Basic | F | P1 | `list --due-before 2026-10-15` | #1, #3, #5 (due < 10-15) | FR-LST-04 |
| TC-QRY-071 | Boundary is exclusive | E | P1 | `list --due-before 2026-10-15` | #6 (due 10-15) **not** included — ❓QA-35 confirm "before" excludes same day | FR-LST-04 |
| TC-QRY-072 | No-due-date excluded | F | P1 | `list --due-before 2030-01-01` | #4, #7 not shown | E4 |
| TC-QRY-073 | Includes done items | F | P2 | `list --due-before 2026-10-10` | #1, #3 (done items included unless status filter) | FR-LST-04 |
| TC-QRY-074 | Date in far past | E | P3 | `--due-before 2000-01-01` | `No items found.` | FR-LST-04 |
| TC-QRY-075 | Invalid date | N | P1 | `--due-before 2026-02-30`, `--due-before 15/10/2026` | Clear error; non-zero exit | FR-LST-07 |

## 6. Combined filters (AND)

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-080 | Owner + status | F | P1 | `list --owner "Priya Shah" --status overdue` | #1, #5 (ambiguous item listing Priya Shah, QA-33) | FR-LST-05 |
| TC-QRY-081 | Owner + due-before | F | P1 | `list --owner rahul --due-before 2026-10-18` | #8 | FR-LST-05 |
| TC-QRY-082 | Status + due-before | F | P1 | `list --status open --due-before 2026-10-16` | #1, #5, #6 | FR-LST-05 |
| TC-QRY-083 | All three | F | P1 | `list --owner "Priya Shah" --status open --due-before 2026-10-31` | #1, #5 (QA-33) | FR-LST-05, Acceptance #5 |
| TC-QRY-084 | Conflicting filters | E | P2 | `list --status done --due-before 2000-01-01` | `No items found.`; exit `0` | FR-LST-05 |
| TC-QRY-085 | Overdue + due-before | E | P3 | `list --status overdue --due-before 2026-10-10` | #1 | FR-LST-05 |
| TC-QRY-086 | Repeated option | E | P3 | `list --owner rahul --owner anita` | ❓QA-36 Last wins **or** error — defined, no crash | M1 |

## 7. `done <id>`

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-100 | Mark open item done | F | P1 | `done 2` | Message `Item 2 marked as done.`; status `done`; `updated_at` changed; exit `0` | FR-DON-01 |
| TC-QRY-101 | Visible in list | F | P1 | `done 2` then `list --status done` | #2 and #3 shown | Acceptance #6 |
| TC-QRY-102 | Mark overdue item done | F | P1 | `done 1` then `list --status overdue` | #1 no longer overdue | FR-DON-01 |
| TC-QRY-103 | Already done | F | P1 | `done 3` | `Item 3 is already done.`; exit `0`; `updated_at` unchanged | FR-DON-03 |
| TC-QRY-104 | ID not found | N | P1 | `done 99` | `Item 99 not found.`; non-zero exit; store unchanged | FR-DON-02 |
| TC-QRY-105 | Done on unassigned item | E | P2 | `done 4` | Marked done | E3 |
| TC-QRY-106 | Done on ambiguous item | E | P2 | `done 5` | Marked done | E6 |
| TC-QRY-107 | Done on empty store | N | P2 | `done 1` with no store | `Item 1 not found.` | FR-DON-02 |
| TC-QRY-108 | Done persists after re-ingest | F | P1 | `done 2`, then `ingest notes/` (note still shows `[ ]`) | #2 still `done` | E10, M6 |
| TC-QRY-109 | Undo done | E | P3 | Way to reopen? | ❓QA-37 Not in scope — confirm no `reopen` command needed | FR-DON-01 |

## 8. Non-functional

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-QRY-120 | `list` speed | NF | P1 | Store with 1,000 items, all filters | < 1 s | NFR-03 |
| TC-QRY-121 | Readable on 80-column terminal | NF | P3 | `list` in 80-col terminal | Readable without wrapping chaos | NFR-04 |
| TC-QRY-122 | Read-only command doesn't write | NF | P2 | `list`; compare store hash before/after | Unchanged | NFR-01 |

---

## Questions affecting this module

- **QA-33:** `--owner priya` when two Priyas exist — show both (recommended) or ask to be more specific (like `followup`)? Should ambiguous items appear under each candidate?
- **QA-34:** Should partial names or last names match (`Pri`, `Shah`)?
- **QA-35:** Is `--due-before 2026-10-15` strictly before (excludes 10-15)?
- **QA-36:** Repeated filter options — last wins or error?
- **QA-37:** Is a way to re-open a done item needed?
