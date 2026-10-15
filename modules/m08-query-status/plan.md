# M8 — Query and Status Update: Implementation Plan

| Item | Detail |
|---|---|
| File | `actiontrack/query.py` |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-QRY-001 … TC-QRY-122 |
| Milestone | 6 |
| Estimate | 0.75 dev-day |
| Depends on | M7 `Store`, M4 `name_matches`, `models.Item` |
| Used by | M1 (`list`, `done`), M9 (`is_overdue`, owner lookup) |

## 1. Goal

Fast, predictable filtering with one overdue rule used everywhere, a readable table, and a safe `done` command.

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Overdue | `is_overdue(item, today) = status == open and due_date is not None and due_date < today` | One function, reused by M9; never stored (TC-QRY-008) |
| `today` | Parameter; the CLI passes `date.today()` | Deterministic tests with today = 2026-10-15 |
| Filters | Composable predicates combined with AND | FR-LST-05 |
| `--owner` | `name_matches(query, item.owner)`, **or** for ambiguous items any candidate matches; literal `unassigned`/`ambiguous` match those groups | FR-LST-02; QA-33 default (show both Priyas and ambiguous items) |
| `--status open` | Includes overdue items | Overdue is a subset of open (TC-QRY-060) |
| `--due-before` | Strict `<`; items with no due date excluded | QA-35 default; TC-QRY-071/072 |
| Sorting | By ID ascending | Stable, matches the `done <id>` workflow |
| Table rendering | Own formatter: compute column widths, truncate task at 40 chars with `...`, `-` for no due date, first source file + `(+N)` | No dependency; TC-QRY-021..028 |
| Status column | `OVERDUE` (computed) / `open` / `done`; red ANSI only if `stdout.isatty()` and `NO_COLOR` is not set | FR-LST-06; TC-QRY-030 |
| Windows colour | Enable VT mode once via `os.system("")` when on Windows and a TTY | Works in modern Windows terminals |
| Unicode width | Use `unicodedata.east_asian_width` for column width | TC-QRY-027 |
| `done` result | Enum `DONE` / `ALREADY_DONE`; `NotFoundError` for a missing ID | FR-DON-01..03 map cleanly to exit codes |
| Read-only `list` | `list` never calls `store.save()` | TC-QRY-122 |

## 3. Components

```python
def is_overdue(item: Item, today: date) -> bool: ...
def display_status(item: Item, today: date) -> str: ...
def filter_items(items, *, owner=None, status=None, due_before=None, today) -> list[Item]: ...
def owner_filter(query: str) -> Callable[[Item], bool]: ...
def format_table(items: list[Item], today: date, color: bool) -> str: ...

class DoneResult(Enum): DONE = 1; ALREADY_DONE = 2
def mark_done(store: Store, item_id: int) -> DoneResult: ...   # raises NotFoundError
```

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | `is_overdue`, `display_status` | 0.5 h | TC-QRY-001..009 |
| 2 | Filters (owner, status, due-before, AND) | 1.5 h | TC-QRY-040..086 |
| 3 | Table formatter, truncation, colour handling | 1.5 h | TC-QRY-020..030 |
| 4 | `mark_done` + CLI wiring/messages | 1 h | TC-QRY-100..109 |
| 5 | Seed-store fixture (8 items from `test_cases.md`) + golden table output | 1 h | all |
| 6 | Performance test (1,000 items) | 0.5 h | TC-QRY-120 |

## 5. Test approach

- One shared pytest fixture builds the 8-item seed store, so every TC-QRY case uses the same data.
- Golden files hold the table text with colour off and with colour on (ANSI codes).
- The `done`-then-`list` checks (Acceptance #6) and `done`-then-re-ingest (TC-QRY-108) run as CLI integration tests.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Wide tables wrap in narrow terminals | Truncate the task column; use `shutil.get_terminal_size` to shrink it further |
| `--owner priya` showing two people surprises users | Show the full owner name in every row; revisit after QA-33 |

## 7. Open questions

QA-33 … QA-37. Defaults are in the decisions table.

## 8. Definition of done

- [ ] All P1 TC-QRY cases pass (Acceptance #4, #5, #6).
- [ ] The overdue rule exists in exactly one function, used by M8 and M9.
