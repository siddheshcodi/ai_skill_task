# actiontrack: Requirements Document

| Item | Detail |
|---|---|
| Project | actiontrack (command-line tool) |
| Document type | Software Requirements |
| Version | 1.1 (open questions marked Yes/No with working assumptions) |
| Status | Draft for review |

---

## 1. Introduction

### 1.1 The problem

Our team writes meeting notes as markdown (`.md`) files. These notes contain action items, which are tasks that someone agreed to do, such as *"Priya to send the revised quote by Friday."*

Today, nobody collects these tasks in one place. As a result:

- Tasks get forgotten.
- Nobody knows which tasks are late.
- Reminder (follow-up) emails are sent late or never.

### 1.2 The solution

Build a small command-line tool called **actiontrack** that:

1. Reads all meeting notes in a folder.
2. Finds every action item and saves it with its owner, task, due date, source file and status.
3. Lets people list, filter and close tasks.
4. Writes a follow-up email for each person and saves it as a **Gmail draft** for a human to review. The tool **never sends** emails by itself.

### 1.3 Who will use it

| User | What they do with it |
|---|---|
| Team lead / project manager | Loads notes, checks overdue items, prepares follow-up emails |
| Team member | Checks their own open tasks, marks tasks as done |

### 1.4 In scope

- Reading `.md` meeting notes from a local folder.
- Extracting, storing and tracking action items.
- Four commands: `ingest`, `list`, `done`, `followup`.
- Creating Gmail **drafts** through the Gmail MCP connector.

### 1.5 Out of scope (not required)

- Sending emails automatically.
- A web or mobile interface.
- Editing the original meeting note files.
- Reading notes from Google Drive, Notion or other online sources.
- Multi-user logins or permissions.

---

## 2. Key terms

| Term | Meaning |
|---|---|
| Meeting note | One `.md` file describing one meeting |
| Action item | A checkbox line in a note, e.g. `- [ ] Priya to send the quote by Friday` |
| Owner | The person responsible for the action item |
| Due date | The real calendar date the task must be done by |
| Source file | The note file(s) where the item was found |
| Open | Task is not finished |
| Done | Task is finished |
| Overdue | Task is still open **and** its due date is before today |
| Malformed note | A file the tool cannot read correctly (see section 6.4) |
| Store | The file where actiontrack saves all items (e.g. JSON or SQLite) |
| Draft | An unsent email saved in Gmail's Drafts folder |

---

## 3. Input: what a meeting note looks like

Each note is expected to contain:

1. **Meeting date**, e.g. `Date: 2026-10-06`
2. **Attendees**, e.g. `Attendees: Priya Shah, Priya Kumar, Rahul Mehta`
3. **Free-form text**: normal discussion notes (ignored by the tool)
4. **Action items**: checkbox lines

Example:

```markdown
# Weekly Sales Sync
Date: 2026-10-06
Attendees: Priya Shah, Rahul Mehta, Anita Rao

## Discussion
Client asked for a lower price on the annual plan...

## Action items
- [ ] Priya to send the revised quote by Friday
- [ ] Rahul will update the CRM by 2026-10-12
- [x] Anita to book the demo room
- [ ] Share the slide deck with the client
```

> **Note:** The exact format must be confirmed by checking the sample `notes/` folder (see Open Questions, section 10). The parser should be flexible, because real notes are messy.

---

## 4. System overview

The tool is split into small modules. Each module does one job.

```
                 ┌────────────────────┐
  notes/*.md ──▶ │  M2 Note Reader     │──▶ skipped files ──▶ M10 Report
                 └─────────┬──────────┘
                           ▼
                 ┌────────────────────┐
                 │ M3 Item Extractor   │  finds "- [ ]" lines
                 └─────────┬──────────┘
                           ▼
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
 M4 Owner Resolver   M5 Date Resolver    (task text)
       └───────────────────┼───────────────────┘
                           ▼
                 ┌────────────────────┐
                 │ M6 Deduplicator     │
                 └─────────┬──────────┘
                           ▼
                 ┌────────────────────┐
                 │ M7 Storage          │◀──── M8 Query (list) / done
                 └─────────┬──────────┘
                           ▼
                 ┌────────────────────┐
                 │ M9 Follow-up Email  │──▶ Gmail MCP ──▶ Gmail Draft
                 └────────────────────┘

  M1 CLI sits on top and calls these modules for each command.
```

