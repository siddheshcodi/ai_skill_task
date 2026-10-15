# M7 — Storage: Implementation Plan

| Item | Detail |
|---|---|
| File | `actiontrack/store.py` |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-STO-001 … TC-STO-083 |
| Milestone | 5 (can start right after milestone 2) |
| Estimate | 0.75 dev-day |
| Depends on | `models.Item`, `errors.StoreError` |
| Used by | `ingest.py` (M6), M8, M9 |

## 1. Goal

A small, safe, single-file store with stable IDs that are never reused. Data is never lost: no half-written files, and a file that cannot be read is never overwritten.

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Backend | JSON file, default `./actiontrack.json`, overridable with `--store` | D1 in the overview; human-readable; small data |
| Layout | `{"version": 1, "next_id": N, "items": [...]}` | `next_id` guarantees no reuse (TC-STO-024); `version` allows migration |
| Load model | Load the whole file into memory on first access; keep a dict `id → Item` | Fast at this scale (TC-STO-080) |
| Save model | Explicit `save()`; commands call it once at the end | One write per command; Ctrl+C before save = no change |
| Atomic write | Write to `<store>.tmp` in the same folder → `flush` + `os.fsync` → `os.replace(tmp, store)` | Atomic on Windows, macOS and Linux (TC-STO-066) |
| Backup | Copy the previous file to `<store>.bak` before replace (optional, on by default) | Cheap recovery |
| Serialisation | Dates as `YYYY-MM-DD`; timestamps as ISO 8601 (local time, seconds); `None` as JSON `null`; `ensure_ascii=False`, `indent=2`, keys in a fixed order | TC-STO-021..028, 040..041; stable diffs |
| Validation on load | Check the top-level keys and types, required item fields, unique IDs, and `status ∈ {open, done}` | TC-STO-062/063/070 raise `StoreError` and the file is not touched |
| Missing file | Empty store; the file is created on first `save()` | TC-STO-060 |
| Empty (0-byte) file | Treated as an empty store, with a warning | QA-32 default |
| ID assignment | `add()` ignores any caller ID and uses `next_id`, then increments | TC-STO-008 |
| Timestamps | `add()` sets both; `update()` sets `updated_at` only when called after a real change (M6/M8 decide) | TC-STO-005, TC-DUP-062 |
| Clock | `now` provider injected (default `datetime.now`) | Deterministic tests |
| Concurrency | None (single user, §11) | Atomic write still prevents corruption |

## 3. Components

```python
class Store:
    def __init__(self, path: Path, now: Callable[[], datetime] = datetime.now): ...
    def load_all(self) -> list[Item]: ...        # sorted by id
    def get(self, item_id: int) -> Item | None: ...
    def add(self, item: Item) -> Item: ...
    def update(self, item: Item) -> None: ...    # raises NotFoundError for an unknown id
    def save(self) -> None: ...                  # atomic

def item_to_dict(item: Item) -> dict: ...
def item_from_dict(d: dict) -> Item: ...         # raises StoreError on bad data
```

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | `item_to_dict` / `item_from_dict` + validation | 1.5 h | TC-STO-021..028, 040..045 |
| 2 | `Store` load (missing / empty / corrupt / wrong structure) | 1 h | TC-STO-060..063, 069..070 |
| 3 | CRUD + `next_id` | 1 h | TC-STO-001..008, 024 |
| 4 | Atomic save + backup + error handling (read-only, disk full) | 1.5 h | TC-STO-064..068 |
| 5 | Stable-ID integration tests with ingest | 0.5 h | TC-STO-025..026 |
| 6 | Performance test (1,000 items) | 0.5 h | TC-STO-080 |

## 5. Test approach

- Round-trip property: `item_from_dict(item_to_dict(x)) == x` for generated items, including Unicode, `None`, and empty lists.
- Crash simulation: monkeypatch `os.replace` or `json.dump` to raise, then assert the original file's bytes are unchanged.
- Cross-OS: CI writes the store on one OS job and reads it in a test on the same job. The format is OS-neutral by construction (UTF-8, no paths beyond file names).

## 6. Risks

| Risk | Mitigation |
|---|---|
| User edits the JSON by hand and breaks it | Clear `StoreError` with the line and column from `json.JSONDecodeError`; `.bak` available |
| Schema changes later | `version` field + a migration function stub |

## 7. Open questions

QA-32 (JSON vs SQLite — the plan uses JSON; empty file = empty store).

## 8. Definition of done

- [ ] All P1 TC-STO cases pass, including the crash simulation.
- [ ] IDs unchanged across re-ingests (E10).
