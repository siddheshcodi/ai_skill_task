# M3 — Action Item Extractor: Implementation Plan

| Item | Detail |
|---|---|
| File | `actiontrack/extractor.py` |
| Spec | `spec.md` (this folder) |
| Tests | `test_cases.md` — TC-EXT-001 … TC-EXT-091 |
| Milestone | 3 |
| Estimate | 1.0 dev-day |
| Depends on | `models.Note`, `models.RawItem` |
| Used by | `ingest.run_ingest` → M4, M5, M6 |

## 1. Goal

Find every checkbox line in a note and split it into owner phrase, task and due phrase, without mis-splitting normal sentences. The extractor only splits text. Resolving owners and dates is M4 and M5's job.

## 2. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Line scan | Iterate `text.splitlines()` (handles CRLF), track line number and whether we are inside a fenced code block; skip fenced and `>` quoted lines | TC-EXT-019, 020, 024; QA-10 |
| Checkbox regex | `^\s*(?:[-*+]\s*)\[(?P<mark>[ xX]?)\]\s*(?P<body>.*\S)?\s*$` | Covers `- [ ]`, `-[ ]`, `* [ ]`, `+ [ ]`, `- []`, indentation (QA-9 defaults) |
| Status | `x`/`X` → done; space or empty → open; any other mark → not an item | TC-EXT-001..012 |
| Split order | 1) strip markdown formatting → 2) take the due phrase from the **end** → 3) take the owner from the **start** → 4) what remains is the task | Due phrases are mostly at the end; owner patterns are at the start (spec §3) |
| Owner patterns | Ordered list: `@Name`, `Name:`, `Name to`, `Name will` | One table, easy to extend |
| Name token | `[A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*\.?)?` (first name + optional last name or initial); lower-case only for `@name` | Avoids `Send deck to client` (TC-EXT-040); QA-11 default |
| Non-name guard | Block a small stop-list of verbs at the start (`Send`, `Share`, `Check`, `Update`, `Review`…) as owners | Extra safety for `Send … to …` |
| Due phrase detection | Trailing regex: `(?:\b(?:by\|on\|due\|before)\s+)?(?P<when>KNOWN_WHEN)\W*$`, where `KNOWN_WHEN` = date/weekday/keyword patterns **shared with M5** | Keeps M3 and M5 in sync; `by the client` is not stripped (QA-14 default) |
| Unclear phrases | Recognise a trailing `by <word>` / `soon` / `ASAP` as a due phrase only if it is in the `VAGUE_WHEN` list | E5 keeps the original text; avoids eating real task words |
| Markdown cleanup | Remove `**`, `__`, backticks; turn `[text](url)` into `text` | TC-EXT-080 |

> **Shared vocabulary:** `dates.py` exports `WHEN_PATTERN` (the regex of supported due expressions) and `VAGUE_WORDS`. M3 imports them, so it extracts exactly the phrases M5 understands.

## 3. Components

```python
CHECKBOX_RE: Pattern
OWNER_PATTERNS: list[Pattern]

def extract_items(note: Note) -> list[RawItem]: ...
def parse_checkbox(line: str) -> tuple[str, str] | None: ...       # (status, body)
def split_line(body: str) -> tuple[str | None, str, str | None]: ...  # (owner, task, due)
def _strip_markdown(s: str) -> str: ...
def _take_due_phrase(s: str) -> tuple[str, str | None]: ...
def _take_owner(s: str) -> tuple[str | None, str]: ...
```

## 4. Tasks

| # | Task | Est. | Tests |
|---|---|---|---|
| 1 | Checkbox regex, line iteration, code-fence tracking | 1.5 h | TC-EXT-001..024 |
| 2 | Markdown cleanup | 0.5 h | TC-EXT-080..081 |
| 3 | Due phrase extraction using M5's shared `WHEN_PATTERN` | 2 h | TC-EXT-060..073 |
| 4 | Owner extraction (patterns, name token, stop-list) | 2 h | TC-EXT-030..046 |
| 5 | Parametrised test table built from spec §3 and the sample notes | 1.5 h | all |
| 6 | Regex safety test (long pathological input) | 0.5 h | TC-EXT-090 |

## 5. Test approach

- One large `parametrize` table: `line → (status, owner, task, due)`. Every new real-world line found in the sample notes is added as a row (regression corpus).
- A property test (optional, `hypothesis`): `split_line` never raises, and `owner + task + due` never contains text that was not in the input.
- A timing test with `pytest-timeout` guards against catastrophic backtracking.

## 6. Risks

| Risk | Mitigation |
|---|---|
| False owner (`Finance to approve…`) | Owner still goes to M4, which flags it as not in attendees (E7). No data is lost. |
| False due phrase eats task words | Only known date expressions are stripped; unknown `by X` stays in the task |
| Regex drift between M3 and M5 | Shared `WHEN_PATTERN` from `dates.py`; contract test checks that every M5 phrase is extracted by M3 |

## 7. Open questions

QA-9 … QA-14. Defaults: `- []` = open; ignore code blocks; owner must be capitalised (except `@`); teams are allowed as owner phrases (flagged later); `Priya and Rahul` is kept as one phrase (flagged later); `by the client` stays in the task.

## 8. Definition of done

- [ ] Every row of spec §3 and all sample-note lines parse as expected.
- [ ] All P1 TC-EXT cases pass; the backtracking test runs in under 100 ms.
