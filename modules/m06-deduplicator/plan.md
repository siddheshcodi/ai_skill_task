# M6 — Deduplicator: Implementation Plan

| Item | Detail |
|---|---|
| File | `actiontrack/dedupe.py` |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-DUP-001 … TC-DUP-092 |
| Milestone | 5 |
| Estimate | 1.0 dev-day |
| Depends on | `models.Item`, `models.ResolvedItem`, M7 `Store` |
| Used by | `ingest.run_ingest` |

## 1. Goal

Each real task is stored once, across meetings and across re-runs. The newest meeting decides the due date. A task marked done anywhere ends up done.

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Processing order | `ingest.py` feeds notes sorted by `(meeting_date, file_name)` | The newest note is applied last; deterministic (TC-DUP-063, 091) |
| Match key | `owner_key` + normalised task similarity ≥ `SIMILARITY_THRESHOLD = 0.85` | Spec §2 |
| `owner_key` | Real name → casefolded name; `ambiguous` → `"ambiguous:" + sorted candidates`; `unassigned` → `"unassigned"` | TC-DUP-031..033 |
| Normalisation | casefold → remove `due_phrase` text → remove punctuation (`[^\w\s]`) → collapse spaces | Spec §2, TC-DUP-001..004 |
| Similarity | `difflib.SequenceMatcher(None, a, b).ratio()` with a fast exact-match short cut | Stdlib; exact matches are the common case |
| Candidate search | Index stored items by `owner_key`, compare only within the same owner | 50 notes × 10 items vs 500 items stays well under 1 s (TC-DUP-090) |
| Best match | Highest ratio ≥ threshold; on a tie, the lowest ID | TC-DUP-036 |
| False-merge guard | Block a merge when the two texts contain **different capitalised words or numbers** (e.g. `Rahul` vs `Anita`, `Q3` vs `Q4`) | Mitigates QA-26 (TC-DUP-029/030); can be switched off |
| Empty normalised text | Never matched by similarity; only an exact `raw_text` match merges | QA-25 default |
| Due-date merge | Apply the incoming due date if `incoming.meeting_date >= item.last_seen_meeting_date` **and** `incoming.due_date is not None` | Newest wins (E1); an older note never overwrites (TC-DUP-053); a missing date never erases a known one (QA-28 default) |
| Status merge | `done` if the existing item is done **or** the incoming one is `[x]`; never done → open | E2; QA-29 default; manual `done` survives (TC-DUP-059) |
| Source files | Append if not already present (keep order of first appearance) | E1, TC-DUP-073 |
| `meeting_date` | Never changed after creation (first meeting) | Data model |
| `raw_text`, `meeting_title` | Keep the first values | QA-30 default |
| Change tracking | `merge()` returns `True` only when a field really changed → M7 bumps `updated_at` | TC-DUP-062, idempotent re-runs |
| Same-note repeats | Handled naturally: the second line matches the item created by the first | TC-DUP-035 |

## 3. Components

```python
SIMILARITY_THRESHOLD = 0.85

@dataclass
class DedupeStats:
    new_items: int = 0
    duplicates_merged: int = 0

def normalize_task(task: str, due_phrase: str | None) -> str: ...
def owner_key(owner: str, candidates: list[str]) -> str: ...
def similarity(a: str, b: str) -> float: ...
def conflicting_tokens(a: str, b: str) -> bool: ...          # false-merge guard
def find_match(index, resolved) -> Item | None: ...
def merge(existing: Item, incoming: ResolvedItem) -> bool: ...
def to_new_item(incoming: ResolvedItem) -> Item: ...
def dedupe_into(store: Store, incoming: list[ResolvedItem], stats: DedupeStats) -> None: ...
```

The index is built once per ingest from `store.load_all()` and updated as new items are added. It lives only in memory.

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | `normalize_task`, `owner_key`, `similarity` | 1 h | TC-DUP-001..006 |
| 2 | `find_match` with owner index, threshold, tie-break, guard | 2 h | TC-DUP-020..036 |
| 3 | `merge` rules + change detection | 1.5 h | TC-DUP-050..063 |
| 4 | `dedupe_into` + stats | 1 h | TC-DUP-070..078 |
| 5 | Integration fixtures N1/N2/N3 + double-ingest snapshot test | 1.5 h | TC-DUP-070..073, E1/E2/E10 |
| 6 | Performance test | 0.5 h | TC-DUP-090 |

## 5. Test approach

- Unit tests for each rule, with hand-built `Item`/`ResolvedItem` objects.
- Threshold boundary tests (0.84 / 0.85 / 0.86) use pairs chosen by computing the ratio in the test, so they don't depend on hard-coded texts.
- Idempotency: ingest the fixture folder, snapshot the store JSON (ignoring nothing), ingest again, and assert the store is byte-identical.

## 6. Risks

| Risk | Mitigation |
|---|---|
| False merges (two different tasks become one) | Token guard; constant threshold; `--debug` logs every merge with its score |
| Missed merges (wording changed a lot) | Acceptable: shows up as two items; user can `done` one |
| Notes renamed or deleted between runs | Items kept; the new name is added to `source_files` (QA-31 default) |

## 7. Open questions

QA-25 … QA-31. Defaults are in the decisions table. QA-26 (the guard) and QA-28/29 (merge semantics) need sign-off.

## 8. Definition of done

- [ ] Re-running ingest leaves the store byte-identical (E10).
- [ ] E1 and E2 integration tests pass; all P1 TC-DUP cases pass.
