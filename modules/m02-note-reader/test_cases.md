# M2 — Note Reader: Test Cases

| Item | Detail |
|---|---|
| Module | M2 Note Reader (`actiontrack/reader.py`) |
| Covers | §3, §5 M2, FR-ING-01, FR-ING-02, FR-ING-07, E8, E9, E11, NFR-01, NFR-03, Q1 |
| Test levels | Unit (`read_notes(folder)` against fixture folders) |
| Fixtures | `tests/fixtures/reader/<case>/` — one small folder per scenario |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

Base valid note (`valid.md`) used unless stated otherwise:

```markdown
# Weekly Sales Sync
Date: 2026-10-06
Attendees: Priya Shah, Rahul Mehta, Anita Rao

## Action items
- [ ] Priya to send the revised quote by Friday
```

---

## 1. File discovery

| ID | Scenario | Type | Pri | Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-RDR-001 | Folder with several `.md` files | F | P1 | 3 valid notes | All 3 returned as good notes | FR-ING-01 |
| TC-RDR-002 | Non-`.md` files ignored | E | P1 | `a.md`, `b.txt`, `c.pdf`, `d.docx`, `e.md.bak` | Only `a.md` read; others not read **and not** counted as skipped | E11 |
| TC-RDR-003 | Upper-case extension | E | P2 | `NOTES.MD`, `Notes.Md` | ❓QA-3 Recommended: treated as `.md` (Windows users) | E11 |
| TC-RDR-004 | `.markdown` extension | E | P3 | `x.markdown` | ❓QA-3 Ignored (only `.md` in scope) | E11 |
| TC-RDR-005 | Sub-folders | E | P2 | `notes/2026/oct/a.md` | ❓QA-4 Recommended: not read (top-level only) — behaviour must be documented | FR-ING-01 |
| TC-RDR-006 | Empty folder | E | P1 | No files | Returns 0 notes, 0 skipped; no error | FR-ING-01 |
| TC-RDR-007 | Folder with only non-`.md` files | E | P2 | `a.txt`, `b.csv` | 0 notes, 0 skipped | E11 |
| TC-RDR-008 | Hidden / temp files | E | P3 | `.~lock.a.md#`, `.a.md` | Not read, or skipped with reason — never crash | NFR-01 |
| TC-RDR-009 | Stable processing order | F | P2 | Files `c.md`, `a.md`, `b.md` | Returned in sorted order every run | E10 (stable IDs) |
| TC-RDR-010 | File names with spaces / unicode | E | P2 | `Sales sync – Oct.md`, `réunion.md` | Read normally; name shown correctly | NFR-07 |

## 2. Meeting date extraction

| ID | Scenario | Type | Pri | Input line | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-RDR-020 | Standard date | F | P1 | `Date: 2026-10-06` | `meeting_date = 2026-10-06` | FR-ING-02 |
| TC-RDR-021 | Label case-insensitive | E | P2 | `date: 2026-10-06`, `DATE: 2026-10-06` | Parsed | Q1, §3 note |
| TC-RDR-022 | Bold label | E | P2 | `**Date:** 2026-10-06` | Parsed | Q1 |
| TC-RDR-023 | Extra / missing spaces | E | P2 | `Date:2026-10-06`, `Date :   2026-10-06  ` | Parsed | Q1 |
| TC-RDR-024 | Alternative date formats | E | P2 | `Date: 06/10/2026`, `Date: Oct 6, 2026`, `Date: 6 October 2026` | ❓QA-5 Supported if found in sample notes; otherwise skipped with clear reason — never wrong date | Q1 |
| TC-RDR-025 | Date only in file name | E | P2 | File `2026-10-06-sales.md` without `Date:` line | ❓QA-6 Recommended: skip "no meeting date found" (do not guess) | E8 |
| TC-RDR-026 | Missing date line | N | P1 | Note without `Date:` | Skipped, reason `no meeting date found` | E8, FR-ING-07 |
| TC-RDR-027 | Invalid calendar date | N | P1 | `Date: 2026-02-30`, `Date: 2026-13-01` | Skipped, reason `invalid meeting date '2026-02-30'` | E8 |
| TC-RDR-028 | Empty date value | N | P2 | `Date:` | Skipped with reason | E8 |
| TC-RDR-029 | Two `Date:` lines | E | P2 | `Date: 2026-10-06` … later `Date: 2026-10-08` | ❓QA-7 Recommended: first one in header wins; consistent result | §11 one date per note |
| TC-RDR-030 | "Date" word inside discussion | E | P2 | Header `Date: 2026-10-06`; body `Next Date: TBD` | Meeting date = 2026-10-06; body line ignored | E9 |
| TC-RDR-031 | Leap day | E | P3 | `Date: 2028-02-29` | Parsed | — |

## 3. Attendee extraction

