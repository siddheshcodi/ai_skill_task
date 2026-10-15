# M3 — Action Item Extractor: Test Cases

| Item | Detail |
|---|---|
| Module | M3 Action Item Extractor (`actiontrack/extractor.py`) |
| Covers | §5 M3, FR-ING-03, E3, E5, E9 |
| Test levels | Unit (`extract_items(note)`, `split_line(text)`) — parametrised tests |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

---

## 1. Checkbox detection and status

| ID | Scenario | Type | Pri | Line | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-EXT-001 | Open checkbox | F | P1 | `- [ ] Priya to send the quote` | 1 item, `status = open` | FR-ING-03 |
| TC-EXT-002 | Done, lower-case x | F | P1 | `- [x] Anita to book the demo room` | `status = done` | FR-ING-03 |
| TC-EXT-003 | Done, upper-case X | F | P1 | `- [X] Anita to book the demo room` | `status = done` | M3 |
| TC-EXT-004 | Star bullet | F | P1 | `* [ ] Rahul will update the CRM` | Detected, open | M3 |
| TC-EXT-005 | Plus bullet | E | P3 | `+ [ ] Rahul will update the CRM` | Detected, open | M3 |
| TC-EXT-006 | No space after dash | F | P1 | `-[ ] Rahul will update the CRM` | Detected | M3 |
| TC-EXT-007 | Extra spaces | F | P1 | `-   [ ]    Rahul will update the CRM   ` | Detected; text trimmed | M3 |
| TC-EXT-008 | Indented / nested item | E | P2 | `    - [ ] Rahul will update the CRM` | Detected | M3 |
| TC-EXT-009 | Tab indentation | E | P3 | `\t- [ ] Rahul will update the CRM` | Detected | M3 |
| TC-EXT-010 | Empty brackets, no space | E | P2 | `- [] Priya to send quote` | ❓QA-9 Recommended: treated as open | M3 |
| TC-EXT-011 | Spaces inside brackets | E | P3 | `- [ x ] …`, `- [  ] …` | ❓QA-9 Recommended: done / open | M3 |
| TC-EXT-012 | Other mark in box | E | P3 | `- [-] …`, `- [~] …`, `- [✓] …` | ❓QA-9 Not detected (ignored) or defined rule — never crash | M3 |
| TC-EXT-013 | Numbered checkbox | E | P3 | `1. [ ] Priya to send quote` | ❓QA-9 Ignored or supported — documented | M3 |
| TC-EXT-014 | Checkbox without bullet | E | P3 | `[ ] Priya to send quote` | ❓QA-9 Ignored or supported — documented | M3 |
| TC-EXT-015 | Checkbox with no text | N | P2 | `- [ ]`, `- [ ]    ` | Ignored (no empty item created) | M3 |
| TC-EXT-016 | Plain bullet ignored | N | P1 | `- Priya to send quote` | No item | E9 |
| TC-EXT-017 | Free text ignored | N | P1 | `Priya will send the quote by Friday` (no checkbox) | No item | E9 |
| TC-EXT-018 | Heading ignored | N | P2 | `## Action items` | No item | E9 |
| TC-EXT-019 | Checkbox inside fenced code block | E | P3 | Inside ```` ``` ```` block | ❓QA-10 Recommended: ignored | E9 |
| TC-EXT-020 | Checkbox in a quote | E | P3 | `> - [ ] Priya to send quote` | ❓QA-10 Defined behaviour; no crash | E9 |
| TC-EXT-021 | Items in any section | E | P2 | Checkbox under `## Discussion` (not `## Action items`) | Still extracted (requirement does not limit to a section) | FR-ING-03 |
| TC-EXT-022 | Count of items | F | P1 | Sample note from §3 (4 checkboxes) | 4 items: 3 open, 1 done | FR-ING-03 |
| TC-EXT-023 | Line numbers recorded | F | P3 | Sample note | `line_number` correct for each item | M3 §4 |
| TC-EXT-024 | CRLF line endings | E | P1 | Windows file | Items extracted; no `\r` in text | NFR-07 |

## 2. Owner phrase splitting

| ID | Scenario | Type | Pri | Line text | Expected owner / task / due | Trace |
|---|---|---|---|---|---|---|
| TC-EXT-030 | `Name to …` | F | P1 | `Priya to send the revised quote by Friday` | Priya / send the revised quote / by Friday | M3 table |
| TC-EXT-031 | `Name will …` | F | P1 | `Rahul will update the CRM by 2026-10-12` | Rahul / update the CRM / by 2026-10-12 | M3 table |
| TC-EXT-032 | `@Name …` | F | P1 | `@Anita book the demo room` | Anita / book the demo room / none | M3 table |
| TC-EXT-033 | `Name: …` | F | P1 | `Priya: send the revised quote` | Priya / send the revised quote / none | M3 |
| TC-EXT-034 | No owner | F | P1 | `Share the slide deck with the client` | none / share the slide deck with the client / none | E3 |
| TC-EXT-035 | Full name owner | F | P1 | `Priya Shah to send the quote` | Priya Shah / send the quote | M4 input |
| TC-EXT-036 | Name + initial | F | P1 | `Priya S. to send the quote` | Priya S. / send the quote | M4 input |
| TC-EXT-037 | Initial without dot | E | P2 | `Priya S to send the quote` | Priya S / send the quote | M4 input |
| TC-EXT-038 | Lower-case owner | E | P2 | `priya to send the quote` | ❓QA-11 Recommended: owner `priya` (attendee match decides) | M3 |
| TC-EXT-039 | `@` with full name | E | P3 | `@Priya Shah send the quote` | ❓QA-11 Defined: owner `Priya` or `Priya Shah` — consistent | M3 |
| TC-EXT-040 | "to" later in sentence | N | P1 | `Send deck to client` | Owner none (verb `Send` is not a name); task whole line | M3 §5 |
| TC-EXT-041 | "will" later in sentence | N | P2 | `Check whether client will renew` | Owner none | M3 §5 |
| TC-EXT-042 | Capitalised non-name starter | N | P2 | `Finance to approve the budget` | ❓QA-12 Owner phrase `Finance` → later "not in attendees" (E7) — confirm teams are allowed as owners | E7 |
| TC-EXT-043 | Multiple owners | E | P2 | `Priya and Rahul to prepare the demo` | ❓QA-13 Not defined — recommended: owner phrase `Priya and Rahul` → unresolved / flagged; never silently picks one | M4 |
| TC-EXT-044 | Owner with apostrophe / accents | E | P3 | `Zoë O'Brien to send notes` | Owner `Zoë O'Brien` | NFR-07 |
| TC-EXT-045 | `Name will be …` | E | P3 | `Priya will be sending the deck` | Priya / be sending the deck | M3 |
| TC-EXT-046 | Owner at end | E | P3 | `Send the quote (Priya)` / `Send the quote – Priya` | ❓QA-11 Not in supported patterns → owner none (unassigned) | M3 |

