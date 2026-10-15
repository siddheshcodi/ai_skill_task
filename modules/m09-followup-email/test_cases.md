# M9 — Follow-up Email & Gmail Draft: Test Cases

| Item | Detail |
|---|---|
| Module | M9 Follow-up Email Composer and Gmail Draft (`actiontrack/followup.py`) |
| Covers | §5 M9, §6.4 FR-FUP-01..08, NFR-02, Q2–Q5, Acceptance #7 |
| Test levels | Unit (compose, collect, people lookup with `FakeDraftCreator`) · Integration (real Gmail MCP, test account) · Static (code scan) |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional · SEC = Safety
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

**Fixed "today": 2026-10-15.** Uses the seed store from M8 test cases.

`people.yaml` (default):

```yaml
Priya Shah: priya.shah@example.com
Rahul Mehta: rahul.mehta@example.com
Anita Rao: anita.rao@example.com
Priya Kumar: priya.kumar@example.com
```

---

## 1. Collecting items

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-001 | Open + overdue collected | F | P1 | `followup "Priya Shah" --dry-run` | #1 (overdue), #7 (open); done items excluded | FR-FUP-01 |
| TC-FUP-002 | Overdue listed first | F | P1 | Same | `Overdue` section before `Open` | M9 |
| TC-FUP-003 | Done items excluded | F | P1 | `followup Anita --dry-run` (only #3, done) | No email; "no open action items" message | FR-FUP-06 |
| TC-FUP-004 | Ambiguous items excluded | F | P1 | `followup "Priya Kumar" --dry-run` | Only #6 — #5 (ambiguous) not included | Q5 |
| TC-FUP-005 | Due today counted as open, not overdue | E | P1 | `followup "Priya Kumar" --dry-run` | #6 under `Open` (due 10-15 = today) | M8 rule |
| TC-FUP-006 | Sort within sections | F | P2 | Owner with 3 open items (due 10-20, none, 10-17) | Order: 10-17, 10-20, no due date | M9 |
| TC-FUP-007 | Many items | E | P3 | Owner with 30 open items | All listed; subject count `(30)` | M9 |

## 2. Owner matching

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-020 | Full name | F | P1 | `followup "Rahul Mehta"` | Resolves to Rahul Mehta | FR-FUP-01 |
| TC-FUP-021 | Unique first name | F | P1 | `followup rahul` | Resolves to Rahul Mehta | FR-FUP-01 |
| TC-FUP-022 | Case-insensitive | F | P2 | `followup RAHUL` | Resolves | FR-FUP-01 |
| TC-FUP-023 | First name matches two people | N | P1 | `followup priya` | Error: "matches more than one person: Priya Shah, Priya Kumar. Please use the full name."; no draft; non-zero exit | FR-FUP-05 |
| TC-FUP-024 | Unknown owner | N | P1 | `followup Vikram` | Clear error "No items found for 'Vikram'"; no draft | FR-FUP-01 |
| TC-FUP-025 | `unassigned` / `ambiguous` as owner | N | P2 | `followup unassigned`, `followup ambiguous` | Refused with clear message; no draft | Q5 |
| TC-FUP-026 | Owner flagged not-in-attendees | E | P2 | `followup Vikram` where Vikram owns items (E7) but not in `people.yaml` | Email address error (FR-FUP-08) | E7, FR-FUP-08 |

## 3. Email content

| ID | Scenario | Type | Pri | Check | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-040 | Subject with count | F | P1 | Priya Shah (2 items) | `Follow-up: your open action items (2)` | M9 template |
| TC-FUP-041 | Subject singular | E | P3 | Owner with 1 item | ❓QA-38 `(1)` as per template (grammar "items" acceptable?) | M9 |
| TC-FUP-042 | Greeting with first name | F | P1 | Priya Shah | `Hi Priya,` | M9 |
| TC-FUP-043 | Greeting single-word name | E | P3 | Owner `Anita` | `Hi Anita,` | M9 |
| TC-FUP-044 | Overdue line format | F | P1 | #1 | `• Send the revised quote (due 2026-10-09, from Weekly Sales Sync)` | M9 |
| TC-FUP-045 | Open line with due date | F | P1 | #8 | `• Call the client (due 2026-10-16)` | M9 |
| TC-FUP-046 | No due date wording | F | P1 | #7 | `• Update pricing sheet (no due date)` | M9, E4 |
| TC-FUP-047 | Meeting title missing | E | P2 | Note without `#` title | `from <source file name>` | M9 |
| TC-FUP-048 | Task capitalised | F | P3 | `send the revised quote` | `Send the revised quote` | M9 |
| TC-FUP-049 | Only overdue items | E | P2 | Owner with overdue only | `Open` section omitted | M9 |
| TC-FUP-050 | Only open items | E | P2 | Owner with open only | `Overdue` section omitted | M9 |
| TC-FUP-051 | Closing text and signature | F | P2 | Any | "Please reply if any of these…", `Thanks,` + sender name | M9, Q4 |
| TC-FUP-052 | Special characters in tasks | E | P2 | Task with `<b>`, `&`, quotes, emoji | Shown as plain text; no HTML injection | M9 |
| TC-FUP-053 | Unicode names | E | P2 | Owner `José Núñez` | Correct greeting and encoding in draft | NFR-07 |
| TC-FUP-054 | Item in several meetings | E | P3 | #7 (2 source files) | Single line (not repeated); from = first/newest meeting — consistent | E1 |

## 4. People list (`people.yaml`)

| ID | Scenario | Type | Pri | Setup | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-060 | Email found | F | P1 | Default file | `To: priya.shah@example.com` | Q3 |
| TC-FUP-061 | Person missing from file | N | P1 | Remove Rahul | Clear error "No email address for Rahul Mehta in people.yaml"; no draft; non-zero exit | FR-FUP-08 |
| TC-FUP-062 | File missing | N | P1 | Delete `people.yaml` | Clear error explaining how to create it; no draft | FR-FUP-08 |
| TC-FUP-063 | File invalid YAML | N | P2 | Broken indentation | Clear error; no draft | FR-FUP-08 |
| TC-FUP-064 | Empty email value | N | P2 | `Rahul Mehta: ""` | Same as missing email | FR-FUP-08 |
| TC-FUP-065 | Invalid email format | N | P2 | `Rahul Mehta: rahul-at-example` | ❓QA-39 Recommended: clear error, no draft | FR-FUP-08 |
| TC-FUP-066 | Name case differs in file | E | P3 | `rahul mehta: …` | ❓QA-39 Recommended: case-insensitive lookup | Q3 |
| TC-FUP-067 | `--dry-run` with missing email | E | P2 | Remove Rahul, `followup rahul --dry-run` | ❓QA-40 Print email with placeholder + warning **or** same error | FR-FUP-07/08 |

## 5. Draft creation & dry run

| ID | Scenario | Type | Pri | Command | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-080 | Draft created | F | P1 | `followup "Priya Shah"` (fake creator) | `create_draft(to, subject, body)` called once with correct values; confirmation printed | FR-FUP-03 |
| TC-FUP-081 | Draft visible in Gmail | F | P1 | Integration with test Gmail account | Draft in **Drafts** folder; correct To/Subject/Body | Acceptance #7 |
| TC-FUP-082 | Nothing in Sent | SEC | P1 | After TC-FUP-081 | Gmail **Sent** folder unchanged; recipient inbox has no email | FR-FUP-04, NFR-02 |
| TC-FUP-083 | Dry run prints only | F | P1 | `followup "Priya Shah" --dry-run` | Full email printed (To, Subject, Body); creator **not** called; exit `0` | FR-FUP-07 |
| TC-FUP-084 | No items → no draft | F | P1 | `followup anita` | Message; creator not called; exit `0` | FR-FUP-06 |
| TC-FUP-085 | Run twice | E | P2 | `followup "Priya Shah"` ×2 | ❓QA-41 Two drafts created (no de-dup) — confirm acceptable | FR-FUP-03 |
| TC-FUP-086 | Store not changed | F | P2 | Compare store before/after followup | Unchanged (followup is read-only) | M9 |
| TC-FUP-087 | Sender | F | P3 | Inspect draft | From = account connected to Gmail MCP; no CC | Q4 |

## 6. Gmail MCP failures

| ID | Scenario | Type | Pri | Setup | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-100 | MCP not available / not connected | N | P1 | Disconnect connector | Clear error "Could not create Gmail draft: …"; suggest `--dry-run`; non-zero exit | NFR-04 |
| TC-FUP-101 | Auth expired | N | P2 | Expired token | Clear error with fix hint | NFR-04 |
| TC-FUP-102 | MCP returns error | N | P2 | Fake creator raises | Clear error; no partial state; never falls back to "send" | NFR-02 |
| TC-FUP-103 | Timeout | N | P3 | Fake creator hangs | Times out with clear message | NFR-04 |
| TC-FUP-104 | Hand-off mode (if chosen, Q2) | F | P2 | Handoff creator | Email JSON written in documented format for assistant to create draft | Q2 |

## 7. Safety (never send)

| ID | Scenario | Type | Pri | Check | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-120 | No send code exists | SEC | P1 | Static scan of `actiontrack/` for `send_message`, `send_draft`, `messages.send`, `drafts.send`, SMTP | Zero matches; test fails build otherwise | NFR-02 |
| TC-FUP-121 | Only create-draft tool called | SEC | P1 | Spy on MCP client during all M9 tests | Only the "create draft" tool name is ever invoked | FR-FUP-04 |
| TC-FUP-122 | No SMTP / network libs | SEC | P2 | Check imports (`smtplib`, etc.) | Not imported | NFR-02 |
| TC-FUP-123 | No hidden send flag | SEC | P2 | `followup --help`, try `--send` | No such option; `--send` → unknown option error | NFR-02 |

## 8. Non-functional

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-FUP-140 | Dry-run speed | NF | P3 | `--dry-run` with 1,000-item store | < 1 s | NFR-03 |
| TC-FUP-141 | Draft transport swappable | NF | P2 | Run with Fake / MCP / Handoff creators | Same composed email in each | NFR-05, Q2 |
| TC-FUP-142 | Email readable on mobile | NF | P3 | Open draft in Gmail mobile | Plain text renders cleanly | NFR-04 |

---

## Questions affecting this module

- **QA-38:** Subject for one item — `(1)` with "items" is fine, or should it be "item"?
- **QA-39:** Should `people.yaml` lookup be case-insensitive? Should invalid email addresses be rejected?
- **QA-40:** Should `--dry-run` work when the email address is missing (with a warning)?
- **QA-41:** Running `followup` twice creates two drafts — is that acceptable?
- **Q2 (from requirements):** Will the CLI call Gmail MCP directly, or hand off to the AI assistant? Decides TC-FUP-081/100/104.
