# M5 — Date Resolver: Implementation Plan

| Item | Detail |
|---|---|
| File | `actiontrack/dates.py` |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-DAT-001 … TC-DAT-092 |
| Milestone | 4 |
| Estimate | 1.0 dev-day |
| Depends on | stdlib only (`datetime`, `calendar`, `re`) |
| Used by | `ingest.run_ingest`; M3 imports its shared patterns |

## 1. Goal

A pure, clock-free function that turns a due phrase into a date **relative to the meeting date**. It returns `None` for anything unclear. It must not produce a wrong date.

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Signature | `resolve_due_date(phrase: str \| None, meeting: date) -> date \| None` | Pure; no `date.today()` inside (TC-DAT-017, 090) |
| Pre-processing | casefold, strip punctuation/brackets at the ends, remove a leading `by`/`on`/`due`/`before`, collapse spaces | TC-DAT-026..027 |
| Rule engine | Ordered list of `(regex, handler)` pairs; first match wins | Each rule is isolated and testable; easy to add rules |
| Weekday rule | `delta = (target - meeting.weekday() - 1) % 7 + 1` → always 1..7 days after | "Strictly after" (Q6, TC-DAT-021/022) |
| Week definition | ISO week, Monday start | QA-19 default |
| `next week` | `meeting - weekday + 7 days` (next Monday) | Spec table |
| `end of week` / `EOW` | `meeting - weekday + 4` (Friday of the same ISO week) | Spec table; weekend meetings → QA-20 (default literal rule, may be before the meeting) |
| `end of month` | `calendar.monthrange(y, m)[1]` | Leap years handled (TC-DAT-050/051) |
| Explicit dates | ISO via `date.fromisoformat`; `D/M/YYYY` (DD/MM); `Mon D`, `D Mon`, `Month D[, YYYY]`, ordinals | Spec table; QA-23 default DD/MM |
| Year inference | Month+day without year → meeting year; if that date is before the meeting → next year | Spec §3 |
| Invalid dates | Catch `ValueError` → `None` | E5, TC-DAT-069..072 |
| `this`/`next <weekday>` | Same as `<weekday>` (strictly after the meeting); phrase kept | QA-18 (decisions.md) |
| Unsupported phrases | `None` (`soon`, `in 2 days`, `next month`, `EOD Friday`, `e.o.d.`, 2-digit years) | E5, QA-21, QA-23, QA-24 |
| Shared patterns | Export `WHEN_PATTERN` (union of all supported phrase regexes) and `VAGUE_WORDS` for M3 | One vocabulary for M3 and M5 |

### Rule table (implementation order)

| # | Pattern (after pre-processing) | Handler |
|---|---|---|
| 1 | `\d{4}-\d{2}-\d{2}` | ISO |
| 2 | `\d{1,2}/\d{1,2}/\d{4}` | DD/MM/YYYY |
| 3 | `<month> <day>[st\|nd\|rd\|th][, <year>]` / `<day> <month> [<year>]` | Month-day + year inference |
| 4 | `today\|eod\|end of day` | meeting |
| 5 | `tomorrow` | meeting + 1 |
| 6 | `<weekday>` (full or 3-letter) | next weekday strictly after |
| 7 | `next week` | Monday of the next week |
| 8 | `end of week\|eow` | Friday of the same week |
| 9 | `end of month\|eom` | Last day of the month |
| — | anything else | `None` |

## 3. Components

```python
WHEN_PATTERN: str              # used by M3
VAGUE_WORDS: frozenset[str]    # used by M3
RULES: list[tuple[Pattern, Callable[[Match, date], date]]]

def resolve_due_date(phrase: str | None, meeting: date) -> date | None: ...
def normalize_phrase(phrase: str) -> str: ...
def next_weekday_after(meeting: date, weekday: int) -> date: ...
def week_monday(d: date) -> date: ...
def month_end(d: date) -> date: ...
```

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | Helpers: `normalize_phrase`, `next_weekday_after`, `week_monday`, `month_end` | 1 h | TC-DAT-020..054 |
| 2 | Explicit date rules + year inference + validation | 2 h | TC-DAT-001..003, 060..073 |
| 3 | Relative keyword rules | 1.5 h | TC-DAT-004..012, 040..056 |
| 4 | `WHEN_PATTERN` / `VAGUE_WORDS` export + M3 contract test | 1 h | TC-EXT-060..073 |
| 5 | Full parametrised table: 7 weekdays × 7 meeting days (49 generated cases) + boundaries | 1.5 h | TC-DAT-020 |
| 6 | Timezone/locale independence test | 0.5 h | TC-DAT-090..091 |

## 5. Test approach

- The spec example table is the first parametrised test (Acceptance #3).
- Generated grid: for each meeting day Mon..Sun and each weekday phrase, check `1 ≤ (due − meeting).days ≤ 7` and that `due.weekday()` is the target weekday.
- Boundary sets: month end, year end, Feb 28/29 in leap and non-leap years.

## 6. Risks

| Risk | Mitigation |
|---|---|
| DD/MM vs MM/DD misread (QA-23) | Only DD/MM is supported; documented in README; `due_phrase` is kept so a human can check |
| Weekend "end of week" gives a date before the meeting (QA-20) | Isolated in one handler; flip the rule once QA-20 is answered |
| Product asks for more phrases later | Add a row to the rule table plus tests; M3 picks it up automatically via `WHEN_PATTERN` |

## 7. Open questions

QA-18 … QA-24. Defaults are in the decisions table. QA-20 and QA-23 should be answered before release.

## 8. Definition of done

- [ ] All rows of the spec table pass (Acceptance #3).
- [ ] All P1 TC-DAT cases pass with the system clock frozen to a different date.