| ID | Scenario | Type | Pri | Input line | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-RDR-040 | Standard list | F | P1 | `Attendees: Priya Shah, Rahul Mehta, Anita Rao` | 3 names, trimmed | FR-ING-02 |
| TC-RDR-041 | Label variants | E | P2 | `attendees:`, `**Attendees:**`, `Attendees :` | Parsed | Q1 |
| TC-RDR-042 | Extra spaces / trailing comma | E | P2 | `Attendees:  Priya Shah ,Rahul Mehta,  ,` | `["Priya Shah", "Rahul Mehta"]` (no empty entries) | M2 §5 |
| TC-RDR-043 | Single attendee | E | P3 | `Attendees: Priya Shah` | `["Priya Shah"]` | — |
| TC-RDR-044 | Same first name twice | F | P1 | `Attendees: Priya Shah, Priya Kumar, Rahul Mehta` | Both Priyas kept as separate entries | E6 |
| TC-RDR-045 | Exact duplicate name | E | P3 | `Attendees: Priya Shah, Priya Shah` | De-duplicated to one entry | E6 |
| TC-RDR-046 | Attendees as bullet list | E | P2 | `Attendees:` followed by `- Priya Shah` lines | ❓QA-5 Supported if present in sample notes | Q1 |
| TC-RDR-047 | Other separators | E | P3 | `Attendees: Priya Shah; Rahul Mehta` / `… and Rahul Mehta` | ❓QA-5 Behaviour defined from sample notes | Q1 |
| TC-RDR-048 | Missing attendees line | E | P1 | Date present, no `Attendees:` | Note read, `attendees = []` (not skipped) — owners then flagged E7 | M2 §6 assumption |
| TC-RDR-049 | Unicode names | E | P2 | `Attendees: José Núñez, Zoë O'Brien` | Kept exactly | NFR-07 |

## 4. Malformed / unreadable files

| ID | Scenario | Type | Pri | Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-RDR-060 | Empty file (0 bytes) | N | P1 | `empty.md` | Skipped, `file is empty` | E8 |
| TC-RDR-061 | Whitespace-only file | N | P1 | Only spaces/newlines | Skipped, `file is empty` | E8 |
| TC-RDR-062 | Non-UTF-8 bytes | N | P1 | File with invalid UTF-8 (e.g. `0xFF 0xFE` junk) | Skipped, `cannot read file (encoding error)` | E8 |
| TC-RDR-063 | UTF-8 with BOM | E | P1 | Valid note saved with BOM | Read normally; `Date:` still found on first line | M2 §5 |
| TC-RDR-064 | UTF-16 file (Windows Notepad) | E | P2 | Valid note saved as UTF-16 | ❓QA-8 Read normally **or** skipped with encoding reason — never crash | E8 |
| TC-RDR-065 | Binary file renamed `.md` | N | P2 | PNG renamed `img.md` | Skipped with reason | E8 |
| TC-RDR-066 | Permission denied | N | P2 | File without read permission | Skipped with reason `cannot read file (permission denied)`; others processed | NFR-01 |
| TC-RDR-067 | File deleted during run | E | P3 | File removed after listing, before reading | Skipped with reason; no crash | NFR-01 |
| TC-RDR-068 | One bad file among good | N | P1 | 3 good + 1 empty + 1 no-date + 1 bad-encoding | 3 notes, 3 skipped with correct reasons | E8, NFR-01 |
| TC-RDR-069 | All files malformed | N | P1 | 3 malformed files | 0 notes, 3 skipped; no crash | E8 |
| TC-RDR-070 | Header only, no action items | E | P2 | Date + attendees, no checkboxes | Read as good note (0 items later) — **not** skipped | E9 |

## 5. Content handling

| ID | Scenario | Type | Pri | Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-RDR-080 | Title extraction | F | P2 | `# Weekly Sales Sync` | `title = "Weekly Sales Sync"` | M9 email "from …" |
| TC-RDR-081 | No title | E | P3 | No `#` heading | `title = None`; note still read | — |
| TC-RDR-082 | Windows line endings | E | P1 | CRLF file | Date/attendees parsed; no `\r` in values | NFR-07 |
| TC-RDR-083 | Mixed line endings | E | P3 | CRLF + LF | Parsed | NFR-07 |
| TC-RDR-084 | Very long note | E | P2 | 10,000 lines of discussion + items | Read normally; full text returned | E9 |
| TC-RDR-085 | Messy markdown | E | P2 | Tables, code blocks, links, emojis | Read normally | E9 |
| TC-RDR-086 | Front-matter header | E | P3 | YAML front matter `---\ndate: 2026-10-06\n---` | ❓QA-5 Supported only if used in sample notes | Q1 |

## 6. Non-functional

| ID | Scenario | Type | Pri | Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-RDR-090 | Read 50 notes quickly | NF | P1 | 50 typical notes (~100 lines each) | Reader completes in < 1 s | NFR-03 |
| TC-RDR-091 | Large folder | NF | P3 | 500 notes | Completes; no memory errors | NFR-03 |
| TC-RDR-092 | Never crashes on any file | NF | P1 | Fuzz: random bytes in 100 `.md` files | Every file is either read or skipped; no exception escapes | NFR-01 |
| TC-RDR-093 | Original files unchanged | NF | P1 | Compare file hash + modified time before/after ingest | Identical (tool never edits notes) | §1.5 |

---

## Questions affecting this module

- **QA-3:** Should `.MD` / `.Md` be accepted? Should `.markdown` be accepted?
- **QA-4:** Should `ingest` read sub-folders (recursive) or only the top-level folder?
- **QA-5:** Can we get the sample `notes/` folder? Exact date/attendee formats decide TC-RDR-024/046/047/086 (Q1).
- **QA-6:** If a note has no `Date:` line but the file name has a date, should we use it or skip the file?
- **QA-7:** If a note has two `Date:` lines, which one wins?
- **QA-8:** Must UTF-16 files be supported or is "skip with encoding error" acceptable?
