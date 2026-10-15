# M6 — Deduplicator: Test Cases

| Item | Detail |
|---|---|
| Module | M6 Deduplicator (`actiontrack/dedupe.py`) |
| Covers | §5 M6, FR-ING-05, FR-ING-08, E1, E2, E10, Acceptance #2 |
| Test levels | Unit (`normalize_task`, `is_duplicate`, `merge`) + Integration (ingest fixture folders twice) |

**Type key:** F = Functional · N = Negative · E = Edge case · NF = Non-functional
**Priority:** P1 must · P2 important · P3 nice to have · **❓QA-n** = open question

Fixture meetings used below:

- **N1** `2026-10-06-sales.md` — meeting 2026-10-06, attendees Priya Shah, Rahul Mehta
- **N2** `2026-10-13-sales.md` — meeting 2026-10-13, same attendees
- **N3** `2026-10-20-sales.md` — meeting 2026-10-20, same attendees

---

## 1. Text normalisation

| ID | Scenario | Type | Pri | Input task / due phrase | Expected normalised text | Trace |
|---|---|---|---|---|---|---|
| TC-DUP-001 | Lower-case | F | P1 | `Send The Revised Quote` | `send the revised quote` | M6 |
| TC-DUP-002 | Remove punctuation | F | P1 | `send the revised quote!!!` / `send the revised-quote.` | `send the revised quote` / `send the revisedquote` (consistent rule) | M6 |
| TC-DUP-003 | Remove due phrase | F | P1 | `send the revised quote by Friday` with due `by Friday` | `send the revised quote` | M6 |
| TC-DUP-004 | Collapse spaces | F | P1 | `send   the  revised quote ` | `send the revised quote` | M6 |
| TC-DUP-005 | Unicode / emoji | E | P3 | `send the quote 🚀`, `réunion notes` | Stable result; no crash | E9 |
| TC-DUP-006 | Empty after cleaning | E | P3 | `!!!` | Empty string handled; not matched to every other empty item by accident — ❓QA-25 | M6 |

## 2. Duplicate decision (same owner + ≥ 85% similar)

| ID | Scenario | Type | Pri | Item A (N1) | Item B (N2) | Expected | Trace |
|---|---|---|---|---|---|---|---|
| TC-DUP-020 | Identical text, same owner | F | P1 | Priya: `send the revised quote` | Priya: `send the revised quote` | Duplicate → 1 item | E1 |
| TC-DUP-021 | Only case/punctuation differ | F | P1 | `Send the revised quote.` | `send the revised quote` | Duplicate | E1 |
| TC-DUP-022 | Different due phrase only | F | P1 | `… quote by Friday` | `… quote by Monday` | Duplicate (due phrase removed before compare) | E1 |
| TC-DUP-023 | Small wording change ≥ 85% | F | P1 | `send the revised quote` | `send the revised quotes` | Duplicate | M6 |
| TC-DUP-024 | Clearly different task | N | P1 | `send the revised quote` | `update the CRM` | Not duplicate → 2 items | M6 |
| TC-DUP-025 | Same text, different owner | N | P1 | Priya: `send the quote` | Rahul: `send the quote` | Not duplicate → 2 items | M6 |
| TC-DUP-026 | Similarity just below threshold | E | P1 | Pair with ratio ≈ 0.84 | — | Not duplicate | M6 |
| TC-DUP-027 | Similarity exactly at threshold | E | P1 | Pair with ratio = 0.85 | — | Duplicate (≥ rule) | M6 |
| TC-DUP-028 | Similarity just above threshold | E | P2 | Pair with ratio ≈ 0.86 | — | Duplicate | M6 |
| TC-DUP-029 | Short texts, one word changed | E | P1 | `call Rahul` | `call Anita` | ❓QA-26 Ratio may be high but meaning differs — expected **not** duplicate; document result | M6 |
| TC-DUP-030 | Different object, long text | E | P1 | `send the revised quote to Acme Corp` | `send the revised quote to Beta Ltd` | ❓QA-26 Risk of false merge — verify ratio and expected outcome | M6 |
| TC-DUP-031 | Both unassigned, same text | E | P2 | unassigned: `share the slide deck` | unassigned: `share the slide deck` | Duplicate (assumption) | E3 |
| TC-DUP-032 | Both ambiguous, same candidates | E | P2 | ambiguous [Priya Shah, Priya Kumar] | same | Duplicate | E6 |
| TC-DUP-033 | Both ambiguous, different candidates | E | P2 | ambiguous [Shah, Kumar] | ambiguous [Shah, Khan] | Not duplicate | E6 |
| TC-DUP-034 | Ambiguous then resolved | E | P2 | N1: `Priya` (ambiguous) | N2: `Priya Shah` (resolved) | ❓QA-27 Separate items (owner differs) per rule — or upgrade ambiguous item? | E6 |
| TC-DUP-035 | Same task twice in one note | E | P2 | Two identical lines in N1 | — | 1 item; `source_files = [N1]` (no repeat) | E1 |
| TC-DUP-036 | Similar to two existing items | E | P3 | New item ≥ 85% to items #3 and #7 | — | Merged into the best match only (highest score) — no double merge | M6 |

