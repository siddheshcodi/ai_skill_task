# M3 — Action Item Extractor

| Item | Detail |
|---|---|
| Module | M3 |
| Source file | `actiontrack/extractor.py` |
| Input from | M2 (`Note`) |
| Feeds | M4 (owner phrase), M5 (due phrase), M6 (task text) |
| Milestone | 3 — Reader + Extractor |
| Source | Requirements §5 M3, FR-ING-03, E3, E9 |

## 1. Purpose

Find action items (checkbox lines) inside a note and split each one into **owner phrase**, **task text** and **due phrase**.

## 2. Checkbox detection

| Marker | Status |
|---|---|
| `- [ ]` | `open` |
| `- [x]`, `- [X]` | `done` |

Accept small variations:

- `*` or `-` (optionally `+`) as bullet: `* [ ]`, `- [ ]`
- Missing or extra spaces: `-[ ]`, `-  [ ]`, `- [ ]   text`
- Leading indentation (nested lists)

Suggested pattern (to refine against sample notes):

```regex
^\s*[-*+]\s*\[( |x|X)\]\s*(.+?)\s*$
```

- Lines that are not checkboxes are ignored (free-form text, headings, plain bullets) — E9.
- Checkbox lines with no text after the box are ignored.

## 3. Splitting a line

| Example line | Owner phrase | Task | Due phrase |
|---|---|---|---|
| `Priya to send the revised quote by Friday` | Priya | send the revised quote | by Friday |
| `Rahul will update the CRM by 2026-10-12` | Rahul | update the CRM | by 2026-10-12 |
| `@Anita book the demo room` | Anita | book the demo room | (none) |
| `Share the slide deck with the client` | (none) | share the slide deck with the client | (none) |

### Owner patterns

| Pattern | Example |
|---|---|
| `Name to …` | `Priya to send …` |
| `Name will …` | `Rahul will update …` |
| `@Name …` | `@Anita book …` |
| `Name: …` | `Priya: send …` |

- `Name` may be one or two words, or a first name + initial (`Priya S.`, `Priya Shah`) so M4 can use the extra detail.
- If no pattern matches, owner phrase = none (E3).

### Due phrase patterns

Look for a trailing phrase such as:

- `by <X>`, `on <X>`, `due <X>`, `before <X>`
- bare keywords: `today`, `tomorrow`, `EOD`, `EOW`, `end of week`, `end of month`, `next week`
- explicit dates: `2026-10-12`, `12/10/2026`, `Oct 12`

The due phrase is removed from the task text. M3 does **not** convert it to a date — that is M5's job. Unclear phrases (e.g. `by soon`) are still captured as a due phrase so M5 can keep the original wording (E5).

## 4. Output

| Field | Type | Example |
|---|---|---|
| `raw_text` | text | `Priya to send the revised quote by Friday` |
| `owner_phrase` | text or null | `Priya` |
| `task` | text | `send the revised quote` |
| `due_phrase` | text or null | `by Friday` |
| `status` | `open` / `done` | `open` |
| `line_number` | number | `14` (useful for debugging) |

### Suggested interface

```python
def extract_items(note: Note) -> list[RawItem]: ...
def split_line(text: str) -> tuple[str | None, str, str | None]: ...
```

## 5. Edge cases

| # | Case | Behaviour |
|---|---|---|
| E3 | No owner | `owner_phrase = None` |
| E5 | Unclear due phrase | Captured as-is, resolved later by M5 |
| E9 | Long or messy note | Only checkbox lines extracted |
| — | Words like "to"/"will" inside task text (e.g. `Send deck to client`) | Owner only detected at the **start** of the line and only for name-like words (capitalised), so `Send` is not treated as an owner |

## 6. Tests

- Every row of the table in §3.
- Each checkbox variation in §2 (open/done, `*`, missing spaces, indentation).
- Non-checkbox bullets ignored.
- Task containing "to"/"will" later in the sentence is not split wrongly.

## 7. Acceptance criteria

- [ ] All open and done checkbox lines are found (FR-ING-03).
- [ ] Owner, task and due phrase are split correctly for all supported patterns.
