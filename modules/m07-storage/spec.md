# M7 — Storage

| Item | Detail |
|---|---|
| Module | M7 |
| Source file | `actiontrack/store.py` |
| Used by | M6 (ingest), M8 (list/done), M9 (followup) |
| Milestone | 5 — Dedupe + Storage |
| Source | Requirements §5 M7, FR-ING-06, E10, §11 |

## 1. Purpose

Save all action items in a single local file so they survive between runs, with stable IDs.

## 2. Responsibilities

- One local store file: `actiontrack.json` **or** `actiontrack.db` (SQLite). Pick one; JSON is simpler and enough for the expected size (tens of notes).
- Assign each item a **unique, stable ID** (1, 2, 3 …). IDs never change and are **never reused**, even if an item is removed.
- Provide: add item, update item, find item by ID, load all items.

## 3. Data model (one action item)

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | number | `12` | Unique, never reused |
| `owner` | text | `Priya Shah` | or `unassigned` / `ambiguous` |
| `owner_candidates` | list | `["Priya Shah", "Priya Kumar"]` | Only when ambiguous, else `[]` |
| `task` | text | `send the revised quote` | Cleaned task text |
| `raw_text` | text | `Priya to send the revised quote by Friday` | Original line |
| `due_date` | date or null | `2026-10-09` | `null` if unknown |
| `due_phrase` | text | `by Friday` | Original wording |
| `status` | `open` / `done` | `open` | Overdue is **calculated**, not stored |
| `source_files` | list | `["2026-10-06-sales.md"]` | All notes it appeared in |
| `meeting_date` | date | `2026-10-06` | First meeting it appeared in |
| `created_at` | timestamp | `2026-10-15T10:21:00` | ISO 8601 |
| `updated_at` | timestamp | `2026-10-15T10:21:00` | ISO 8601 |

Suggested extra fields (internal, optional):

| Field | Purpose |
|---|---|
| `meeting_title` | Shown in follow-up emails ("from Weekly Sales Sync") |
| `last_seen_meeting_date` | Lets M6 apply "newest meeting's due date" correctly |
| `not_in_attendees` | Flag for E7 |

## 4. JSON file layout (if JSON is chosen)

```json
{
  "version": 1,
  "next_id": 13,
  "items": [ { "id": 1, "owner": "Priya Shah", "...": "..." } ]
}
```

`next_id` guarantees IDs are never reused.

## 5. Suggested interface

```python
class Store:
    def __init__(self, path: Path): ...
    def load_all(self) -> list[Item]: ...
    def get(self, item_id: int) -> Item | None: ...
    def add(self, item: Item) -> Item: ...        # assigns id, timestamps
    def update(self, item: Item) -> None: ...     # refreshes updated_at
    def save(self) -> None: ...
```

## 6. Reliability rules

- Missing store file → start with an empty store (first run).
- Write **atomically**: write to a temp file, then rename over the original, so a crash never leaves a half-written store.
- Corrupt store file → stop with a clear error (do **not** silently overwrite user data).
- Dates stored as `YYYY-MM-DD` strings; timestamps as ISO 8601.
- Single user at a time; no locking required (§11).

## 7. Tests

- Add → get by ID returns the same item.
- IDs increase and survive reload.
- `next_id` not reused after deletion (if deletion exists).
- Save → reload round-trip preserves every field.
- Missing file → empty store; corrupt file → clear error.

## 8. Acceptance criteria

- [ ] Items survive between runs.
- [ ] IDs remain unchanged after re-ingesting (E10).