## 3. Merge rules

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-DUP-050 | Source files appended | F | P1 | Same task in N1, N2, N3; ingest | 1 item; `source_files = [N1, N2, N3]` | E1 |
| TC-DUP-051 | No new ID created | F | P1 | Same as above | Only one ID used; `next_id` increments by 1 | M6 |
| TC-DUP-052 | Newest meeting's due date wins | F | P1 | N1 `by Friday` (→10-09), N2 `by 2026-10-20` | `due_date = 2026-10-20`, `due_phrase = by 2026-10-20` | E1 |
| TC-DUP-053 | Older note does not overwrite | E | P1 | Ingest N2 first (`by 2026-10-20`), then folder containing N1 (`by Friday` → 10-09) | `due_date` stays 2026-10-20 (N2 is newer meeting) | E1 |
| TC-DUP-054 | Newer note has no due date | E | P1 | N1 `by Friday`, N2 same task without due phrase | ❓QA-28 Recommended: keep 2026-10-09 (don't erase known date) | E1 |
| TC-DUP-055 | Newer note has unclear due | E | P2 | N1 `by Friday`, N2 `soon` | ❓QA-28 Same question | E1, E5 |
| TC-DUP-056 | Later note marks done | F | P1 | N1 `[ ]`, N2 `[x]` | `status = done` | E2 |
| TC-DUP-057 | Middle note marks done | F | P2 | N1 `[ ]`, N2 `[x]`, N3 `[ ]` | ❓QA-29 Recommended: stays `done` (never re-opened by ingest) | E2 |
| TC-DUP-058 | Older note shows done | E | P2 | N1 `[x]`, N2 `[ ]` | ❓QA-29 Recommended: `done` ("any note marks done") | E2 |
| TC-DUP-059 | Manual done not undone | F | P1 | Ingest N1 `[ ]` → `done <id>` → re-ingest | Status remains `done` | E10, FR-DON-01 |
| TC-DUP-060 | `meeting_date` = first meeting | F | P1 | Same task in N1, N2 | `meeting_date = 2026-10-06` | M7 model |
| TC-DUP-061 | `raw_text` after merge | E | P3 | N1 / N2 wording differs | ❓QA-30 Keep first or newest `raw_text` — consistent | M7 model |
| TC-DUP-062 | `updated_at` changes only on real change | F | P2 | Merge that adds new source file vs. re-ingest with no change | Updated vs unchanged | M6 |
| TC-DUP-063 | Same meeting date, two files | E | P3 | Two notes both dated 2026-10-06, different due dates | Deterministic result (e.g. sorted file name order) | E1 |

## 4. Re-running ingest (idempotency)

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-DUP-070 | Ingest same folder twice | F | P1 | `ingest notes/` ×2 | Store identical (same items, IDs, fields); summary 2nd run: `New items: 0` | FR-ING-08, E10 |
| TC-DUP-071 | Ingest 3+ times | F | P2 | `ingest notes/` ×5 | No change after first run | E10 |
| TC-DUP-072 | New note added between runs | F | P1 | Ingest; add N3 with 1 new + 1 repeated item; ingest | 1 new item (new ID), 1 merged; old IDs unchanged | E10 |
| TC-DUP-073 | Source file not duplicated | F | P1 | Re-ingest | `source_files` has no repeated names | E10 |
| TC-DUP-074 | Note edited between runs | E | P2 | Change task wording in N1 slightly (≥85%), re-ingest | Merged into same item | E10 |
| TC-DUP-075 | Note edited heavily | E | P2 | Change N1 task to unrelated text, re-ingest | New item created; old item remains | E10 |
| TC-DUP-076 | Note deleted between runs | E | P2 | Delete N1, re-ingest | Existing items kept (store is history) — ❓QA-31 | E10 |
| TC-DUP-077 | Note renamed | E | P3 | Rename N1 → `sales-oct6.md`, re-ingest | ❓QA-31 Same item, new name added to `source_files` | E10 |
| TC-DUP-078 | Different folder, same notes | E | P3 | `ingest notes/` then `ingest copy_of_notes/` | No duplicate items | FR-ING-08 |

## 5. Non-functional

| ID | Scenario | Type | Pri | Steps | Expected | Trace |
|---|---|---|---|---|---|---|
| TC-DUP-090 | Dedupe performance | NF | P1 | 50 notes × 10 items against store of 500 items | Completes in < 2 s | NFR-03 |
| TC-DUP-091 | Deterministic | NF | P1 | Same input, different run order of identical files | Same final store | NFR-06 |
| TC-DUP-092 | Threshold configurable | NF | P3 | Change constant to 0.9 | Behaviour follows constant | NFR-05 |

---

## Questions affecting this module

- **QA-25:** Item whose task becomes empty after cleaning — skip it or store it?
- **QA-26:** 85% similarity can merge different tasks (`call Rahul` vs `call Anita`). Accept the risk or add a guard (e.g. require identical names/numbers)?
- **QA-27:** If an ambiguous item (`Priya`) later appears with a resolved owner (`Priya Shah`), merge or keep separate?
- **QA-28:** If the newest meeting has no / unclear due date, keep the old date or clear it?
- **QA-29:** Can ingest ever change a `done` item back to `open`?
- **QA-30:** After merging, keep the first or the newest `raw_text`?
- **QA-31:** If a note is deleted or renamed, what happens to its items / `source_files`?
