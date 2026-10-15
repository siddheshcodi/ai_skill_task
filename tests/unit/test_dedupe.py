"""M6 Deduplicator unit tests (modules/m06-deduplicator/test_cases.md)."""

from __future__ import annotations

from datetime import date

import pytest

from actiontrack.dedupe import (
    DedupeIndex,
    conflicting_tokens,
    dedupe_into,
    merge,
    normalize_task,
    owner_key,
    similarity,
    to_new_item,
)
from actiontrack.models import AMBIGUOUS, UNASSIGNED, Note, OwnerResult, RawItem, ResolvedItem
from actiontrack.store import Store

N1 = Note("n1.md", "Sales", date(2026, 10, 6), [], "")
N2 = Note("n2.md", "Sales", date(2026, 10, 13), [], "")
N3 = Note("n3.md", "Sales", date(2026, 10, 20), [], "")


def resolved(
    task: str,
    owner: str = "Priya Shah",
    note: Note = N1,
    due: date | None = None,
    due_phrase: str | None = None,
    status: str = "open",
    candidates: list[str] | None = None,
) -> ResolvedItem:
    raw = RawItem(task, None, task, due_phrase, status, 1)
    return ResolvedItem(raw, OwnerResult(owner, candidates or []), due, note)


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "s.json")


def ingest(store: Store, *items: ResolvedItem):
    index = DedupeIndex(store.load_all())
    return dedupe_into(store, list(items), index)


# ---------------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    ("task", "due", "expected"),
    [
        ("Send The Revised Quote", None, "send the revised quote"),  # TC-DUP-001
        ("send the revised quote!!!", None, "send the revised quote"),  # TC-DUP-002
        ("send the revised-quote.", None, "send the revisedquote"),
        ("send the revised quote by Friday", "by Friday", "send the revised quote"),  # TC-DUP-003
        ("send   the  revised quote ", None, "send the revised quote"),  # TC-DUP-004
        ("send the quote 🚀", None, "send the quote"),  # TC-DUP-005
        ("réunion notes", None, "réunion notes"),
        ("!!!", None, ""),  # TC-DUP-006
    ],
)
def test_normalize_task(task, due, expected):
    assert normalize_task(task, due) == expected


def test_owner_key():
    assert owner_key("Priya Shah", []) == "priya shah"
    assert owner_key(UNASSIGNED, []) == "unassigned"
    assert owner_key(AMBIGUOUS, ["Priya Shah", "Priya Kumar"]) == owner_key(
        AMBIGUOUS, ["priya kumar", "Priya Shah"]
    )


# ---------------------------------------------------------------- duplicate decision


def assert_merged(store, *items, expected_count):
    ingest(store, *items)
    assert len(store.load_all()) == expected_count


@pytest.mark.edge("E1")
@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("send the revised quote", "send the revised quote"),  # TC-DUP-020
        ("Send the revised quote.", "send the revised quote"),  # TC-DUP-021
        ("send the revised quote", "send the revised quotes"),  # TC-DUP-023
        ("update the CRM", "update the crm"),
    ],
)
def test_same_task_merges(store, a, b):
    assert_merged(store, resolved(a), resolved(b, note=N2), expected_count=1)


def test_different_due_phrase_only_merges(store):  # TC-DUP-022
    first = resolved("send the quote", due_phrase="by Friday")
    second = resolved("send the quote", note=N2, due_phrase="by Monday")
    assert_merged(store, first, second, expected_count=1)


@pytest.mark.parametrize(
    ("a", "b", "owner_b"),
    [
        ("send the revised quote", "update the CRM", "Priya Shah"),  # TC-DUP-024
        ("send the quote", "send the quote", "Rahul Mehta"),  # TC-DUP-025
    ],
)
def test_not_duplicates(store, a, b, owner_b):
    assert_merged(store, resolved(a), resolved(b, owner=owner_b, note=N2), expected_count=2)


