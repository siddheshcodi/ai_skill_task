# M2 — Note Reader

| Item | Detail |
|---|---|
| Module | M2 |
| Source file | `actiontrack/reader.py` |
| Used by | M1 (`ingest`) |
| Feeds | M3 (good notes), M10 (skipped files) |
| Milestone | 3 — Reader + Extractor |
| Source | Requirements §3, §5 M2, FR-ING-01/02/07, E8, E9, E11, Q1 |

## 1. Purpose

Find every `.md` file in a folder, read it safely and extract the header information (meeting date and attendees). Bad files are skipped, never fatal.

## 2. Responsibilities

- List all `.md` files in the given folder; ignore every other file type (E11).
- Read each file safely and handle encoding errors.
- Extract the **meeting date** and the **attendee list**.
- If a file is malformed, add it to the **skipped** list with a reason and continue with the next file (FR-ING-07, NFR-01).

## 3. Input

- `folder`: path to a local folder containing meeting notes.

## 4. Output

For each good file:

| Field | Type | Example |
|---|---|---|
| `file_name` | text | `2026-10-06-sales.md` |
| `title` | text or null | `Weekly Sales Sync` (first `#` heading, optional — used by M9) |
| `meeting_date` | date | `2026-10-06` |
| `attendees` | list of text | `["Priya Shah", "Rahul Mehta", "Anita Rao"]` |
| `text` | text | full file content |

For each skipped file: `file_name` + `reason`.

### Suggested interface

```python
@dataclass
class Note:
    file_name: str
    title: str | None
    meeting_date: date
    attendees: list[str]
    text: str

@dataclass
class SkippedFile:
    file_name: str
    reason: str

def read_notes(folder: Path) -> tuple[list[Note], list[SkippedFile]]: ...
```

## 5. Parsing rules

| Field | Expected format | Flexibility |
|---|---|---|
| Meeting date | `Date: 2026-10-06` | Case-insensitive label; optional bold (`**Date:**`); extra spaces. Other formats to be confirmed from sample notes (Q1). |
| Attendees | `Attendees: Priya Shah, Rahul Mehta` | Case-insensitive label; comma-separated; trim spaces; drop empty entries. |

- Encoding: try UTF-8 (and UTF-8 with BOM); on failure, skip with reason `cannot read file (encoding error)`.
- File order: process files in a stable order (sorted by name) so IDs and results are repeatable.

## 6. Malformed files (skip reasons)

| Condition | Reason text |
|---|---|
| File is empty / only whitespace | `file is empty` |
| No meeting date found | `no meeting date found` |
| Date found but not a valid date | `invalid meeting date '<value>'` |
| Cannot decode file | `cannot read file (encoding error)` |
| Any other unexpected error | `unexpected error: <message>` |

> **Open decision:** A note with a date but **no attendees** is not listed as malformed in the requirements. Working assumption: read it normally with an empty attendee list (owners then fall through to "not in attendee list", E7).

## 7. Edge cases

| # | Case | Behaviour |
|---|---|---|
| E8 | No date, empty or unreadable file | Skipped with reason; other files still processed |
| E9 | Very long or messy note | Read normally |
| E11 | Non-`.md` files | Ignored (not counted as skipped) |

## 8. Open questions

- **Q1:** Exact date/attendee format must be confirmed by inspecting the sample `notes/` folder. Working assumption: `Date: YYYY-MM-DD`, `Attendees: A, B, C`.

## 9. Tests (fixtures in `tests/fixtures/`)

- Valid note → correct date, attendees, title.
- Empty file, missing date, invalid date, bad encoding → skipped with the right reason.
- Folder with `.txt`/`.pdf` files → ignored.
- One bad file among good ones → good ones still returned.

## 10. Acceptance criteria

- [ ] All `.md` files in the folder are read or reported as skipped.
- [ ] No single file can crash the reader.
