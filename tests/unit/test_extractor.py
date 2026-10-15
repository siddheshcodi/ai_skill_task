"""M3 Action Item Extractor tests (modules/m03-item-extractor/test_cases.md)."""

from __future__ import annotations

import time
from datetime import date

import pytest

from actiontrack.extractor import extract_items, parse_checkbox, split_line
from actiontrack.models import Note


def note(text: str) -> Note:
    return Note("a.md", None, date(2026, 10, 6), ["Priya Shah"], text)


# ---------------------------------------------------------------- checkbox detection


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("- [ ] Priya to send the quote", "open"),  # TC-EXT-001
        ("- [x] Anita to book the room", "done"),  # TC-EXT-002
        ("- [X] Anita to book the room", "done"),  # TC-EXT-003
        ("* [ ] Rahul will update the CRM", "open"),  # TC-EXT-004
        ("+ [ ] Rahul will update the CRM", "open"),  # TC-EXT-005
        ("-[ ] Rahul will update the CRM", "open"),  # TC-EXT-006
        ("-   [ ]    Rahul will update the CRM   ", "open"),  # TC-EXT-007
        ("    - [ ] Rahul will update the CRM", "open"),  # TC-EXT-008
        ("\t- [ ] Rahul will update the CRM", "open"),  # TC-EXT-009
        ("- [] Priya to send quote", "open"),  # TC-EXT-010 (QA-9)
        ("- [ x ] Priya to send quote", "done"),  # TC-EXT-011
        ("- [  ] Priya to send quote", "open"),
    ],
)
def test_checkbox_status(line, expected):
    status, body = parse_checkbox(line)
    assert status == expected
    assert body == body.strip()


@pytest.mark.parametrize(
    "line",
    [
        "- [-] Priya to send quote",  # TC-EXT-012
        "- [~] Priya to send quote",
        "- [✓] Priya to send quote",
        "1. [ ] Priya to send quote",  # TC-EXT-013
        "[ ] Priya to send quote",  # TC-EXT-014
        "- [ ]",  # TC-EXT-015
        "- [ ]    ",
        "- Priya to send quote",  # TC-EXT-016
        "Priya will send the quote by Friday",  # TC-EXT-017
        "## Action items",  # TC-EXT-018
        "- [link](http://example.com) text",
    ],
)
def test_not_a_checkbox(line):
    assert parse_checkbox(line) is None


@pytest.mark.edge("E9")
def test_code_blocks_and_quotes_are_ignored():  # TC-EXT-019, TC-EXT-020 (QA-10)
    text = (
        "```\n- [ ] in code\n```\n~~~\n- [ ] in tilde code\n~~~\n> - [ ] quoted\n- [ ] real one\n"
    )
    assert [i.raw_text for i in extract_items(note(text))] == ["real one"]


def test_items_in_any_section():  # TC-EXT-021
    text = "## Discussion\n- [ ] Priya to send quote\n## Action items\n- [ ] Rahul will call\n"
    assert len(extract_items(note(text))) == 2


SAMPLE = """\
# Weekly Sales Sync
Date: 2026-10-06
Attendees: Priya Shah, Rahul Mehta, Anita Rao

## Discussion
Client asked for a lower price on the annual plan...

## Action items
- [ ] Priya to send the revised quote by Friday
- [ ] Rahul will update the CRM by 2026-10-12
- [x] Anita to book the demo room
- [ ] Share the slide deck with the client
"""


def test_sample_note_from_requirements():  # TC-EXT-022, TC-EXT-023
    items = extract_items(note(SAMPLE))
    assert [(i.status, i.owner_phrase, i.task, i.due_phrase, i.line_number) for i in items] == [
        ("open", "Priya", "send the revised quote", "by Friday", 9),
        ("open", "Rahul", "update the CRM", "by 2026-10-12", 10),
        ("done", "Anita", "book the demo room", None, 11),
        ("open", None, "Share the slide deck with the client", None, 12),
    ]
    assert items[0].raw_text == "Priya to send the revised quote by Friday"


def test_crlf_line_endings():  # TC-EXT-024
    items = extract_items(note(SAMPLE.replace("\n", "\r\n")))
    assert len(items) == 4
    assert all("\r" not in i.raw_text for i in items)


# ---------------------------------------------------------------- owner phrase


@pytest.mark.parametrize(
    ("text", "owner", "task", "due"),
    [
        # spec table / TC-EXT-030..034
        (
            "Priya to send the revised quote by Friday",
            "Priya",
            "send the revised quote",
            "by Friday",
        ),
        ("Rahul will update the CRM by 2026-10-12", "Rahul", "update the CRM", "by 2026-10-12"),
        ("@Anita book the demo room", "Anita", "book the demo room", None),
        ("Priya: send the revised quote", "Priya", "send the revised quote", None),
        (
            "Share the slide deck with the client",
            None,
            "Share the slide deck with the client",
            None,
        ),
        # names / TC-EXT-035..039
        ("Priya Shah to send the quote", "Priya Shah", "send the quote", None),
        ("Priya S. to send the quote", "Priya S.", "send the quote", None),
        ("Priya S to send the quote", "Priya S", "send the quote", None),
        ("priya to send the quote", None, "priya to send the quote", None),
        ("@Priya Shah send the quote", "Priya Shah", "send the quote", None),
        ("@priya send the quote", "priya", "send the quote", None),
        # not owners / TC-EXT-040..042
        ("Send deck to client", None, "Send deck to client", None),
        ("Check whether client will renew", None, "Check whether client will renew", None),
        ("Please review the contract", None, "Please review the contract", None),
        ("Finance to approve the budget", "Finance", "approve the budget", None),
        # multiple owners, unicode, will be / TC-EXT-043..046
        ("Priya and Rahul to prepare the demo", "Priya and Rahul", "prepare the demo", None),
        ("Zoë O'Brien to send notes", "Zoë O'Brien", "send notes", None),
        ("Priya will be sending the deck", "Priya", "be sending the deck", None),
        ("Send the quote (Priya)", None, "Send the quote (Priya)", None),
    ],
)
def test_split_owner(text, owner, task, due):
    assert split_line(text) == (owner, task, due)