def test_threshold_is_inclusive(store):  # TC-DUP-026..028, TC-DUP-092
    a, b = "send the revised quote", "send the revision of quote"
    score = similarity(normalize_task(a), normalize_task(b))
    item = store.add(to_new_item(resolved(a)))
    assert DedupeIndex([item], threshold=score).find(resolved(b)) is item
    assert DedupeIndex([item], threshold=score + 0.001).find(resolved(b)) is None


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("call Rahul", "call Anita"),  # TC-DUP-029 (QA-26)
        ("send the revised quote to Acme Corp", "send the revised quote to Acme Co"),  # TC-DUP-030
        ("update Q3 forecast numbers", "update Q4 forecast numbers"),
    ],
)
def test_guard_blocks_merging_different_names_or_numbers(store, a, b):
    assert conflicting_tokens(a, b)
    assert_merged(store, resolved(a), resolved(b, note=N2), expected_count=2)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("send the revised quote to Acme Corp", "send the revised quote to Acme Co"),
        ("update Q3 forecast numbers", "update Q4 forecast numbers"),
    ],
)
def test_guard_is_what_blocks_high_similarity_pairs(a, b):
    # these pairs pass the 85% rule on their own; only the guard keeps them apart
    assert similarity(normalize_task(a), normalize_task(b)) >= 0.85


def test_guard_ignores_case_and_first_word():
    assert not conflicting_tokens("Update the CRM", "update the crm")
    assert not conflicting_tokens("Send the quote", "send the quote")


@pytest.mark.edge("E3")
def test_unassigned_items_dedupe_by_text(store):  # TC-DUP-031
    assert_merged(
        store,
        resolved("share the slide deck", owner=UNASSIGNED),
        resolved("share the slide deck", owner=UNASSIGNED, note=N2),
        expected_count=1,
    )


@pytest.mark.edge("E6")
def test_ambiguous_same_candidates_merge(store):  # TC-DUP-032
    both = ["Priya Shah", "Priya Kumar"]
    assert_merged(
        store,
        resolved("review contract", owner=AMBIGUOUS, candidates=both),
        resolved("review contract", owner=AMBIGUOUS, candidates=both[::-1], note=N2),
        expected_count=1,
    )


@pytest.mark.edge("E6")
def test_ambiguous_different_candidates_do_not_merge(store):  # TC-DUP-033
    assert_merged(
        store,
        resolved("review contract", owner=AMBIGUOUS, candidates=["Priya Shah", "Priya Kumar"]),
        resolved(
            "review contract", owner=AMBIGUOUS, candidates=["Priya Shah", "Priya Khan"], note=N2
        ),
        expected_count=2,
    )


def test_ambiguous_then_resolved_stay_separate(store):  # TC-DUP-034 (QA-27)
    assert_merged(
        store,
        resolved("review contract", owner=AMBIGUOUS, candidates=["Priya Shah", "Priya Kumar"]),
        resolved("review contract", owner="Priya Shah", note=N2),
        expected_count=2,
    )


@pytest.mark.edge("E1")
def test_same_task_twice_in_one_note(store):  # TC-DUP-035
    outcomes = ingest(store, resolved("send quote"), resolved("send quote"))
    assert [o.created for o in outcomes] == [True, False]
    assert store.get(1).source_files == ["n1.md"]


def test_best_match_wins(store):  # TC-DUP-036
    store.add(to_new_item(resolved("send the revised quote now")))
    store.add(to_new_item(resolved("send the revised quote")))
    outcomes = ingest(store, resolved("send the revised quote", note=N2))
    assert outcomes[0].item.id == 2
    assert len(store.load_all()) == 2


def test_empty_text_merges_only_on_identical_line(store):  # TC-DUP-006 (QA-25)
    assert_merged(store, resolved("!!!"), resolved("???", note=N2), expected_count=2)
    assert_merged(store, resolved("!!!", note=N3), expected_count=2)


# ---------------------------------------------------------------- merge rules


def test_new_item_fields():
    item = to_new_item(resolved("send quote", due=date(2026, 10, 9), due_phrase="by Friday"))
    assert (item.source_files, item.meeting_date, item.last_seen_meeting_date) == (
        ["n1.md"],
        date(2026, 10, 6),
        date(2026, 10, 6),
    )
    assert (item.due_date, item.due_phrase, item.meeting_title) == (
        date(2026, 10, 9),
        "by Friday",
        "Sales",
    )


