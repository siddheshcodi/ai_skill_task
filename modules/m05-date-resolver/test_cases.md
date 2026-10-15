# M5 — Date Resolver: Test Cases

| Item | Detail |
|---|---|
| Module | M5 Date Resolver (`actiontrack/dates.py`) |
| Covers | §5 M5, FR-ING-04, E4, E5, Q6, Acceptance #3 |
| Test levels | Unit (`resolve_due_date(due_phrase, meeting_date)`) — parametrised; independent of system clock |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

Default meeting date: **Tue 2026-10-06** (week Mon 2026-10-05 … Sun 2026-10-11).

---

## 1. Requirement table (exact rules)

| ID | Scenario | Type | Pri | Due phrase | Meeting | Expected `due_date` | Trace |
|---|---|---|---|---|---|---|---|
| TC-DAT-001 | ISO date | F | P1 | `2026-10-12` / `by 2026-10-12` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-002 | DD/MM/YYYY | F | P1 | `12/10/2026` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-003 | Month + day | F | P1 | `Oct 12` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-004 | `by Friday` | F | P1 | `by Friday` | Tue 10-06 | 2026-10-09 | M5, Acceptance #3 |
| TC-DAT-005 | `on Monday` | F | P1 | `on Monday` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-006 | `tomorrow` | F | P1 | `tomorrow` | Tue 10-06 | 2026-10-07 | M5 |
| TC-DAT-007 | `today` | F | P1 | `today` | Tue 10-06 | 2026-10-06 | M5 |
| TC-DAT-008 | `EOD` | F | P1 | `EOD` | Tue 10-06 | 2026-10-06 | M5 |
| TC-DAT-009 | `next week` | F | P1 | `next week` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-010 | `end of week` | F | P1 | `end of week` | Tue 10-06 | 2026-10-09 | M5 |
| TC-DAT-011 | `EOW` | F | P1 | `EOW` | Tue 10-06 | 2026-10-09 | M5 |
| TC-DAT-012 | `end of month` | F | P1 | `end of month` | Tue 10-06 | 2026-10-31 | M5 |
| TC-DAT-013 | No phrase | F | P1 | `None` | Tue 10-06 | `null` | E4 |
| TC-DAT-014 | Unclear phrase | F | P1 | `soon`, `ASAP`, `later`, `when possible` | Tue 10-06 | `null`, original phrase kept | E5 |
| TC-DAT-015 | Output format | F | P1 | Any resolved phrase | — | Stored as `YYYY-MM-DD` string | M5 |
| TC-DAT-016 | Original phrase kept | F | P1 | `by Friday` | Tue 10-06 | `due_phrase = "by Friday"` alongside date | M5 |
| TC-DAT-017 | Relative to meeting, not today | F | P1 | `tomorrow` with meeting 2026-10-06 and system date 2026-10-15 | — | 2026-10-07 (not 2026-10-16) | M5, Acceptance #3 |

## 2. Weekday rule — every weekday from every meeting day

| ID | Scenario | Type | Pri | Due phrase | Meeting | Expected | Trace |
|---|---|---|---|---|---|---|---|
| TC-DAT-020 | All weekdays from Tuesday | F | P1 | `by Monday` … `by Sunday` | Tue 10-06 | Mon 10-12, **Tue 10-13**, Wed 10-07, Thu 10-08, Fri 10-09, Sat 10-10, Sun 10-11 | M5 |
| TC-DAT-021 | Same weekday as meeting → next week | E | P1 | `by Tuesday` | Tue 10-06 | 2026-10-13 (strictly after) | M5, Q6 |
| TC-DAT-022 | "by Friday" written on Friday | E | P1 | `by Friday` | Fri 2026-10-09 | 2026-10-16 | Q6 |
| TC-DAT-023 | Weekday from Sunday meeting | E | P2 | `by Monday` | Sun 2026-10-11 | 2026-10-12 | M5 |
| TC-DAT-024 | Weekday from Saturday meeting | E | P2 | `by Friday` | Sat 2026-10-10 | 2026-10-16 | M5 |
| TC-DAT-025 | Short weekday names | F | P2 | `by Fri`, `on Mon`, `Thu` | Tue 10-06 | 10-09, 10-12, 10-08 | M5 |
| TC-DAT-026 | Case-insensitive | F | P2 | `BY FRIDAY`, `by friday`, `eod`, `Eow`, `End Of Month` | Tue 10-06 | Same as standard | M5 |
| TC-DAT-027 | Trailing punctuation | E | P2 | `by Friday.`, `by Friday!`, `(by Friday)` | Tue 10-06 | 2026-10-09 | M5 |
| TC-DAT-028 | "this Friday" / "next Friday" | E | P2 | `this Friday`, `next Friday` | Tue 10-06 | ❓QA-18 `this Friday` = 10-09; `next Friday` = 10-09 or 10-16? Must be defined, else null | M5 |
| TC-DAT-029 | Weekday across month end | E | P2 | `by Monday` | Thu 2026-10-29 | 2026-11-02 | M5 |
| TC-DAT-030 | Weekday across year end | E | P1 | `by Friday` | Wed 2026-12-30 | 2027-01-01 | M5 |

