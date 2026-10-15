# actiontrack — Decision Log

| Item | Detail |
|---|---|
| Status | **Accepted for v1** (2026-10-15). The stakeholder accepted the recommended defaults for all open questions. |
| Applies to | `plan.md`, `modules/*/spec.md`, `modules/*/plan.md`, `modules/*/test_cases.md` |
| How to read test cases | Every **❓QA-n** tag in `test_cases.md` resolves to the answer below. Use that answer as the expected result. |
| Change rule | Any decision can be revisited later. Update this file first, then the affected spec, plan and test cases. |

---

## 1. Requirement open questions (req §10)

| # | Question | Decision |
|---|---|---|
| Q1 | Date and attendee format in notes | Support `Date: YYYY-MM-DD` and `Attendees: A, B, C`, with label variations (any case, bold, extra spaces). Other formats → file skipped with a clear reason. Extend once sample notes are available. |
| Q2 / D3 | How the CLI reaches Gmail MCP | **Hand-off by default.** `followup` writes the draft payload (`outbox/*.json`) and the Claude session's Gmail connector calls `create_draft`. Direct MCP adapter is optional (`--transport mcp`). Never send. |
| Q3 | Email addresses | `people.yaml` (full name → email) |
| Q4 | Sender / CC | Sender = connected Gmail account; signature name from `people.yaml` `sender:` or `ACTIONTRACK_SENDER`; no CC |
| Q5 | Follow-ups for unassigned / ambiguous | None. Shown in `list` and the ingest summary only. |
| Q6 | "by Friday" written on a Friday | Next Friday (+7 days) |

## 2. QA questions

### CLI (M1)

| # | Decision |
|---|---|
| QA-1 | `--status` is case-insensitive (`OPEN` = `open`) |
| QA-2 | `done` takes exactly one ID |

### Note Reader (M2)

| # | Decision |
|---|---|
| QA-3 | `.md` matched case-insensitively (`.MD`, `.Md`); `.markdown` ignored |
| QA-4 | Top-level folder only (no sub-folders) |
| QA-5 | No sample notes yet. Use the Q1 formats; add more when samples arrive. |
| QA-6 | A date in the file name is **not** used; no `Date:` line → skipped (`no meeting date found`) |
| QA-7 | First `Date:` line in the header area (first 30 non-empty lines) wins |
| QA-8 | UTF-16 files with a BOM are read; other undecodable files → skipped (encoding error) |

### Item Extractor (M3)

| # | Decision |
|---|---|
| QA-9 | `- []` = open; `- [ x ]` = done; `- [  ]` = open. `[-]`, `[~]`, numbered `1. [ ]` and `[ ]` without a bullet are **ignored**. |
| QA-10 | Checkboxes inside fenced code blocks or block quotes are ignored |
| QA-11 | An owner must start with a capital letter, except after `@`. `@Priya Shah` → owner `Priya Shah`. An owner written at the end (`… (Priya)`) is not supported → unassigned. |
| QA-12 | Teams (`Finance to …`) are kept as the owner phrase and flagged "not in attendee list" |
| QA-13 | Multiple owners (`Priya and Rahul to …`) are kept as one phrase and flagged; not split |
| QA-14 | A non-date `by …` (`by the client`) stays in the task text. Due phrases are only taken from the end of the line. |

### Owner Resolver (M4)

| # | Decision |
|---|---|
| QA-15 | First name matches but last name differs (`Priya Patel` vs `Priya Shah`) → kept as written and flagged. `Priya Shah` **does** match attendee `Priya Ann Shah`. |
| QA-16 | A last name alone (`Shah`) is not matched → flagged |
| QA-17 | Accents are not ignored (`Jose` ≠ `José`) → flagged |

### Date Resolver (M5)

| # | Decision |
|---|---|
| QA-18 | `this Friday` and `next Friday` follow the same rule as `by Friday` (next Friday strictly after the meeting). The original phrase is kept for checking. |
| QA-19 | Weeks start on Monday (ISO) |
| QA-20 | `end of week` = Friday of the same ISO week, even for a Saturday/Sunday meeting (literal requirement rule) |
| QA-21 | `end of day` and `EOM` are supported; `e.o.d.` is not (→ null) |
| QA-22 | An explicit due date before the meeting date is kept as written |
| QA-23 | Slash dates are **DD/MM/YYYY**; 2-digit years are not supported (→ null) |
| QA-24 | `in N days`, `next month` and combined phrases (`EOD Friday`) → null, phrase kept |

### Deduplicator (M6)

| # | Decision |
|---|---|
| QA-25 | A task that is empty after cleaning is merged only on an exact `raw_text` match |
| QA-26 | False-merge guard is **on**: different capitalised words or numbers block a merge |
| QA-27 | An ambiguous item (`Priya`) and a later resolved one (`Priya Shah`) stay **separate** |
| QA-28 | A newer note with no or unclear due date **keeps** the existing date |
| QA-29 | Ingest never changes `done` back to `open` |
| QA-30 | `raw_text` and `meeting_title` keep the **first** values |
| QA-31 | Deleted notes: items kept. Renamed notes: the new file name is appended to `source_files`. |

### Storage (M7)

| # | Decision |
|---|---|
| QA-32 | JSON store (`actiontrack.json`); a 0-byte file = empty store, with a warning |

### Query (M8)

| # | Decision |
|---|---|
| QA-33 | `--owner priya` shows items of every matching Priya **plus** ambiguous items listing a Priya |
| QA-34 | No partial or last-name-only matching |
| QA-35 | `--due-before` is strictly before (the given date is excluded) |
| QA-36 | A repeated option → the last value wins |
| QA-37 | No `reopen` command in v1 |

### Follow-up (M9)

| # | Decision |
|---|---|
| QA-38 | Subject follows the template exactly: `Follow-up: your open action items (1)` |
| QA-39 | `people.yaml` lookup is case-insensitive; an invalid email format → clear error, no draft |
| QA-40 | `--dry-run` with no known email prints the email with `To: <unknown>` and a warning (exit 0) |
| QA-41 | Running `followup` twice creates two drafts (accepted) |

### Reporting (M10)

| # | Decision |
|---|---|
| QA-42 | Summary counts cover **this run** (items new or merged in this ingest) |
| QA-43 | Performance target: ingest of 50 notes ≤ 5 s on a normal laptop (CI threshold ×2) |

## 3. Architecture decisions

| # | Decision |
|---|---|
| D1 | JSON store, not SQLite |
| D2 | `argparse`, not `click` |
| D3 | `DraftCreator` interface; hand-off adapter is the default (see Q2) |
| D4 | DD/MM/YYYY (QA-23) |
| D5 | Weekday = strictly after the meeting date (Q6) |
| D6 | Ingest never re-opens done items (QA-29) |
| D7 | A newer note without a due date keeps the old date (QA-28) |
| D8 | `--due-before` is strict (QA-35) |
| D9 | Top-level folder only; `.md` case-insensitive (QA-3, QA-4) |
