# M4 — Owner Resolver: Test Cases

| Item | Detail |
|---|---|
| Module | M4 Owner Resolver (`actiontrack/owners.py`) |
| Covers | §5 M4, FR-ING-04, E3, E6, E7, Q5, Acceptance #4 |
| Test levels | Unit (`resolve_owner(owner_phrase, attendees)`) — parametrised |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

Attendee sets used below:

- **A1** = `[Priya Shah, Rahul Mehta, Anita Rao]`
- **A2** = `[Priya Shah, Priya Kumar, Rahul Mehta]`
- **A3** = `[Priya Shah, Priya Kumar, Priya Khan, Rahul Mehta]`

---

## 1. Basic resolution

| ID | Scenario | Type | Pri | Owner phrase | Attendees | Expected result | Trace |
|---|---|---|---|---|---|---|---|
| TC-OWN-001 | First name, one match | F | P1 | `Priya` | A1 | `Priya Shah` | M4 |
| TC-OWN-002 | Full name exact | F | P1 | `Rahul Mehta` | A1 | `Rahul Mehta` | M4 |
| TC-OWN-003 | Case-insensitive | F | P1 | `rahul`, `RAHUL`, `rAhUl` | A1 | `Rahul Mehta` | M4 |
| TC-OWN-004 | `@` prefix | F | P1 | `@Anita` | A1 | `Anita Rao` | M4 |
| TC-OWN-005 | Surrounding spaces / trailing colon | E | P2 | `  Priya  `, `Priya:` | A1 | `Priya Shah` | M4 |
| TC-OWN-006 | No owner phrase | F | P1 | `None` / `""` | A1 | `owner = unassigned`, candidates `[]` | E3 |
| TC-OWN-007 | Output uses attendee spelling | F | P2 | `priya` | A1 | Stored as `Priya Shah` (attendee spelling, not phrase) | M4 |

## 2. Same first name (E6)

| ID | Scenario | Type | Pri | Owner phrase | Attendees | Expected result | Trace |
|---|---|---|---|---|---|---|---|
| TC-OWN-020 | Two Priyas, first name only | F | P1 | `Priya` | A2 | `owner = ambiguous`, candidates `[Priya Shah, Priya Kumar]` | E6 |
| TC-OWN-021 | Two Priyas, initial with dot | F | P1 | `Priya S.` | A2 | `Priya Shah` | E6 |
| TC-OWN-022 | Two Priyas, initial no dot | F | P1 | `Priya K` | A2 | `Priya Kumar` | E6 |
| TC-OWN-023 | Two Priyas, full name | F | P1 | `Priya Kumar` | A2 | `Priya Kumar` | E6 |
| TC-OWN-024 | Two Priyas, full name lower-case | E | P2 | `priya shah` | A2 | `Priya Shah` | E6 |
| TC-OWN-025 | Three Priyas, initial matches two | E | P1 | `Priya K.` | A3 | `ambiguous`, candidates `[Priya Kumar, Priya Khan]` | E6 |
| TC-OWN-026 | Three Priyas, partial last name | E | P2 | `Priya Kh` | A3 | `Priya Khan` (last name starts with `Kh`) | E6 |
| TC-OWN-027 | Only one Priya in **this** meeting | F | P1 | `Priya` | A1 (Priya Kumar exists in other notes) | `Priya Shah` — only this note's attendees used | E6 |
| TC-OWN-028 | Never guesses | F | P1 | `Priya` | A2 | Never returns a single Priya; candidates list complete | E6 |
| TC-OWN-029 | Exact duplicate attendee | E | P3 | `Priya` | `[Priya Shah, Priya Shah]` | `Priya Shah` (not ambiguous) | E6 |

## 3. Owner not in attendees (E7)