## 3. Relative keywords — boundaries

| ID | Scenario | Type | Pri | Due phrase | Meeting | Expected | Trace |
|---|---|---|---|---|---|---|---|
| TC-DAT-040 | `tomorrow` at month end | E | P1 | `tomorrow` | 2026-10-31 | 2026-11-01 | M5 |
| TC-DAT-041 | `tomorrow` at year end | E | P1 | `tomorrow` | 2026-12-31 | 2027-01-01 | M5 |
| TC-DAT-042 | `tomorrow` on Feb 28, leap year | E | P2 | `tomorrow` | 2028-02-28 | 2028-02-29 | M5 |
| TC-DAT-043 | `tomorrow` on Feb 28, non-leap | E | P2 | `tomorrow` | 2027-02-28 | 2027-03-01 | M5 |
| TC-DAT-044 | `next week` from Monday | E | P1 | `next week` | Mon 2026-10-05 | 2026-10-12 | M5 |
| TC-DAT-045 | `next week` from Sunday | E | P1 | `next week` | Sun 2026-10-11 | 2026-10-12 (week = Mon–Sun) — ❓QA-19 confirm week starts Monday | M5 |
| TC-DAT-046 | `next week` across year end | E | P2 | `next week` | Wed 2026-12-30 | 2027-01-04 | M5 |
| TC-DAT-047 | `end of week` on Friday | E | P1 | `EOW` | Fri 2026-10-09 | 2026-10-09 (same day) | M5 |
| TC-DAT-048 | `end of week` on Saturday | E | P1 | `EOW` | Sat 2026-10-10 | ❓QA-20 2026-10-09 (before meeting, literal rule) **or** 2026-10-16 | M5 |
| TC-DAT-049 | `end of week` on Sunday | E | P1 | `EOW` | Sun 2026-10-11 | ❓QA-20 Same question as above | M5 |
| TC-DAT-050 | `end of month` February leap | E | P1 | `end of month` | 2028-02-10 | 2028-02-29 | M5 |
| TC-DAT-051 | `end of month` February non-leap | E | P1 | `end of month` | 2027-02-10 | 2027-02-28 | M5 |
| TC-DAT-052 | `end of month` 30-day month | E | P2 | `end of month` | 2026-11-03 | 2026-11-30 | M5 |
| TC-DAT-053 | `end of month` December | E | P2 | `end of month` | 2026-12-15 | 2026-12-31 | M5 |
| TC-DAT-054 | `end of month` on last day | E | P2 | `end of month` | 2026-10-31 | 2026-10-31 | M5 |
| TC-DAT-055 | `EOD` variants | E | P3 | `by EOD`, `end of day`, `e.o.d.` | Tue 10-06 | ❓QA-21 2026-10-06 if variant supported, else null | M5 |
| TC-DAT-056 | `EOM` abbreviation | E | P3 | `EOM` | Tue 10-06 | ❓QA-21 2026-10-31 if supported, else null | M5 |

## 4. Explicit dates — formats and validity