@pytest.mark.edge("E1")
def test_newer_meeting_due_date_wins():  # TC-DUP-052
    item = to_new_item(resolved("q", due=date(2026, 10, 9), due_phrase="by Friday"))
    assert merge(item, resolved("q", note=N2, due=date(2026, 10, 20), due_phrase="by 2026-10-20"))
    assert (item.due_date, item.due_phrase) == (date(2026, 10, 20), "by 2026-10-20")
    assert item.source_files == ["n1.md", "n2.md"]
    assert item.meeting_date == date(2026, 10, 6)  # TC-DUP-060
    assert item.last_seen_meeting_date == date(2026, 10, 13)


@pytest.mark.edge("E1")
def test_older_meeting_does_not_overwrite_due_date():  # TC-DUP-053
    item = to_new_item(resolved("q", note=N2, due=date(2026, 10, 20), due_phrase="by 2026-10-20"))
    merge(item, resolved("q", note=N1, due=date(2026, 10, 9), due_phrase="by Friday"))
    assert item.due_date == date(2026, 10, 20)
    assert item.last_seen_meeting_date == date(2026, 10, 13)
    assert item.source_files == ["n2.md", "n1.md"]


@pytest.mark.parametrize("phrase", [None, "soon"])
def test_newer_meeting_without_date_keeps_old_date(phrase):  # TC-DUP-054/055 (QA-28)
    item = to_new_item(resolved("q", due=date(2026, 10, 9), due_phrase="by Friday"))
    merge(item, resolved("q", note=N2, due=None, due_phrase=phrase))
    assert (item.due_date, item.due_phrase) == (date(2026, 10, 9), "by Friday")


@pytest.mark.edge("E2")
def test_later_done_marks_done():  # TC-DUP-056
    item = to_new_item(resolved("q"))
    assert merge(item, resolved("q", note=N2, status="done"))
    assert item.status == "done"


@pytest.mark.edge("E2")
@pytest.mark.parametrize(("first", "later"), [("done", "open"), ("open", "open")])
def test_ingest_never_reopens(first, later):  # TC-DUP-057/058/059 (QA-29)
    item = to_new_item(resolved("q", status=first))
    item.status = "done"  # done in a note or by `actiontrack done`
    merge(item, resolved("q", note=N2, status=later))
    assert item.status == "done"


def test_first_raw_text_and_title_kept():  # TC-DUP-061 (QA-30)
    item = to_new_item(resolved("send the quote"))
    other = resolved("send the quotes", note=Note("n2.md", "Other", date(2026, 10, 13), [], ""))
    merge(item, other)
    assert (item.raw_text, item.meeting_title) == ("send the quote", "Sales")


def test_merge_reports_no_change_when_nothing_changes():  # TC-DUP-062
    item = to_new_item(resolved("q", due=date(2026, 10, 9), due_phrase="by Friday"))
    assert not merge(item, resolved("q", due=date(2026, 10, 9), due_phrase="by Friday"))


def test_updated_at_only_changes_on_real_change(store):  # TC-DUP-062
    ingest(store, resolved("q"))
    stamp = store.get(1).updated_at
    ingest(store, resolved("q"))
    assert store.get(1).updated_at == stamp
    ingest(store, resolved("q", note=N2))
    assert store.get(1).updated_at >= stamp
    assert store.get(1).source_files == ["n1.md", "n2.md"]


def test_same_meeting_date_two_files_is_deterministic():  # TC-DUP-063
    twin = Note("n1b.md", "Sales", date(2026, 10, 6), [], "")
    item = to_new_item(resolved("q", due=date(2026, 10, 9), due_phrase="by Friday"))
    merge(item, resolved("q", note=twin, due=date(2026, 10, 12), due_phrase="by Monday"))
    assert item.due_date == date(2026, 10, 12)  # later file name in the same meeting wins
