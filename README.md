# actiontrack

A command-line tool that reads markdown meeting notes, collects every action
item, tracks who owns it and when it is due, and prepares follow-up emails as
**Gmail drafts** for a human to review. **It never sends email.**

```
notes/*.md ──▶ ingest ──▶ actiontrack.json ──▶ list / done
                                         └──▶ followup ──▶ Gmail draft
```

## Install

Requires Python 3.10 or newer. One command on Windows, macOS or Linux:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install .
actiontrack --help
```

## Quick start (5 minutes)

The `examples/` folder has three meeting notes, one broken note and a demo
people list. Run these from inside `examples/`.

**1. Collect the action items**

```
$ actiontrack ingest notes
Ingest complete
  Files read:                  3
  Files skipped:               1
  New items:                   8
  Duplicates merged:           4
  Unassigned items:            1
  Ambiguous owners:            1
  Owners not in attendees:     1

Skipped files:
  - notes/retro-draft.md: no meeting date found

Owners not in attendee list:
  - notes/2026-10-08-product-sync.md: "Vikram" (item 7)
```

Running it again is safe: nothing is duplicated and IDs never change.

**2. See what is open and what is late** (overdue depends on today's date;
this output is from 2026-10-15)

```
$ actiontrack list
ID  Owner                                Task                                  Due         Status   Source
--  -----------------------------------  ------------------------------------  ----------  -------  ------------------------------------
1   Priya Shah                           send the revised quote                2026-10-09  OVERDUE  2026-10-06-weekly-sales-sync.md (+1)
2   Rahul Mehta                          update the CRM                        2026-10-12  done     2026-10-06-weekly-sales-sync.md (+2)
3   Anita Rao                            book the demo room                    -           done     2026-10-06-weekly-sales-sync.md
4   unassigned                           Share the slide deck with the client  -           open     2026-10-06-weekly-sales-sync.md (+1)
5   Priya Kumar                          draft the release notes               2026-10-12  OVERDUE  2026-10-08-product-sync.md
6   ambiguous: Priya Shah / Priya Kumar  review the launch checklist           -           open     2026-10-08-product-sync.md
7   Vikram                               approve the Q4 budget                 -           open     2026-10-08-product-sync.md
8   Anita Rao                            prepare the pricing sheet             2026-10-14  OVERDUE  2026-10-13-weekly-sales-sync.md

8 items, 3 overdue
```

What happened here:

- "Priya to send the revised quote **by Friday**" in the Tuesday 2026-10-06
  meeting became **2026-10-09**: dates are relative to the meeting, not today.
- The quote and the CRM task appear in several meetings but are stored once.
  The CRM task is `done` because a later note ticked it.
- "**Priya K.**" was matched to Priya Kumar; plain "**Priya**" in a meeting
  with two Priyas is marked `ambiguous` instead of guessing.
- Vikram was not in that meeting's attendee list, so he is flagged.

**3. Filter**

```
$ actiontrack list --status overdue
$ actiontrack list --owner priya              # both Priyas + items that may be theirs
$ actiontrack list --owner "Rahul Mehta" --status open --due-before 2026-10-31
```

**4. Close a task**

```
$ actiontrack done 1
Item 1 marked as done: send the revised quote
```

**5. Prepare a follow-up email**

```
$ actiontrack followup "Priya Kumar" --people people.example.yaml --dry-run
To: priya.kumar@example.com
Subject: Follow-up: your open action items (1)

Hi Priya,

A quick reminder of your action items from recent meetings:

Overdue
  • Draft the release notes (due 2026-10-12, from Product Sync)

Please reply if any of these are already done or need a new date.

Thanks,
Team Lead

(dry run: no draft created)

$ actiontrack followup "Priya Kumar" --people people.example.yaml
Draft for Priya Kumar <priya.kumar@example.com> prepared: outbox/20261015-165308-priya-kumar.json
Ask Claude to create the Gmail draft from this file. It is saved as a draft for you to review; nothing is sent.
```

Then, in Claude Code: *"Create Gmail drafts from the files in outbox/"*. The
draft appears in your Gmail **Drafts** folder; you review and send it yourself.
`followup priya` on its own is refused here because two people are called
Priya; use the full name.

## Commands

| Command | What it does |
|---|---|
| `actiontrack ingest <folder>` | Read every `.md` note in the folder (not sub-folders), extract action items, merge duplicates, save. Bad notes are skipped and listed with a reason. |
| `actiontrack list [--owner NAME] [--status open\|done\|overdue] [--due-before YYYY-MM-DD]` | Show items. Filters combine. `--owner` takes a full or first name (any case), or `unassigned` / `ambiguous`. `--due-before` excludes that date. |
| `actiontrack done <id>` | Mark one item done. Already done is fine; an unknown ID is an error. |
| `actiontrack followup <owner> [--dry-run] [--people PATH] [--outbox PATH]` | One reminder email for that person's open items, overdue first, saved as a draft file for Gmail. `--dry-run` only prints it. |

Options for every command: `--store PATH` (default `./actiontrack.json`),
`--debug` (full error details), `--help`, `--version`.

Exit codes: `0` success · `1` failure · `2` wrong usage · `130` cancelled.

## Writing notes

```markdown
# Weekly Sales Sync
Date: 2026-10-06
Attendees: Priya Shah, Rahul Mehta, Anita Rao