## 3. Due phrase splitting

| ID | Scenario | Type | Pri | Line text | Expected task / due phrase | Trace |
|---|---|---|---|---|---|---|
| TC-EXT-060 | `by <weekday>` | F | P1 | `Priya to send the quote by Friday` | send the quote / by Friday | M3 |
| TC-EXT-061 | `by <ISO date>` | F | P1 | `… update the CRM by 2026-10-12` | update the CRM / by 2026-10-12 | M3 |
| TC-EXT-062 | `on <weekday>` | F | P1 | `… call the client on Monday` | call the client / on Monday | M5 input |
| TC-EXT-063 | `by DD/MM/YYYY` | F | P1 | `… send report by 12/10/2026` | send report / by 12/10/2026 | M5 input |
| TC-EXT-064 | `by Mon DD` | F | P1 | `… send report by Oct 12` | send report / by Oct 12 | M5 input |
| TC-EXT-065 | Bare keyword | F | P1 | `… send report tomorrow`, `… EOD`, `… EOW`, `… next week`, `… end of month`, `… today` | Keyword captured as due phrase; removed from task | M5 input |
| TC-EXT-066 | `due` / `before` | E | P2 | `… send report due Friday`, `… before Oct 12` | due phrase captured | M3 §3 |
| TC-EXT-067 | Unclear due phrase | E | P1 | `Priya to send the quote soon` / `by ASAP` | Due phrase `soon` / `by ASAP` captured (M5 makes date null) | E5 |
| TC-EXT-068 | "by" that is not a date | N | P1 | `Priya to get sign-off by the client` | ❓QA-14 Task keeps `get sign-off by the client` **or** due phrase `by the client` (→ null date). Task text must not lose meaning silently | E5 |
| TC-EXT-069 | Two "by" in a line | E | P2 | `Rahul to review by Priya's notes by Friday` | Due phrase = last one `by Friday` | M3 |
| TC-EXT-070 | Due phrase in middle | E | P3 | `Priya by Friday to send the quote` | ❓QA-14 Defined result; no crash | M3 |
| TC-EXT-071 | Trailing punctuation | E | P2 | `Priya to send the quote by Friday.` | due `by Friday` (dot removed) | M5 input |
| TC-EXT-072 | Due phrase in brackets | E | P3 | `Priya to send the quote (by Fri)` | due `by Fri` | M5 input |
| TC-EXT-073 | No due phrase | F | P1 | `@Anita book the demo room` | due phrase none | E4 |

## 4. Messy content

| ID | Scenario | Type | Pri | Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-EXT-080 | Markdown formatting in text | E | P2 | `- [ ] **Priya** to send the [quote](http://x)` | Owner Priya; task readable (formatting stripped or kept consistently) | E9 |
| TC-EXT-081 | Emoji in text | E | P3 | `- [ ] Priya to send the quote 🚀 by Friday` | Parsed; no crash | E9 |
| TC-EXT-082 | Very long line | E | P3 | 2,000-character task | Parsed; no crash / no regex hang | E9 |
| TC-EXT-083 | Many items | E | P2 | Note with 500 checkboxes | 500 items | E9 |
| TC-EXT-084 | Done item with owner + due | F | P1 | `- [x] Priya to send quote by Friday` | status done; owner/task/due split the same as open | FR-ING-03 |
| TC-EXT-085 | Same task twice in one note | E | P2 | Two identical lines | Both extracted here (M6 merges) | E1 |

## 5. Non-functional

| ID | Scenario | Type | Pri | Input | Expected result | Trace |
|---|---|---|---|---|---|---|
| TC-EXT-090 | No catastrophic regex backtracking | NF | P2 | Line of 10,000 spaces + `[` characters | Returns in < 100 ms | NFR-03 |
| TC-EXT-091 | Pure function | NF | P3 | Same note twice | Same output; no global state | NFR-05 |

---

## Questions affecting this module

- **QA-9:** Which checkbox variants must be supported? (`- []`, `- [ x ]`, `[-]`, numbered `1. [ ]`, `[ ]` with no bullet)
- **QA-10:** Should checkboxes inside code blocks or quotes be ignored?
- **QA-11:** Is a lower-case owner (`priya to …`) valid? Should owners written at the end (`… (Priya)`) be supported?
- **QA-12:** Can a team (`Finance`, `Legal`) be an owner, or should it be unassigned?
- **QA-13:** How to handle multiple owners (`Priya and Rahul to …`)?
- **QA-14:** If "by" is followed by something that is not a date (`by the client`), should it stay in the task text?
