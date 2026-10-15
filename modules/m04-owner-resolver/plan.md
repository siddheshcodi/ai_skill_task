# M4 — Owner Resolver: Implementation Plan

| Item | Detail |
|---|---|
| File | `actiontrack/owners.py` |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-OWN-001 … TC-OWN-084 |
| Milestone | 4 |
| Estimate | 0.5 dev-day |
| Depends on | `models.OwnerResult`, constants `UNASSIGNED`, `AMBIGUOUS` |
| Used by | `ingest.run_ingest`; M8/M9 reuse `name_matches()` |

## 1. Goal

Map an owner phrase to exactly one attendee of **that meeting**. If it is unclear, return `ambiguous` with candidates. If it is unknown, keep the name and flag it. Never guess.

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Pure function | `resolve_owner(phrase, attendees) -> OwnerResult` | No I/O; fully table-testable |
| Normalisation | `casefold()`, trim, drop leading `@` and trailing `:`/`.`, collapse spaces | TC-OWN-003..005 |
| Accents | Not stripped by default (exact Unicode compare after casefold) | QA-17 default; can switch to `unicodedata` NFKD later |
| Name parts | Attendee split into `first`, `last` (last token), `middle` (anything between) | Middle-name support (TC-OWN-060) |
| Matching cascade | 1 exact full name → 2 first + last/initial → 3 first name only → 4 not found | Matches spec §2 order; first rule that gives ≥ 1 candidate decides |
| Initial rule | `last.startswith(given)` after removing `.` | `Priya S.` → Shah; `Priya Kh` → Khan |
| Result per count | 1 candidate → that attendee · ≥ 2 → `ambiguous` + sorted candidates · 0 → phrase as written + `not_in_attendees=True` | E6, E7 |
| Duplicate attendees | De-duplicate attendees before matching | TC-OWN-029 |
| Spelling | Return the attendee's spelling, not the phrase's | TC-OWN-007 |
| Wrong last name | `Priya Patel` with attendee `Priya Shah` → not found (flag), do **not** fall back to first name | QA-15 default; avoids wrong owner |
| Reserved values | Owner phrases equal to `unassigned`/`ambiguous` are treated as unknown names | TC-OWN-066 |

## 3. Components

```python
def resolve_owner(owner_phrase: str | None, attendees: list[str]) -> OwnerResult: ...
def normalize_name(s: str) -> str: ...
def split_name(full: str) -> tuple[str, str | None]: ...      # (first, last)
def name_matches(query: str, full_name: str) -> bool: ...     # shared with M8/M9 (--owner, followup)
```

`name_matches` (full-name or first-name match, case-insensitive) is the single owner-matching rule used by `list --owner` and `followup <owner>`, so all three commands behave the same way.

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | `normalize_name`, `split_name` | 0.5 h | TC-OWN-003..005, 060..065 |
| 2 | Matching cascade + `OwnerResult` | 1.5 h | TC-OWN-001..048 |
| 3 | `name_matches` helper for M8/M9 | 0.5 h | TC-QRY-040..050, TC-FUP-020..023 |
| 4 | Parametrised tests with attendee sets A1/A2/A3 | 1 h | all |
| 5 | Integration checks via ingest (unassigned/ambiguous visible, counted) | 0.5 h | TC-OWN-080..084 |

## 5. Test approach

- One table per section of `test_cases.md`: `(phrase, attendees) → (owner, candidates, flagged)`.
- Property: if the result is a real name, it is always either an attendee or exactly the input phrase. It is never some other person.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Nicknames (`Raj` vs `Rajesh`) are not resolved | Flagged as not-in-attendees in the summary (E7); an alias map in `people.yaml` could come later |
| Multiple owners in one phrase | Flagged; not split (QA-13) |

## 7. Open questions

QA-12, QA-13, QA-15, QA-16, QA-17. Defaults are listed in the decisions table.

## 8. Definition of done

- [ ] All P1 TC-OWN cases pass.
- [ ] `name_matches` is reused by M8 and M9 (no duplicate matching logic).