---

## 5. Modules and what to build

### M1. CLI (command-line interface)

**Purpose:** The entry point. Reads the command the user typed and calls the right module.

**What to build:**
- A program named `actiontrack` with four sub-commands: `ingest`, `list`, `done`, `followup`.
- `--help` text for every command.
- Clear error messages for wrong input (e.g. unknown command, bad date format).
- Exit code `0` on success and non-zero on failure.

**Suggested tools:** Python with `argparse` or `click`.

---

### M2. Note Reader

**Purpose:** Open each `.md` file and read the header information.

**What to build:**
- Find all `.md` files in the given folder (ignore other file types).
- Read each file safely (handle encoding errors).
- Extract the **meeting date** and the **attendee list**.
- If a file is malformed, do **not** crash. Add it to the "skipped" list with a reason and move to the next file.

**Output:** For each good file: file name, meeting date, attendee list, file text.

---

### M3. Action Item Extractor

**Purpose:** Find action items inside a note.

**What to build:**
- Detect checkbox lines:
  - `- [ ]` means **open**
  - `- [x]` or `- [X]` means **done**
- Also accept small variations, such as `* [ ]`, `-[ ]` or `- [ ]` with extra spaces.
- Split each line into three parts: **owner phrase**, **task text** and **due phrase**.

| Example line | Owner | Task | Due phrase |
|---|---|---|---|
| `Priya to send the revised quote by Friday` | Priya | send the revised quote | by Friday |
| `Rahul will update the CRM by 2026-10-12` | Rahul | update the CRM | by 2026-10-12 |
| `@Anita book the demo room` | Anita | book the demo room | (none) |
| `Share the slide deck with the client` | (none) | share the slide deck with the client | (none) |

Common owner patterns to support: `Name to …`, `Name will …`, `@Name …`, `Name: …`.

---

### M4. Owner Resolver

**Purpose:** Turn the owner phrase into one real person.

**What to build:**
- Match the owner name against **that meeting's attendee list** to get the full name.
  - `Priya` + attendees `[Priya Shah, Rahul Mehta]` → **Priya Shah**
- Handle **two people with the same first name**:
  - If only one "Priya" attended that meeting, pick her.
  - If the note uses a last name or initial (`Priya S.`, `Priya Shah`), use it.
  - If both Priyas attended and the note says only "Priya", mark the owner as **ambiguous** and keep both candidate names. Do not guess.
- If no owner is found, set owner to **unassigned**.

---

### M5. Date Resolver

