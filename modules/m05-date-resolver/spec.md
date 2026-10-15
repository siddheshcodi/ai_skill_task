# M5 — Date Resolver

| Item | Detail |
|---|---|
| Module | M5 |
| Source file | `actiontrack/dates.py` |
| Input from | M3 (`due_phrase`), M2 (`meeting_date`) |
| Feeds | M6, M7 |
| Milestone | 4 — Owner + Date resolvers |
| Source | Requirements §5 M5, FR-ING-04, E4, E5, Q6, Acceptance #3 |

## 1. Purpose

Turn a due phrase into a real calendar date **relative to the meeting date** (not today's date). Keep the original wording so a human can check it.

## 2. Rules

Example column assumes a meeting on **Tue 2026-10-06**.

| Due phrase | Rule | Example result |
|---|---|---|
| `2026-10-12` | ISO date as written | 2026-10-12 |
| `12/10/2026` | `DD/MM/YYYY` (per the example in requirements) | 2026-10-12 |
| `Oct 12`, `12 Oct` | Month + day; year = meeting year | 2026-10-12 |
| `by Friday`, `on Monday` | Next matching weekday **strictly after** the meeting date | Fri 2026-10-09 |
| `tomorrow` | Meeting date + 1 day | 2026-10-07 |
| `today`, `EOD` | Meeting date | 2026-10-06 |
| `next week` | Monday of the following week | 2026-10-12 |
| `end of week`, `EOW` | Friday of the same week | 2026-10-09 |
| `end of month` | Last day of the meeting's month | 2026-10-31 |
| No phrase | `due_date = null` | null |
| Unclear phrase (e.g. `soon`, `ASAP`) | `due_date = null`; original phrase kept (E5) | null |

- Leading words `by`, `on`, `due`, `before` are stripped before matching.
- Matching is case-insensitive (`eod`, `Eow`, `FRIDAY`).
- Short weekday names (`Fri`, `Mon`) are accepted.
- Output dates are always `YYYY-MM-DD`.

## 3. Decisions on corner cases

| Case | Decision | Basis |
|---|---|---|
| "by Friday" written on a Friday | **Next** Friday (+7 days) | Q6 working assumption; consistent with "strictly after" |
| `Oct 12` falls before the meeting date (e.g. meeting in Dec) | Use the following year | Working assumption — confirm |
| `end of week` on a Saturday/Sunday meeting | Friday of the **same** ISO week (may be before the meeting) | Literal rule; flag for confirmation |
| `12/10/2026` vs US `10/12/2026` | Treat as `DD/MM/YYYY` | Requirements example → 2026-10-12 |
| Invalid date (`2026-02-30`) | `due_date = null`, phrase kept | Treated as unclear |

## 4. Output

| Field | Type | Example |
|---|---|---|
| `due_date` | date or null | `2026-10-09` |
| `due_phrase` | text or null | `by Friday` (original wording) |

### Suggested interface

```python
def resolve_due_date(due_phrase: str | None, meeting_date: date) -> date | None: ...
```

Pure function, no dependency on the system clock — easy to test.

## 5. Edge cases

| # | Case | Behaviour |
|---|---|---|
| E4 | No due date | `due_date = null`; item never overdue |
| E5 | Unclear due phrase | `due_date = null`; phrase kept |

## 6. Tests

- Every row in §2 with the 2026-10-06 meeting date.
- Meeting on a Friday + "by Friday" → next Friday.
- Year rollover: `next week` / `tomorrow` / `end of month` in late December.
- Month-end in February (leap and non-leap years).
- Case-insensitivity and short weekday names.

## 7. Acceptance criteria

- [ ] "by Friday" and other relative phrases resolve to the correct date based on the meeting date (Acceptance #3).
- [ ] Unclear phrases never crash and never produce a wrong date.
