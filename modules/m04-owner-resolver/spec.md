# M4 — Owner Resolver

| Item | Detail |
|---|---|
| Module | M4 |
| Source file | `actiontrack/owners.py` |
| Input from | M3 (`owner_phrase`), M2 (`attendees`) |
| Feeds | M6, M7 |
| Milestone | 4 — Owner + Date resolvers |
| Source | Requirements §5 M4, FR-ING-04, E3, E6, E7, Q5 |

## 1. Purpose

Turn an owner phrase (e.g. `Priya`) into one real person, using **that meeting's attendee list**. Never guess when it is unclear.

## 2. Resolution rules (in order)

| # | Situation | Result |
|---|---|---|
| 1 | No owner phrase | `owner = "unassigned"` (E3) |
| 2 | Phrase exactly matches an attendee full name (case-insensitive) | That attendee |
| 3 | Phrase is first name + last name or initial (`Priya S.`, `Priya Shah`) | The attendee whose first name matches and whose last name equals / starts with the given part |
| 4 | Phrase is a first name and **exactly one** attendee has it | That attendee — `Priya` + `[Priya Shah, Rahul Mehta]` → **Priya Shah** |
| 5 | Phrase is a first name and **two or more** attendees have it | `owner = "ambiguous"`, `owner_candidates = [all matches]` (E6) |
| 6 | No attendee matches | Keep the name **as written** and set `not_in_attendees = true` so M10 flags it (E7) |

Matching is case-insensitive and ignores surrounding whitespace and a leading `@`.

## 3. Output

| Field | Type | Example |
|---|---|---|
| `owner` | text | `Priya Shah` / `unassigned` / `ambiguous` / `Vikram` |
| `owner_candidates` | list | `["Priya Shah", "Priya Kumar"]` — only when ambiguous |
| `not_in_attendees` | bool | `true` when rule 6 applied |

### Suggested interface

```python
@dataclass
class OwnerResult:
    owner: str
    candidates: list[str]
    not_in_attendees: bool = False

def resolve_owner(owner_phrase: str | None, attendees: list[str]) -> OwnerResult: ...
```

## 4. Examples

| Owner phrase | Attendees | Result |
|---|---|---|
| `Priya` | Priya Shah, Rahul Mehta | Priya Shah |
| `Priya` | Priya Shah, Priya Kumar, Rahul Mehta | ambiguous → [Priya Shah, Priya Kumar] |
| `Priya S.` | Priya Shah, Priya Kumar | Priya Shah |
| `Priya Kumar` | Priya Shah, Priya Kumar | Priya Kumar |
| `rahul` | Priya Shah, Rahul Mehta | Rahul Mehta |
| `Vikram` | Priya Shah, Rahul Mehta | Vikram (flagged: not in attendees) |
| (none) | any | unassigned |

## 5. Notes

- `unassigned` and `ambiguous` are reserved values; a real person with these names is not supported.
- Ambiguous / unassigned items are stored and shown in `list` and the ingest summary but get **no follow-up email** (Q5 working assumption).
- Resolution uses only the attendees of the note the item came from, not a global people list.

## 6. Tests

- Every row in §4.
- Case-insensitivity and `@` prefix.
- Initial that matches both people (`Priya K.` vs `Priya Kumar`/`Priya Khan`) → ambiguous.

## 7. Acceptance criteria

- [ ] Owners resolved correctly in tests (Milestone 4).
- [ ] Same first name handled per E6; never guesses.
- [ ] Unknown owners are kept and flagged (E7).