**Purpose:** Turn a due phrase into a real calendar date, **relative to the meeting date** (not today's date).

**What to build:** Support at least these phrases:

| Due phrase | Rule | Example (meeting on Tue 2026-10-06) |
|---|---|---|
| `2026-10-12`, `12/10/2026`, `Oct 12` | Use that exact date | 2026-10-12 |
| `by Friday`, `on Monday` | Next matching weekday **after** the meeting date | Fri 2026-10-09 |
| `tomorrow` | Meeting date + 1 day | 2026-10-07 |
| `today`, `EOD` | Meeting date | 2026-10-06 |
| `next week` | Monday of the following week | 2026-10-12 |
| `end of week` / `EOW` | Friday of the same week | 2026-10-09 |
| `end of month` | Last day of that month | 2026-10-31 |
| No phrase / unclear phrase | Due date = **none**; keep the original text | none |

- Always store dates in `YYYY-MM-DD` format.
- Keep the original phrase (e.g. "by Friday") so a human can check it.

---

### M6. Deduplicator

**Purpose:** Make sure the same task, repeated in several meetings, is stored **only once**.

**What to build:**
- Two items are the **same** when:
  - they have the same resolved owner, **and**
  - their task text is the same or very similar after cleaning (lowercase, remove punctuation, remove the due phrase, remove extra spaces). A similarity score of about 85% or more is a good starting rule.
- When a duplicate is found:
  - Do not create a new item.
  - Add the new file to the item's list of **source files**.
  - If the newer meeting gives a different due date, use the **newest meeting's** due date.
  - If any newer note marks the task `[x]`, set the status to **done**.
- Running `ingest` twice on the same folder must **not** create duplicates. The command must be safe to repeat.

---

### M7. Storage

**Purpose:** Save all items so they survive between runs.

**What to build:**
- A single local store file, e.g. `actiontrack.json` or `actiontrack.db` (SQLite).
- Each item gets a **unique, stable ID** (1, 2, 3 …). IDs must not change after re-ingesting.
- Functions to: add item, update item, find item by ID, load all items.

**Data model (one action item):**

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | number | `12` | Unique, never reused |
| `owner` | text | `Priya Shah` | or `unassigned` / `ambiguous` |
| `owner_candidates` | list | `["Priya Shah", "Priya Kumar"]` | Only when ambiguous |
| `task` | text | `send the revised quote` | Cleaned task text |
| `raw_text` | text | `Priya to send the revised quote by Friday` | Original line |
| `due_date` | date or null | `2026-10-09` | `null` if unknown |
| `due_phrase` | text | `by Friday` | Original wording |
| `status` | `open` / `done` | `open` | Overdue is calculated, not stored |
| `source_files` | list | `["2026-10-06-sales.md"]` | All notes it appeared in |
| `meeting_date` | date | `2026-10-06` | First meeting it appeared in |
| `created_at` / `updated_at` | timestamp | | For tracking |

---

### M8. Query and Status Update

**Purpose:** Show items and mark them done.

**What to build:**
- **List with filters** (filters can be combined):
  - `--owner <name>`: match on full or first name (case-insensitive)
  - `--status open|done|overdue`
  - `--due-before <YYYY-MM-DD>`
- **Overdue rule:** `status == open` **and** `due_date < today`. Items with no due date are never overdue.
- Output as a readable table: ID, owner, task, due date, status, source file.
- Overdue items should stand out (e.g. a `OVERDUE` label or red text).
- **Mark done:** change one item's status to `done` by ID.

---

### M9. Follow-up Email Composer and Gmail Draft

**Purpose:** Write one reminder email per person and save it as a Gmail draft.

**What to build:**
- Collect the person's **open** and **overdue** items. Overdue items are listed first.
- Build a short, polite email:

```
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

- Look up the person's email address from a simple people list (e.g. `people.yaml`, see Open Questions).
- Create the email as a **Gmail draft** using the Gmail MCP connector.
- **Safety rule:** the tool must only call the "create draft" action. It must **never** call any "send" action.
- `--dry-run` option: print the email to the screen without creating a draft.
- If the person has no open or overdue items, print a message and create **no** draft.

---

### M10. Error Handling and Reporting

**Purpose:** Make problems visible without crashing.

**What to build:**
- At the end of `ingest`, print a summary:

```
Ingest complete
  Files read:         31
  Files skipped:       3
  New items:          42
  Duplicates merged:  11
  Unassigned items:    4
  Ambiguous owners:    2

Skipped files:
  - notes/meeting_17.md: no meeting date found
  - notes/meeting_22.md: file is empty
  - notes/meeting_29.md: cannot read file (encoding error)
```

- Unexpected errors in one file must never stop the processing of other files.

---

## 6. Functional requirements by command

### 6.1 `actiontrack ingest <folder>`

| ID | Requirement |
|---|---|
| FR-ING-01 | Read every `.md` file in the folder. |
| FR-ING-02 | Extract meeting date and attendees from each file. |
| FR-ING-03 | Extract all action items (open and done). |
| FR-ING-04 | Resolve owner, task and due date for each item. |
| FR-ING-05 | Merge duplicate items across meetings. |
| FR-ING-06 | Save items to the store with stable IDs. |
| FR-ING-07 | Skip malformed files and report them with a reason. |
| FR-ING-08 | Running ingest again on the same folder creates no duplicates. |
| FR-ING-09 | Print a summary at the end (see M10). |

### 6.2 `actiontrack list [filters]`

| ID | Requirement |
|---|---|
| FR-LST-01 | With no filters, show all items. |
| FR-LST-02 | `--owner` shows only that person's items. |
| FR-LST-03 | `--status open|done|overdue` filters by status. |
| FR-LST-04 | `--due-before <date>` shows items due before that date. |
| FR-LST-05 | Filters can be combined. |
| FR-LST-06 | Overdue items are clearly marked. |
| FR-LST-07 | An invalid date or status gives a clear error message. |

### 6.3 `actiontrack done <id>`

| ID | Requirement |
|---|---|
| FR-DON-01 | Mark the item with that ID as done. |
| FR-DON-02 | If the ID does not exist, show an error. |
| FR-DON-03 | If the item is already done, say so without failing. |

### 6.4 `actiontrack followup <owner>`

| ID | Requirement |
|---|---|
| FR-FUP-01 | Collect the owner's open and overdue items. |
| FR-FUP-02 | Compose one email for that owner. |
| FR-FUP-03 | Create a Gmail draft through the Gmail MCP connector. |
| FR-FUP-04 | Never send the email. |
| FR-FUP-05 | If the owner name matches more than one person, ask the user to be more specific. |
| FR-FUP-06 | If the owner has no open items, create no draft. |
| FR-FUP-07 | `--dry-run` prints the email instead of creating a draft. |
| FR-FUP-08 | If the owner has no known email address, show a clear error. |

---

## 7. Edge cases (must handle)

| # | Case | Expected behaviour |
|---|---|---|
| E1 | Same task repeated in several meetings | Stored once; all source files recorded; newest due date used |
| E2 | Task marked done in a later meeting | Status becomes `done` |
| E3 | Item with no owner | Saved with owner `unassigned`; shown in `list` |
| E4 | Item with no due date | Saved with `due_date = null`; never overdue |
| E5 | Unclear due phrase (e.g. "soon") | `due_date = null`; original phrase kept |
| E6 | Two people with the same first name | Resolved using attendees; otherwise marked `ambiguous` |
| E7 | Owner not in attendee list | Keep the name as written and flag it in the summary |
| E8 | Malformed note (no date, empty, unreadable) | Skipped and reported; other files still processed |
| E9 | Very long or messy note | Parsed normally; non-action text ignored |
| E10 | Ingest run twice | No new duplicates; IDs unchanged |
| E11 | Non-`.md` files in folder | Ignored |

---

## 8. Non-functional requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-01 | Reliability | The tool never crashes because of one bad file. |
| NFR-02 | Safety | Emails are only ever saved as drafts. No send action exists in the code. |
| NFR-03 | Performance | Ingesting about 30–50 notes takes only a few seconds. |
| NFR-04 | Usability | Every command has `--help`; error messages say what went wrong and how to fix it. |
| NFR-05 | Maintainability | Code is split into the modules above, so each part can be tested alone. |
| NFR-06 | Testability | Each edge case in section 7 has at least one automated test. |
| NFR-07 | Portability | Runs on Windows, macOS and Linux with one install command. |

---

## 9. Suggested project structure

```
actiontrack/
├── actiontrack/
│   ├── cli.py            # M1  commands and arguments
│   ├── reader.py         # M2  read files, date, attendees
│   ├── extractor.py      # M3  find checkbox items
│   ├── owners.py         # M4  owner resolution
│   ├── dates.py          # M5  due date resolution
│   ├── dedupe.py         # M6  duplicate detection
│   ├── store.py          # M7  save/load items
│   ├── query.py          # M8  list filters, done
│   ├── followup.py       # M9  email text + Gmail draft
│   └── report.py         # M10 ingest summary
├── tests/
│   ├── fixtures/         # small sample notes for each edge case
│   └── test_*.py
├── people.yaml           # name → email mapping
├── README.md
└── pyproject.toml
```

---

## 10. Open questions (confirm with the instructor)

The column **"Answered in given requirement?"** shows whether the original task description already answers the question.
**Yes** = the requirement answers it. **No** = the requirement does not answer it, so we use the working assumption until it is confirmed.

| # | Question | Answered in given requirement? | What the requirement says today | Working assumption (until confirmed) | Why it matters |
|---|---|---|---|---|---|
| Q1 | What is the exact date and attendee format in the sample notes? | **No** | Only says each note *has* a date and attendees. No format given. | Check the sample `notes/` folder and support the formats found there (e.g. `Date: YYYY-MM-DD`, `Attendees: A, B, C`). | Decides how M2 is written |
| Q2 | How should the CLI connect to Gmail MCP: call the MCP server directly, or prepare the email and let the AI assistant in the session create the draft? | **No** | Says the draft is created "through the Gmail MCP connector", but not *how* the CLI talks to it. | Build the email text in the CLI; keep the draft-creation step in one small function so either approach can be plugged in. | Decides how M9 is written |
| Q3 | Where do email addresses come from? | **No** | Not mentioned. Notes only contain names. | Use a `people.yaml` file that maps full names to email addresses. | Needed for the draft's "To" field |
| Q4 | Who is the email sender, and should the team lead be in CC? | **No** | Not mentioned. | Sender = the Gmail account connected to the MCP connector. No CC. | Email content |
| Q5 | Should `unassigned` and `ambiguous` items get a follow-up email (e.g. to the meeting organiser)? | **No** | `followup` works per owner only. Items with no owner are not covered. | No email for these items. They are shown in `list` and in the ingest summary for manual handling. | Follow-up scope |
| Q6 | If "by Friday" is written on a Friday, is it the same day or next Friday? | **No** | Only says the due date must be "resolved to a real date". | Next Friday (the following week). | Date rule in M5 |

**Summary:** 0 of 6 questions are answered by the given requirement. All six use the working assumptions above until confirmed.

---

## 11. Assumptions

- Notes are in English.
- Each note describes exactly one meeting with one date.
- "Today" for overdue checks is the computer's current date.
- One store file is used by one person at a time (no shared editing).

---

## 12. Delivery plan (milestones)

| # | Milestone | Done when |
|---|---|---|
| 1 | Explore sample notes | Formats and malformed patterns are written down |
| 2 | Project setup + CLI skeleton (M1) | `actiontrack --help` works |
| 3 | Reader + Extractor (M2, M3) | Items printed from one note |
| 4 | Owner + Date resolvers (M4, M5) | Owners and real dates resolved correctly in tests |
| 5 | Dedupe + Storage (M6, M7) | `ingest` works on the full folder; re-run adds no duplicates |
| 6 | `list` and `done` (M8) | All filters work; overdue shown |
| 7 | `followup` (M9) | Draft appears in Gmail; nothing sent |
| 8 | Reporting + tests (M10) | Summary printed; all edge-case tests pass |
| 9 | README + demo | Someone else can install and run it |

---

## 13. Acceptance criteria (definition of done)

The project is complete when:

1. `ingest` processes the full sample `notes/` folder without crashing and lists all skipped files with reasons.
2. Duplicate items appear only once in `list`.
3. Due dates like "by Friday" are converted to the correct real date based on the meeting date.
4. Items with no owner, no due date or an ambiguous owner are stored and visible.
5. `list` filters (`--owner`, `--status`, `--due-before`) work alone and together.
6. `done <id>` updates the item, and the change is visible in `list`.
7. `followup <owner>` creates a Gmail draft with the correct open and overdue items, and **no email is sent**.
8. All edge cases in section 7 are covered by automated tests that pass.