| ID | Scenario | Type | Pri | Owner phrase | Attendees | Expected result | Trace |
|---|---|---|---|---|---|---|---|
| TC-OWN-040 | Unknown first name | F | P1 | `Vikram` | A1 | `owner = Vikram`, `not_in_attendees = true` | E7 |
| TC-OWN-041 | Unknown full name | F | P1 | `Vikram Singh` | A1 | `owner = Vikram Singh`, flagged | E7 |
| TC-OWN-042 | Known first name, wrong last name | E | P1 | `Priya Patel` | A1 | ❓QA-15 Recommended: `Priya Patel` flagged not-in-attendees (do **not** map to Priya Shah) | E7 |
| TC-OWN-043 | Empty attendee list | E | P1 | `Priya` | `[]` | `Priya`, flagged not-in-attendees | E7, M2 |
| TC-OWN-044 | Partial first name | N | P2 | `Pri` | A1 | Not matched → `Pri`, flagged (no prefix matching on first name) | E7 |
| TC-OWN-045 | Last name only | E | P2 | `Shah` | A1 | ❓QA-16 Recommended: flagged not-in-attendees (no last-name matching) | E7 |
| TC-OWN-046 | Nickname | E | P3 | `Raj` (attendee `Rajesh Iyer`) | — | Flagged not-in-attendees (no nickname dictionary) | E7 |
| TC-OWN-047 | Team as owner | E | P2 | `Finance` | A1 | ❓QA-12 Flagged not-in-attendees | E7 |
| TC-OWN-048 | Multiple owners | E | P2 | `Priya and Rahul` | A1 | ❓QA-13 Not mapped to one person; flagged | — |

## 4. Name formats

| ID | Scenario | Type | Pri | Owner phrase | Attendees | Expected result | Trace |
|---|---|---|---|---|---|---|---|
| TC-OWN-060 | Attendee with middle name | E | P2 | `Priya` | `[Priya Ann Shah]` | `Priya Ann Shah` | M4 |
| TC-OWN-061 | Middle-name attendee, first+last given | E | P3 | `Priya Shah` | `[Priya Ann Shah]` | ❓QA-15 Recommended: `Priya Ann Shah` | M4 |
| TC-OWN-062 | Single-word attendee | E | P2 | `Anita` | `[Anita]` | `Anita` | M4 |
| TC-OWN-063 | Accented names | E | P2 | `José` | `[José Núñez]` | `José Núñez` | NFR-07 |
| TC-OWN-064 | Accent mismatch | E | P3 | `Jose` | `[José Núñez]` | ❓QA-17 Match or flag — defined behaviour | NFR-07 |
| TC-OWN-065 | Apostrophe / hyphen | E | P3 | `Zoë O'Brien`, `Anne-Marie` | matching attendee | Matched exactly | — |
| TC-OWN-066 | Reserved word as name | E | P3 | `Unassigned` | A1 | Treated as unknown name, flagged — must not be confused with reserved `unassigned` value | M4 §5 |

## 5. Downstream behaviour

| ID | Scenario | Type | Pri | Steps | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-OWN-080 | Unassigned item stored and visible | F | P1 | Ingest note with `- [ ] Share the slide deck`, then `list` | Item listed with owner `unassigned` | E3, Acceptance #4 |
| TC-OWN-081 | Ambiguous item stored and visible | F | P1 | Ingest A2 note with `Priya to …`, then `list` | Owner `ambiguous` shown with both candidates | E6, Acceptance #4 |
| TC-OWN-082 | Unassigned / ambiguous counted in summary | F | P1 | Ingest above notes | Summary `Unassigned items` and `Ambiguous owners` counts correct | M10 |
| TC-OWN-083 | Not-in-attendees flagged in summary | F | P1 | Ingest note with `Vikram to …` | Summary lists Vikram with file name | E7, M10 |
| TC-OWN-084 | No follow-up for unassigned/ambiguous | F | P2 | `followup unassigned`, `followup ambiguous` | No draft; clear message | Q5 |

---

## Questions affecting this module

- **QA-12:** Can a team/department be an owner?
- **QA-13:** Multiple owners on one line — how should we store them?
- **QA-15:** If the first name matches but the last name differs (`Priya Patel` vs attendee `Priya Shah`), keep as written and flag (recommended)?
- **QA-16:** Should a last name alone (`Shah to …`) be matched?
- **QA-17:** Should matching ignore accents (`Jose` = `José`)?