| ID | Scenario | Type | Pri | Due phrase | Meeting | Expected | Trace |
|---|---|---|---|---|---|---|---|
| TC-DAT-060 | `12 Oct` | F | P2 | `12 Oct` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-061 | Full month name | F | P2 | `October 12`, `12 October` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-062 | Month + day + year | F | P2 | `Oct 12, 2026`, `12 Oct 2026` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-063 | Ordinal day | E | P3 | `Oct 12th`, `12th October` | Tue 10-06 | 2026-10-12 | M5 |
| TC-DAT-064 | Month+day before meeting | E | P1 | `Jan 15` | 2026-12-10 | 2027-01-15 (next year) — assumption | M5 §3 |
| TC-DAT-065 | ISO date before meeting date | E | P2 | `2026-10-01` | Tue 10-06 | 2026-10-01 kept as written (already overdue) — ❓QA-22 confirm | M5 |
| TC-DAT-066 | DD/MM ambiguity | E | P1 | `05/10/2026` | Tue 10-06 | 2026-10-05 (DD/MM) — ❓QA-23 confirm DD/MM not MM/DD | M5 |
| TC-DAT-067 | Day > 12 forces DD/MM | E | P2 | `25/10/2026` | — | 2026-10-25 | M5 |
| TC-DAT-068 | Short year | E | P3 | `12/10/26` | — | ❓QA-23 2026-10-12 if supported, else null | M5 |
| TC-DAT-069 | Invalid ISO date | N | P1 | `2026-02-30`, `2026-13-01` | — | `null`, phrase kept; no crash | E5 |
| TC-DAT-070 | Invalid DD/MM | N | P1 | `31/02/2026`, `13/13/2026` | — | `null`, phrase kept | E5 |
| TC-DAT-071 | Invalid month name | N | P2 | `Octember 12`, `Oct 32` | — | `null` | E5 |
| TC-DAT-072 | Leap day valid / invalid | E | P2 | `2028-02-29` / `2027-02-29` | — | 2028-02-29 / `null` | M5 |
| TC-DAT-073 | Time included | E | P3 | `by Friday 5pm`, `2026-10-12 17:00` | Tue 10-06 | Date only (2026-10-09 / 2026-10-12) or null — defined, no crash | M5 |

## 5. Unsupported / unclear phrases (E5)

| ID | Scenario | Type | Pri | Due phrase | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-DAT-080 | Vague words | N | P1 | `soon`, `ASAP`, `later`, `TBD`, `next sprint`, `Q4` | `null`, phrase kept | E5 |
| TC-DAT-081 | Relative counts | E | P2 | `in 2 days`, `in a week`, `within 3 days` | ❓QA-24 `null` (not in required list) or supported | E5 |
| TC-DAT-082 | `next month` | E | P3 | `next month` | ❓QA-24 `null` unless rule defined | E5 |
| TC-DAT-083 | Empty / whitespace | N | P2 | `""`, `"   "` | `null` | E4 |
| TC-DAT-084 | Combined phrases | E | P3 | `EOD Friday`, `by Friday or Monday` | ❓QA-24 Defined (e.g. first phrase / null) — no crash | E5 |
| TC-DAT-085 | Non-English | N | P3 | `viernes`, `demain` | `null` (notes are English, §11) | §11 |

## 6. Non-functional

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-DAT-090 | Independent of system clock | NF | P1 | Run TC-DAT-001..012 with system date mocked to 2027-06-01 | Same results | NFR-06 |
| TC-DAT-091 | Independent of locale/timezone | NF | P2 | Run tests with `TZ=Asia/Kolkata`, `TZ=America/Los_Angeles`, different OS locales | Same results | NFR-07 |
| TC-DAT-092 | Performance | NF | P3 | Resolve 10,000 phrases | < 1 s | NFR-03 |

---

## Questions affecting this module

- **QA-18:** What does "next Friday" mean — the coming Friday or the Friday of next week? What about "this Friday"?
- **QA-19:** Does the week start on Monday (for "next week" / "end of week")?
- **QA-20:** For a meeting on Saturday/Sunday, is "end of week" the Friday just passed or the coming Friday?
- **QA-21:** Which abbreviations must be supported (`end of day`, `EOM`)?
- **QA-22:** If an explicit due date is before the meeting date, keep it as written or treat it as invalid?
- **QA-23:** Confirm `DD/MM/YYYY` (not US `MM/DD/YYYY`). Should 2-digit years be supported?
- **QA-24:** Should `in N days`, `next month`, or combined phrases be supported, or become null?
