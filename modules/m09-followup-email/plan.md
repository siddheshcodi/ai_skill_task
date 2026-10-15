# M9 — Follow-up Email & Gmail Draft: Implementation Plan

| Item | Detail |
|---|---|
| Files | `actiontrack/followup.py` (collect + compose), `actiontrack/drafts.py` (DraftCreator adapters), `actiontrack/people.py` (people.yaml) |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-FUP-001 … TC-FUP-142 |
| Milestone | 7 |
| Estimate | 1.25 dev-days |
| Depends on | M7 `Store`, M8 `is_overdue`, M4 `name_matches`, PyYAML, Gmail MCP connector |
| Used by | M1 (`followup`) |

## 1. Goal

Compose one correct reminder email per person and hand it to Gmail **as a draft only**. Make sending impossible by construction, and keep the transport replaceable (Q2 is still open).

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Split | Collect → compose (pure) → look up email → create draft (adapter) | Each step tested alone (NFR-05) |
| Owner resolution | Distinct real owners in the store matched with `name_matches`. 0 matches → `NotFoundError`; > 1 → `AmbiguousOwnerError` listing names; `unassigned`/`ambiguous` refused | FR-FUP-05, Q5 |
| Items | Owner's `open` items only (ambiguous items excluded); split into overdue / open using M8 `is_overdue`; each section sorted by due date, no-date last, then ID | FR-FUP-01, spec §3 |
| Empty | No items → message, return 0, adapter never called | FR-FUP-06 |
| Email model | `@dataclass Email(to, subject, body)`; plain text only | No HTML injection (TC-FUP-052) |
| Template | Built in code from the spec template; sections omitted when empty; `from <meeting_title or first source file>` | TC-FUP-040..054 |
| Sender name | `ACTIONTRACK_SENDER` env var or `sender:` key in `people.yaml`; default `actiontrack` | Q4: the From address is the connected Gmail account |
| People list | `people.yaml` (path via `--people`, default `./people.yaml`); case-insensitive name lookup; basic email check `^[^@\s]+@[^@\s]+\.[^@\s]+$` | Q3; QA-39 default |
| Dry run | Compose and print `To/Subject/Body`; never builds an adapter. If the email is missing: print with `To: <unknown>` + warning | FR-FUP-07; QA-40 default |
| **Draft transport (D3)** | `DraftCreator` protocol with exactly one method `create_draft(email) -> str` | Q2 open; swap without touching compose logic |
| Default adapter | **`HandoffDraftCreator`**: writes `outbox/<timestamp>-<owner>.json` (`{"to","subject","body"}`) and prints instructions. The Claude session's Gmail connector (`create_draft`) then creates the draft. | The claude.ai Gmail connector lives in the assistant session, not in the Python process |
| Optional adapter | `McpDraftCreator`: uses the `mcp` Python SDK to call a configured Gmail MCP server's draft tool. The tool name is **allow-listed** (`create_draft`) and any other name raises. | For teams running a local Gmail MCP server; selected with `--transport mcp` |
| Test adapter | `FakeDraftCreator` records calls | Unit tests |
| Safety | No `send` function, method, option or import anywhere; adapters expose only `create_draft`; static scan test in CI | NFR-02, FR-FUP-04 |
| Errors | Adapter failures → `DraftError` with a "try --dry-run" hint; no retry | TC-FUP-100..103 |
| Read-only | `followup` never writes the store | TC-FUP-086 |

## 3. Components

```python
# followup.py
def resolve_followup_owner(store, query: str) -> str: ...
def collect_items(store, owner: str, today: date) -> tuple[list[Item], list[Item]]: ...
def compose_email(owner: str, to: str, overdue, open_, sender: str) -> Email: ...
def run_followup(query, store, people_path, creator_factory, dry_run, today, out) -> int: ...

# people.py
def load_people(path: Path) -> People: ...            # raises ConfigError
class People: def email_for(self, full_name: str) -> str: ...

# drafts.py
class DraftCreator(Protocol):
    def create_draft(self, email: Email) -> str: ...
class HandoffDraftCreator: ...
class McpDraftCreator: ...        # optional, allow-list = {"create_draft"}
class FakeDraftCreator: ...       # tests
```

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | `resolve_followup_owner` + `collect_items` | 1.5 h | TC-FUP-001..007, 020..026 |
| 2 | `compose_email` + golden email text | 1.5 h | TC-FUP-040..054 |
| 3 | `people.py` loader + validation | 1 h | TC-FUP-060..067 |
| 4 | `DraftCreator` protocol, Fake + Handoff adapters | 1.5 h | TC-FUP-080..087, 104 |
| 5 | Optional `McpDraftCreator` with allow-list | 1.5 h | TC-FUP-081, 100..103 |
| 6 | Safety tests: source scan for `send`, `smtplib`, `drafts.send`, `messages.send`; MCP spy | 1 h | TC-FUP-120..123 |
| 7 | Manual check with test Gmail account: draft present, Sent empty | 0.5 h | TC-FUP-081..082 (release checklist) |

## 5. Test approach

- Pure tests for compose, using the M8 seed store and today = 2026-10-15. The expected email is stored as a golden file.
- `FakeDraftCreator` asserts the call count (0 for dry run and empty owner, 1 otherwise) and the payload.
- The safety scan walks `actiontrack/**/*.py` with `ast` and fails on any call or attribute named `send*` or any `smtplib` import.
- The manual Gmail check is in the release checklist, with screenshots attached to the release PR.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Q2 decides a direct MCP call and the connector is not reachable from Python | Hand-off adapter works today; MCP adapter is optional and behind a flag |
| A future contributor adds a send path | AST safety test in CI + code-owner review on `drafts.py` |
| Wrong recipient | `To` shown in confirmation output; `--dry-run` recommended in README before the first real run |
| Duplicate drafts on repeated runs | Documented (QA-41); a later option could look for an existing draft |

## 7. Open questions

Q2 (transport — **blocking decision D3**), QA-38 … QA-41.

## 8. Definition of done

- [ ] Draft appears in Gmail with the correct overdue/open items; Sent folder unchanged (Acceptance #7).
- [ ] Safety tests green in CI; no send code exists.
- [ ] All P1 TC-FUP cases pass.
