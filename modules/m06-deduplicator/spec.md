# M6 — Deduplicator

| Item | Detail |
|---|---|
| Module | M6 |
| Source file | `actiontrack/dedupe.py` |
| Input from | M3 + M4 + M5 (resolved items), M7 (existing items) |
| Feeds | M7 (add/update), M10 (counts) |
| Milestone | 5 — Dedupe + Storage |
| Source | Requirements §5 M6, FR-ING-05, FR-ING-08, E1, E2, E10, Acceptance #2 |

## 1. Purpose

Make sure the same task, repeated across several meetings, is stored **only once**, and that running `ingest` again never creates duplicates.

## 2. When are two items the same?

Both conditions must be true:

1. **Same resolved owner** (exact match of the `owner` field).
2. **Same or very similar task text** after cleaning, with similarity **≥ 85%**.

### Cleaning steps (applied to task text)

1. Lowercase.
2. Remove the due phrase.
3. Remove punctuation.
4. Collapse extra spaces and trim.

Similarity: e.g. `difflib.SequenceMatcher(None, a, b).ratio()` (standard library). Threshold `0.85` kept as a named constant so it can be tuned.

### Special owners

- `ambiguous`: also compare `owner_candidates` (same set) so the same ambiguous line is not duplicated.
- `unassigned`: dedupe among unassigned items by task text (working assumption).

## 3. Merge rules when a duplicate is found

| Rule | Action |
|---|---|
| New item | **Not** created |
| Source files | Add the new file to `source_files` if not already present |
| Due date | If the newer meeting gives a different due date, use the **newest meeting's** due date (and its `due_phrase`) |
| Status | If any newer note marks it `[x]`, set status to `done` (E2) |
| `meeting_date` | Stays the **first** meeting it appeared in |
| `updated_at` | Updated only when something actually changed |

"Newer" is decided by **meeting date**, not file order. Notes should be processed in meeting-date order so the newest wins; if a note is older than the item's latest-seen meeting, it must not overwrite the due date.

> **Open decision:** Should an older note showing `[ ]` re-open an item marked `done`? Working assumption: **no** — status only moves `open → done`, and a manual `actiontrack done` is never undone by ingest.

## 4. Re-running ingest (idempotency)

- Re-ingesting the same folder: every item matches an existing one, the file is already in `source_files`, so nothing changes (E10).
- IDs never change (M7).
- Counts reported to M10: `new_items`, `duplicates_merged`.

## 5. Suggested interface

```python
def normalize_task(task: str, due_phrase: str | None) -> str: ...
def is_duplicate(a: Item, b: Item, threshold: float = 0.85) -> bool: ...
def merge(existing: Item, incoming: ResolvedItem) -> bool:  # returns True if changed
    ...
def dedupe_into(store: Store, incoming: list[ResolvedItem]) -> DedupeStats: ...
```

## 6. Edge cases

| # | Case | Behaviour |
|---|---|---|
| E1 | Same task in several meetings | Stored once; all source files recorded; newest due date used |
| E2 | Task marked done in a later meeting | Status becomes `done` |
| E10 | Ingest run twice | No new duplicates; IDs unchanged |
| — | Same task, different owners | **Not** duplicates (two items) |
| — | Same task twice in one note | Stored once |

## 7. Tests

- `Send the revised quote!` vs `send the revised quote by Friday` (same owner) → duplicate.
- Similar text, different owner → separate items.
- Text below threshold → separate items.
- Later meeting with new due date → due date updated; older meeting does not overwrite.
- Later `[x]` → done.
- Ingest same folder twice → identical store.

## 8. Acceptance criteria

- [ ] Duplicate items appear only once in `list` (Acceptance #2).
- [ ] Re-running ingest adds no duplicates (Milestone 5).