@pytest.mark.edge("E3")
def test_no_owner_gives_none():  # TC-EXT-034
    owner, _, _ = split_line("Share the slide deck with the client")
    assert owner is None


# ---------------------------------------------------------------- due phrase


@pytest.mark.parametrize(
    ("text", "task", "due"),
    [
        ("Priya to send the quote by Friday", "send the quote", "by Friday"),  # TC-EXT-060
        ("Rahul to update the CRM by 2026-10-12", "update the CRM", "by 2026-10-12"),  # 061
        ("Rahul to call the client on Monday", "call the client", "on Monday"),  # 062
        ("Rahul to send report by 12/10/2026", "send report", "by 12/10/2026"),  # 063
        ("Rahul to send report by Oct 12", "send report", "by Oct 12"),  # 064
        ("Rahul to send report tomorrow", "send report", "tomorrow"),  # 065
        ("Rahul to send report EOD", "send report", "EOD"),
        ("Rahul to send report EOW", "send report", "EOW"),
        ("Rahul to send report next week", "send report", "next week"),
        ("Rahul to send report end of month", "send report", "end of month"),
        ("Rahul to send report today", "send report", "today"),
        ("Rahul to send report end of the week", "send report", "end of the week"),
        ("Rahul to send report due Friday", "send report", "due Friday"),  # 066
        ("Rahul to send report before Oct 12", "send report", "before Oct 12"),
        ("Rahul to send report by 12 October 2026", "send report", "by 12 October 2026"),
        ("Rahul to send report by Oct 12th", "send report", "by Oct 12th"),
        ("Rahul to send report by next Friday", "send report", "by next Friday"),
        ("Priya to send the quote soon", "send the quote", "soon"),  # TC-EXT-067
        ("Priya to send the quote by ASAP", "send the quote", "by ASAP"),
        ("Priya to send the quote in 2 days", "send the quote", "in 2 days"),
        ("Priya to get sign-off by the client", "get sign-off by the client", None),  # 068
        ("Rahul to review by Priya's notes by Friday", "review by Priya's notes", "by Friday"),
        ("Priya to send the quote by Friday.", "send the quote", "by Friday"),  # TC-EXT-071
        ("Priya to send the quote (by Fri)", "send the quote", "by Fri"),  # TC-EXT-072
        ("Priya to send the quote BY FRIDAY", "send the quote", "BY FRIDAY"),
        ("Priya to send the quote", "send the quote", None),  # TC-EXT-073
        ("Priya to review the Monday report", "review the Monday report", None),
    ],
)
def test_split_due(text, task, due):
    _, got_task, got_due = split_line(text)
    assert (got_task, got_due) == (task, due)


@pytest.mark.edge("E5")
def test_unclear_due_phrase_is_kept():  # TC-EXT-067
    assert split_line("Priya to send the quote soon")[2] == "soon"


def test_line_that_is_only_a_due_phrase_keeps_its_text():
    assert split_line("tomorrow") == (None, "tomorrow", None)


# ---------------------------------------------------------------- messy content


@pytest.mark.edge("E9")
def test_markdown_formatting_removed():  # TC-EXT-080
    owner, task, due = split_line("**Priya** to send the [quote](http://x) by `Friday`")
    assert (owner, task, due) == ("Priya", "send the quote", "by Friday")


def test_emoji():  # TC-EXT-081
    assert split_line("Priya to send the quote 🚀 by Friday") == (
        "Priya",
        "send the quote 🚀",
        "by Friday",
    )


def test_very_long_line():  # TC-EXT-082
    owner, task, _ = split_line("Priya to " + "do the thing " * 150)
    assert owner == "Priya"
    assert len(task) > 1500


def test_many_items():  # TC-EXT-083
    text = "\n".join(f"- [ ] Priya to do task {i}" for i in range(500))
    assert len(extract_items(note(text))) == 500


def test_done_item_is_split_like_open():  # TC-EXT-084
    item = extract_items(note("- [x] Priya to send quote by Friday"))[0]
    assert (item.status, item.owner_phrase, item.task, item.due_phrase) == (
        "done",
        "Priya",
        "send quote",
        "by Friday",
    )


@pytest.mark.edge("E1")
def test_same_task_twice_in_one_note_both_extracted():  # TC-EXT-085
    text = "- [ ] Priya to send quote\n- [ ] Priya to send quote\n"
    assert len(extract_items(note(text))) == 2


# ---------------------------------------------------------------- non-functional


@pytest.mark.perf
@pytest.mark.parametrize(
    "line",
    [
        " " * 10_000 + "[" * 10_000,
        "Priya " + "to " * 5_000 + "x",
        "Rahul to send " + "by " * 5_000 + "Fri",
        "- [ ] " + "a " * 10_000 + "on",
    ],
)
def test_no_catastrophic_backtracking(line):  # TC-EXT-090
    start = time.perf_counter()
    split_line(line)
    parse_checkbox(line)
    assert time.perf_counter() - start < 0.1


def test_extraction_is_repeatable():  # TC-EXT-091
    n = note(SAMPLE)
    assert extract_items(n) == extract_items(n)
