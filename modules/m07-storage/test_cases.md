# M7 — Storage: Test Cases

| Item | Detail |
|---|---|
| Module | M7 Storage (`actiontrack/store.py`) |
| Covers | §5 M7 (data model), FR-ING-06, E10, NFR-01, §11 |
| Test levels | Unit (`Store` against temp files) + Integration (CLI round-trips) |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

---

## 1. CRUD operations

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-STO-001 | Add item | F | P1 | `add(item)` on empty store | Item gets `id = 1`, `created_at` and `updated_at` set | M7 |
| TC-STO-002 | IDs increase | F | P1 | Add 3 items | IDs 1, 2, 3 | M7 |
| TC-STO-003 | Get by ID | F | P1 | `get(2)` | Returns item 2 with all fields | M7 |
| TC-STO-004 | Get missing ID | N | P1 | `get(99)` | Returns `None` (no exception) | FR-DON-02 |
| TC-STO-005 | Update item | F | P1 | Change status to `done`, `update()` | Persisted; `updated_at` newer; `created_at` unchanged | M7 |
| TC-STO-006 | Update missing item | N | P2 | `update()` on item with unknown ID | Clear error; store unchanged | M7 |
| TC-STO-007 | Load all | F | P1 | `load_all()` after adding 3 | 3 items in ID order | M7 |
| TC-STO-008 | Caller cannot set ID | E | P2 | `add(item with id=50)` | Store assigns its own next ID (ignores caller ID) | M7 |

## 2. Persistence and stable IDs

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-STO-020 | Survives restart | F | P1 | Add items, save, new `Store()` on same file | Same items and IDs | M7 |
| TC-STO-021 | Round-trip all fields | F | P1 | Save item with every field filled (incl. `owner_candidates`, multiple `source_files`) | Reloaded item equal field by field | M7 model |
| TC-STO-022 | `null` due date round-trip | F | P1 | `due_date = None` | Reloaded as `None` (not `"None"` / `""`) | E4 |
| TC-STO-023 | Empty lists round-trip | E | P2 | `owner_candidates = []` | Reloaded as `[]` | M7 |
| TC-STO-024 | IDs never reused | F | P1 | Add 1,2,3; delete 3 (if supported) or simulate; add new | New ID = 4 (`next_id` honoured) | M7 |
| TC-STO-025 | IDs stable on re-ingest | F | P1 | Ingest folder, record IDs; re-ingest | All IDs unchanged | E10 |
| TC-STO-026 | IDs stable when new notes added | F | P1 | Ingest; add note; ingest | Old IDs unchanged; new items get next IDs | E10 |
| TC-STO-027 | Unicode preserved | E | P2 | Owner `José Núñez`, task with emoji | Saved and reloaded exactly (UTF-8) | NFR-07 |
| TC-STO-028 | Special characters in task | E | P2 | Task with quotes `"`, backslash `\`, newline-like text | Valid store file; reloaded exactly | M7 |

## 3. Data format validation

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-STO-040 | Date format | F | P1 | Inspect stored `due_date`, `meeting_date` | `YYYY-MM-DD` | M5 |
| TC-STO-041 | Timestamp format | F | P2 | Inspect `created_at`, `updated_at` | ISO 8601 | M7 |
| TC-STO-042 | Status values | F | P1 | Inspect any item | Only `open` or `done` — **never** `overdue` stored | M7 model |
| TC-STO-043 | Owner values | F | P1 | Store unassigned/ambiguous/real items | `owner` is name, `unassigned` or `ambiguous`; candidates only when ambiguous | M7 model |
| TC-STO-044 | Schema version present | F | P3 | Inspect JSON | `version` field present | M7 §4 |
| TC-STO-045 | All required fields present | F | P1 | Inspect any item | `id, owner, owner_candidates, task, raw_text, due_date, due_phrase, status, source_files, meeting_date, created_at, updated_at` | M7 model |

## 4. File problems

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-STO-060 | Store file missing | E | P1 | Run with no store | Empty store; file created on first save | M7 |
| TC-STO-061 | Store file empty (0 bytes) | E | P2 | Create empty store file | ❓QA-32 Recommended: treated as empty store **or** clear error — never crash | NFR-01 |
| TC-STO-062 | Corrupt store (invalid JSON) | N | P1 | Write `{"items": [` | Clear error `store file is corrupt…`; file **not** overwritten | M7 §6 |
| TC-STO-063 | Wrong structure | N | P2 | Valid JSON but missing `items` / wrong types | Clear error; file not overwritten | M7 §6 |
| TC-STO-064 | Read-only store | N | P2 | Make file read-only, then `done 1` | Clear write error; original intact | NFR-04 |
| TC-STO-065 | Store folder missing | E | P3 | `--store newdir/at.json` | Folder created or clear error | M7 |
| TC-STO-066 | Atomic write — crash during save | NF | P1 | Kill process / raise exception during write | Store is either old version or new version — never partial/invalid | M7 §6 |
| TC-STO-067 | Temp file cleaned up | NF | P3 | After normal and failed saves | No leftover temp files | M7 |
| TC-STO-068 | Disk full | N | P3 | Simulate `OSError: No space` on write | Clear error; original store intact | NFR-01 |
| TC-STO-069 | Manually edited store | E | P3 | User changes a task text in JSON and re-runs `list` | Loaded fine | M7 |
| TC-STO-070 | Duplicate IDs in file | N | P3 | Hand-edit file to have two items with id 3 | Clear error (data integrity) | M7 |

## 5. Non-functional

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-STO-080 | Load/save speed | NF | P1 | Store with 1,000 items | Load + save < 0.5 s | NFR-03 |
| TC-STO-081 | Portable store file | NF | P2 | Create store on Windows, read on Linux/macOS | Works (UTF-8, no OS-specific paths) | NFR-07 |
| TC-STO-082 | Store separate from notes | NF | P1 | Ingest notes | Store written only to store path; note files never modified | §1.5 |
| TC-STO-083 | Single-user assumption | NF | P3 | Two processes writing at once | Documented as unsupported (§11); at minimum no corrupt file thanks to atomic write | §11 |

---

## Questions affecting this module

- **QA-32:** Is the store JSON or SQLite? (Test cases are written for JSON; SQLite would replace TC-STO-044/062/063.) And should an empty store file be treated as empty or as an error?