## Action items
- [ ] Priya to send the revised quote by Friday
- [x] Anita to book the demo room
```

- **Header:** `Date: YYYY-MM-DD` and `Attendees: Name, Name` near the top
  (any case, bold allowed). A note without a valid date is skipped.
- **Items:** `- [ ]` open, `- [x]` done. `* [ ]`, `-[ ]` and indented items
  work too; checkboxes in code blocks and quotes are ignored.
- **Owner** at the start: `Priya to …`, `Priya will …`, `@Priya …`,
  `Priya: …`. Use a last name or initial (`Priya S.`) when two people share
  a first name. No owner → `unassigned`.
- **Due date** at the end of the line:

| You write | Due date (meeting on Tue 2026-10-06) |
|---|---|
| `by 2026-10-12`, `by 12/10/2026` (day/month), `by Oct 12` | 2026-10-12 |
| `by Friday`, `on Monday`, `next Friday` | next such day **after** the meeting (Fri 2026-10-09) |
| `today`, `EOD` / `tomorrow` | 2026-10-06 / 2026-10-07 |
| `next week` / `end of week`, `EOW` | Monday 2026-10-12 / Friday 2026-10-09 |
| `end of month`, `EOM` | 2026-10-31 |
| `soon`, `ASAP`, anything else | no date (the phrase is kept) |

Items with no due date are never overdue. All rules and their reasons are in
`decisions.md`.

## Follow-up emails and safety

- Email addresses come from `people.yaml`: copy `people.yaml.example`, fill
  in real addresses (the file is git-ignored). The optional `sender:` line or
  the `ACTIONTRACK_SENDER` environment variable sets the signature.
- `followup` writes `outbox/<time>-<name>.json`; Claude's Gmail connector
  turns it into a **draft**. Unassigned and ambiguous items get no email.
- actiontrack has **no send function at all**. A test scans the source code
  and fails the build if any send-type call or mail library ever appears.

## Files it creates

| File | Purpose |
|---|---|
| `actiontrack.json` | The store. Written atomically; IDs never change. |
| `actiontrack.json.bak` | The previous version, kept on every save. |
| `outbox/*.json` | Draft emails waiting to be created in Gmail. |

Your meeting notes are only ever read, never changed. Set `NO_COLOR=1` to
turn off red overdue rows.

## Development

```bash
pip install -e ".[dev]"
pytest                         # full test suite
pytest --cov                   # coverage (CI requires 90%)
python tools/traceability.py   # maps all 514 documented test cases to tests
ruff check . && ruff format --check .
```

CI (`.github/workflows/ci.yml`) runs all of this on Windows, macOS and
Linux with Python 3.10, 3.12 and 3.14.

| Document | Content |
|---|---|
| `actiontrack-requirements.md` | Requirements |
| `plan.md` | Architecture and delivery plan |
| `decisions.md` | Answers to every open question (e.g. DD/MM dates) |
| `modules/<module>/spec.md` | Module specification |
| `modules/<module>/plan.md` | Module implementation plan |
| `modules/<module>/test_cases.md` | Module test cases |

```
actiontrack/
  cli.py       M1  commands, validation, exit codes
  reader.py    M2  find notes, read date and attendees
  extractor.py M3  find checkbox items, split owner / task / due
  owners.py    M4  match owner phrase to an attendee
  dates.py     M5  due phrase -> calendar date (relative to meeting)
  dedupe.py    M6  merge repeated tasks across meetings
  store.py     M7  JSON store, stable IDs, atomic save
  query.py     M8  list filters, overdue rule, table, done
  followup.py  M9  collect open/overdue items, compose email
  people.py    M9  people.yaml (name -> email)
  drafts.py    M9  draft hand-off (create only, never send)
  report.py    M10 ingest summary
  ingest.py        ingest pipeline (per-note error boundary)
  models.py        shared data types
  errors.py        error types -> exit codes
tests/
  unit/            per-module tests
  integration/     ingest pipeline, CLI and acceptance tests
  safety/          never-send checks (NFR-02)
  fixtures/        sample notes      golden/  expected outputs
tools/
  traceability.py  test case -> test mapping
examples/          demo notes and people list
```

## Status

All nine milestones are complete and every acceptance criterion in the
requirements is met, including a real Gmail draft check (draft created,
nothing sent).
