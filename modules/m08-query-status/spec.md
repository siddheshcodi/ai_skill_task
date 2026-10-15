# M8 — Query and Status Update

| Item | Detail |
|---|---|
| Module | M8 |
| Source file | `actiontrack/query.py` |
| Used by | M1 (`list`, `done`), M9 (owner lookup, open/overdue items) |
| Depends on | M7 |
| Milestone | 6 — `list` and `done` |
| Source | Requirements §5 M8, §6.2, §6.3, E3, E4, Acceptance #4/#5/#6 |

## 1. Purpose

Show stored items with filters, and mark an item as done.

## 2. List filters

| Option | Behaviour | Requirement |
|---|---|---|
| (none) | Show all items | FR-LST-01 |
| `--owner <name>` | Match full name or first name, case-insensitive | FR-LST-02 |
| `--status open\|done\|overdue` | Filter by status (overdue is computed) | FR-LST-03 |
| `--due-before <YYYY-MM-DD>` | `due_date < given date`; items with no due date excluded | FR-LST-04 |
| Combined | All given filters are applied together (AND) | FR-LST-05 |

- `--owner` against `ambiguous` items: an item matches if any of its `owner_candidates` matches (working assumption, so people can see items that might be theirs).
- `--owner unassigned` / `--owner ambiguous` show those groups.
- Invalid status or date → clear error (FR-LST-07; validated in M1).

## 3. Overdue rule

```
overdue  =  status == "open"  AND  due_date is not null  AND  due_date < today
```

- "Today" = the computer's current date (§11). Pass `today` as a parameter so tests can fix it.
- Items with no due date are **never** overdue (E4).
- `--status open` includes overdue items (they are still open); `--status overdue` shows only overdue.

## 4. Output table

Columns: **ID, Owner, Task, Due date, Status, Source file**

```
ID  Owner        Task                         Due         Status    Source
--  -----------  ---------------------------  ----------  --------  ---------------------
 1  Priya Shah   send the revised quote       2026-10-09  OVERDUE   2026-10-06-sales.md
 2  Rahul Mehta  update the CRM               2026-10-12  open      2026-10-06-sales.md
 3  unassigned   share the slide deck ...     -           open      2026-10-06-sales.md
 4  ambiguous    review contract (Priya Shah / Priya Kumar)  -  open  2026-10-08-legal.md
```

- Overdue items stand out with an `OVERDUE` label (and red text when the terminal supports colour) — FR-LST-06.
- Several source files: show the first and `(+N)`.
- Long task text is truncated to keep the table readable.
- Sort: by ID (default).
- No matching items → print `No items found.` and exit `0`.

## 5. Mark done

| Case | Behaviour | Requirement |
|---|---|---|
| ID exists, status open | Set `status = done`, update `updated_at`, save | FR-DON-01 |
| ID does not exist | Error `Item 99 not found.`, non-zero exit | FR-DON-02 |
| Already done | Message `Item 12 is already done.`, exit `0` | FR-DON-03 |

## 6. Suggested interface

```python
def is_overdue(item: Item, today: date) -> bool: ...
def filter_items(items, owner=None, status=None, due_before=None, today=None) -> list[Item]: ...
def owner_matches(item: Item, name: str) -> bool: ...
def format_table(items, today) -> str: ...
def mark_done(store: Store, item_id: int) -> DoneResult: ...  # DONE | ALREADY_DONE | NOT_FOUND
```

## 7. Tests

- Each filter alone and all combinations.
- Owner by first name, full name, mixed case.
- Overdue boundaries: due yesterday (overdue), due today (not overdue), no due date (never overdue), done + past due (not overdue).
- `done` on open, already done, missing ID.
- `done` change visible in subsequent `list`.

## 8. Acceptance criteria

- [ ] Items with no owner, no due date or ambiguous owner are visible (Acceptance #4).
- [ ] Filters work alone and together (Acceptance #5).
- [ ] `done <id>` updates the item and the change is visible in `list` (Acceptance #6).
