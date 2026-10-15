# M9 — Follow-up Email Composer and Gmail Draft

| Item | Detail |
|---|---|
| Module | M9 |
| Source file | `actiontrack/followup.py` |
| Used by | M1 (`followup`) |
| Depends on | M7, M8, `people.yaml`, Gmail MCP connector |
| Milestone | 7 — `followup` |
| Source | Requirements §5 M9, §6.4, NFR-02, Q2–Q5, Acceptance #7 |

## 1. Purpose

Write one polite reminder email per person listing their open and overdue items, and save it as a **Gmail draft** for a human to review. The tool **never sends** email.

## 2. Flow

1. Resolve `<owner>` to one person (full or first name, case-insensitive) among stored owners.
   - Matches more than one person → error asking to be more specific, listing the matches (FR-FUP-05).
   - Matches nobody → error `No items found for '<owner>'.`
2. Collect that person's `open` items (FR-FUP-01). Overdue items first, then other open items.
3. No open/overdue items → print `<Name> has no open action items. No draft created.`, exit `0` (FR-FUP-06).
4. Look up the email address in `people.yaml` → missing: clear error (FR-FUP-08).
5. Compose the email (FR-FUP-02).
6. `--dry-run` → print the email, stop (FR-FUP-07).
7. Otherwise → create a Gmail draft (FR-FUP-03) and print a confirmation (draft ID / recipient).

## 3. Email template

```
To: priya.shah@example.com
Subject: Follow-up: your open action items (3)

Hi Priya,

A quick reminder of your action items from recent meetings:

Overdue
  • Send the revised quote (due 2026-10-09, from Weekly Sales Sync)

Open
  • Update pricing sheet (due 2026-10-20)
  • Review contract draft (no due date)

Please reply if any of these are already done or need a new date.

Thanks,
<sender name>
```

- Count in subject = overdue + open items.
- Greeting uses the first name.
- Task text capitalised for display.
- `due <date>` or `no due date`; `from <meeting title>` when known (otherwise the source file name). Shown on every line, open and overdue, so the reader always knows where a task came from.
- Omit the `Overdue` or `Open` section when it is empty.
- Within each section, sort by due date (no due date last).

## 4. People list (`people.yaml`)

```yaml
Priya Shah: priya.shah@example.com
Rahul Mehta: rahul.mehta@example.com
```

- Keys are full names exactly as they appear in attendee lists (Q3 working assumption).
- Missing file → clear error explaining how to create it.

## 5. Gmail draft integration

- Draft creation lives behind **one small function / interface** so the transport can change (Q2):

```python
class DraftCreator(Protocol):
    def create_draft(self, to: str, subject: str, body: str) -> str: ...  # returns draft id
```

- Possible implementations:
  - `McpDraftCreator` — calls the Gmail MCP server's **create draft** tool directly.
  - `HandoffDraftCreator` — writes the composed email (e.g. JSON) for the AI assistant in the session to create the draft.
  - `FakeDraftCreator` — used in tests.
- Sender = the Gmail account connected to the MCP connector; no CC (Q4).

## 6. Safety rule (NFR-02, FR-FUP-04)

- The code calls **only** the "create draft" action.
- **No send function exists** anywhere in the codebase.
- Add an automated test that scans the source for send-type calls (e.g. `send_message`, `send_draft`, `send`) on the Gmail client and fails if any are found.

## 7. Scope decisions

- `unassigned` and `ambiguous` items get **no** email (Q5). They appear only in `list` and the ingest summary.
- One draft per run of `followup <owner>` (one person).

## 8. Suggested interface

```python
def collect_items(store, owner_full_name, today) -> tuple[list[Item], list[Item]]: ...  # overdue, open
def compose_email(name, email, overdue, open_, sender_name) -> Email: ...
def load_people(path: Path) -> dict[str, str]: ...
def run_followup(owner, store, people, creator: DraftCreator, dry_run: bool, today) -> int: ...
```

## 9. Tests

- Email text matches the template (overdue first, counts, no-due-date wording).
- No open items → no draft created (fake creator not called).
- `--dry-run` → printed, creator not called.
- Ambiguous owner name → error, no draft.
- Missing email → error, no draft.
- Safety test: no send calls in source.

## 10. Acceptance criteria

- [ ] `followup <owner>` creates a Gmail draft with the correct open and overdue items (Acceptance #7).
- [ ] **No email is sent**, ever.
