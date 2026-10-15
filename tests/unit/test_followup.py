"""M9 Follow-up tests (modules/m09-followup-email/test_cases.md).

Seed store as in the M8 test cases plus an owner who is not in people.yaml;
today = 2026-10-15.
"""

from __future__ import annotations

import io
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from actiontrack.drafts import HandoffDraftCreator
from actiontrack.errors import AmbiguousOwnerError, ConfigError, DraftError, NotFoundError
from actiontrack.followup import (
    collect_items,
    compose_email,
    resolve_followup_owner,
    run_followup,
)
from actiontrack.models import Email, Item
from actiontrack.people import load_people

TODAY = date(2026, 10, 15)
TITLE = "Weekly Sales Sync"
SEED = [
    # id, owner, task, due, status, title, candidates
    (1, "Priya Shah", "send the revised quote", "2026-10-09", "open", TITLE, []),
    (2, "Rahul Mehta", "update the CRM", "2026-10-20", "open", TITLE, []),
    (3, "Anita Rao", "book the demo room", "2026-10-08", "done", TITLE, []),
    (4, "unassigned", "share the slide deck", None, "open", TITLE, []),
    (5, "ambiguous", "review contract", "2026-10-14", "open", None, ["Priya Shah", "Priya Kumar"]),
    (6, "Priya Kumar", "prepare invoice", "2026-10-15", "open", None, []),
    (7, "Priya Shah", "update pricing sheet", None, "open", TITLE, []),
    (8, "Rahul Mehta", "call the client", "2026-10-16", "open", TITLE, []),
    (9, "Vikram", "review the budget", None, "open", TITLE, []),
]
PEOPLE_YAML = """\
sender: Team Lead
Priya Shah: priya.shah@example.com
Rahul Mehta: rahul.mehta@example.com
Anita Rao: anita.rao@example.com
Priya Kumar: priya.kumar@example.com
"""


def make_item(item_id, owner, task, due, status, title, candidates) -> Item:
    meeting = date(2026, 10, 6)
    return Item(
        id=item_id,
        owner=owner,
        owner_candidates=list(candidates),
        task=task,
        raw_text=task,
        status=status,
        meeting_date=meeting,
        last_seen_meeting_date=meeting,
        due_date=date.fromisoformat(due) if due else None,
        source_files=["legal-1008.md" if title is None else "sales-1006.md"],
        meeting_title=title,
    )


@pytest.fixture
def items() -> list[Item]:
    return [make_item(*row) for row in SEED]


@pytest.fixture
def people_file(tmp_path) -> Path:
    path = tmp_path / "people.yaml"
    path.write_text(PEOPLE_YAML, encoding="utf-8")
    return path


class FakeCreator:
    def __init__(self) -> None:
        self.drafts: list[Email] = []

    def create_draft(self, email: Email) -> str:
        self.drafts.append(email)
        return f"draft-{len(self.drafts)}"


@pytest.fixture
def creator() -> FakeCreator:
    return FakeCreator()


@pytest.fixture
def run(items, people_file, creator, monkeypatch):
    monkeypatch.delenv("ACTIONTRACK_SENDER", raising=False)

    def invoke(query: str, dry_run: bool = False, people: Path | None = None):
        out, err = io.StringIO(), io.StringIO()
        run_followup(
            query,
            items,
            people or people_file,
            lambda: creator,
            dry_run=dry_run,
            today=TODAY,
            out=out,
            err=err,
        )
        return out.getvalue(), err.getvalue()

    return invoke


# ---------------------------------------------------------------- collecting


def ids(items: list[Item]) -> list[int]:
    return [item.id for item in items]


def test_open_and_overdue_collected(items):  # TC-FUP-001, TC-FUP-002, FR-FUP-01
    overdue, open_ = collect_items(items, "Priya Shah", TODAY)
    assert (ids(overdue), ids(open_)) == ([1], [7])


def test_done_and_ambiguous_items_excluded(items):  # TC-FUP-003, TC-FUP-004 (Q5)
    assert collect_items(items, "Anita Rao", TODAY) == ([], [])
    assert ids(collect_items(items, "Priya Kumar", TODAY)[1]) == [6]


def test_due_today_is_open_not_overdue(items):  # TC-FUP-005
    overdue, open_ = collect_items(items, "Priya Kumar", TODAY)
    assert (overdue, ids(open_)) == ([], [6])


def test_sections_sorted_by_due_date(items):  # TC-FUP-006
    assert ids(collect_items(items, "Rahul Mehta", TODAY)[1]) == [8, 2]


# ---------------------------------------------------------------- owner matching


@pytest.mark.parametrize(
    ("query", "owner"),
    [
        ("Rahul Mehta", "Rahul Mehta"),  # TC-FUP-020
        ("rahul", "Rahul Mehta"),  # TC-FUP-021
        ("RAHUL", "Rahul Mehta"),  # TC-FUP-022
        ("  priya   shah ", "Priya Shah"),
        ("Vikram", "Vikram"),
    ],
)
def test_owner_resolution(items, query, owner):
    assert resolve_followup_owner(items, query) == owner


def test_first_name_matching_two_people(items):  # TC-FUP-023, FR-FUP-05
    with pytest.raises(AmbiguousOwnerError, match="Priya Kumar, Priya Shah"):
        resolve_followup_owner(items, "priya")


def test_unknown_owner(items):  # TC-FUP-024
    with pytest.raises(NotFoundError, match="No items found for 'Bob'"):
        resolve_followup_owner(items, "Bob")


@pytest.mark.parametrize("query", ["unassigned", "Ambiguous"])
def test_groups_get_no_email(items, query):  # TC-FUP-025 (Q5)
    with pytest.raises(NotFoundError, match="no follow-up email"):
        resolve_followup_owner(items, query)


# ---------------------------------------------------------------- email content

EXPECTED_PRIYA = """\
Hi Priya,

A quick reminder of your action items from recent meetings:

Overdue
  • Send the revised quote (due 2026-10-09, from Weekly Sales Sync)

Open
  • Update pricing sheet (no due date, from Weekly Sales Sync)

Please reply if any of these are already done or need a new date.

Thanks,
Team Lead
"""


def test_email_matches_template(run, creator):  # TC-FUP-040..046, 051, FR-FUP-02
    run("Priya Shah")
    (email,) = creator.drafts
    assert email.to == "priya.shah@example.com"  # TC-FUP-060
    assert email.subject == "Follow-up: your open action items (2)"
    assert email.body == EXPECTED_PRIYA


def test_subject_with_one_item(run, creator):  # TC-FUP-041 (QA-38)
    run("Priya Kumar")
    assert creator.drafts[0].subject == "Follow-up: your open action items (1)"


def test_missing_title_uses_source_file(run, creator):  # TC-FUP-047
    run("Priya Kumar")
    assert "Prepare invoice (due 2026-10-15, from legal-1008.md)" in creator.drafts[0].body


def test_only_open_section(run, creator):  # TC-FUP-050
    run("rahul")
    body = creator.drafts[0].body
    assert "Overdue" not in body
    assert body.index("Call the client") < body.index("Update the CRM")


def test_only_overdue_section(items):  # TC-FUP-049
    overdue, _ = collect_items(items, "Priya Shah", TODAY)
    body = compose_email("Priya Shah", "p@example.com", overdue, [], "Me").body
    assert "Overdue" in body and "\nOpen\n" not in body


def test_single_word_name_greeting():  # TC-FUP-043
    item = make_item(1, "Anita", "t", None, "open", None, [])
    assert compose_email("Anita", "a@example.com", [], [item], "Me").body.startswith("Hi Anita,")


def test_special_characters_stay_plain_text():  # TC-FUP-052, TC-FUP-053
    item = make_item(1, "José Núñez", 'send <b>"Q&A"</b> deck 🚀', None, "open", None, [])
    email = compose_email("José Núñez", "jose@example.com", [], [item], "Me")
    assert email.body.startswith("Hi José,")
    assert 'Send <b>"Q&A"</b> deck 🚀 (no due date, from legal-1008.md)' in email.body


def test_sender_from_environment(run, creator, monkeypatch):  # Q4
    monkeypatch.setenv("ACTIONTRACK_SENDER", "Asha (PM)")
    run("Priya Shah")
    assert creator.drafts[0].body.endswith("Thanks,\nAsha (PM)\n")


def test_default_sender(run, creator, tmp_path):
    people = tmp_path / "p.yaml"
    people.write_text("Priya Shah: priya.shah@example.com\n", encoding="utf-8")
    run("Priya Shah", people=people)
    assert creator.drafts[0].body.endswith("Thanks,\nactiontrack\n")


# ---------------------------------------------------------------- draft / dry run flow


def test_draft_created_once(run, creator):  # TC-FUP-080, FR-FUP-03
    out, _ = run("Priya Shah")
    assert len(creator.drafts) == 1
    assert "draft-1" in out
    assert "nothing is sent" in out


def test_no_open_items_no_draft(run, creator):  # TC-FUP-084, FR-FUP-06
    out, _ = run("Anita")
    assert out.strip() == "Anita Rao has no open action items. No draft created."
    assert creator.drafts == []


def test_dry_run_prints_and_creates_nothing(run, creator):  # TC-FUP-083, FR-FUP-07
    out, _ = run("Priya Shah", dry_run=True)
    assert creator.drafts == []
    assert out.startswith("To: priya.shah@example.com\nSubject: Follow-up: your open action items")
    assert EXPECTED_PRIYA in out
    assert out.rstrip().endswith("(dry run: no draft created)")


def test_missing_email_is_an_error(run, creator, tmp_path):  # TC-FUP-061, FR-FUP-08
    with pytest.raises(ConfigError, match="No email address for Vikram"):
        run("Vikram")
    assert creator.drafts == []


def test_dry_run_with_missing_email_warns(run, creator):  # TC-FUP-067 (QA-40)
    out, err = run("Vikram", dry_run=True)
    assert out.startswith("To: <unknown>")
    assert "No email address for Vikram" in err
    assert creator.drafts == []


def test_run_twice_creates_two_drafts(run, creator):  # TC-FUP-085 (QA-41)
    run("Priya Shah")
    run("Priya Shah")
    assert len(creator.drafts) == 2


# ---------------------------------------------------------------- people.yaml


def write_people(tmp_path, text: str) -> Path:
    path = tmp_path / "people.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_people_lookup_is_case_insensitive(tmp_path):  # TC-FUP-066 (QA-39)
    people = load_people(write_people(tmp_path, "rahul  mehta: rahul@example.com\n"))
    assert people.email_for("Rahul Mehta") == "rahul@example.com"


def test_people_sender_key(people_file):
    assert load_people(people_file).sender == "Team Lead"


def test_people_file_missing(tmp_path):  # TC-FUP-062
    with pytest.raises(ConfigError, match=r"people\.yaml\.example"):
        load_people(tmp_path / "people.yaml")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("Priya Shah: [unclosed\n", "not valid YAML"),  # TC-FUP-063
        ("- Priya Shah\n- Rahul Mehta\n", "must contain lines like"),
    ],
)
def test_people_file_invalid(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message):
        load_people(write_people(tmp_path, text))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('Rahul Mehta: ""\n', "No email address"),  # TC-FUP-064
        ("Rahul Mehta:\n", "No email address"),
        ("Rahul Mehta: rahul-at-example\n", "is not valid"),  # TC-FUP-065 (QA-39)
    ],
)
def test_people_bad_email(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message):
        load_people(write_people(tmp_path, text)).email_for("Rahul Mehta")


def test_empty_people_file(tmp_path):
    with pytest.raises(ConfigError, match="No email address"):
        load_people(write_people(tmp_path, "")).email_for("Rahul Mehta")


# ---------------------------------------------------------------- hand-off creator


EMAIL = Email("priya.shah@example.com", "Follow-up: your open action items (2)", "Hi Priya,\n")
NOW = datetime(2026, 10, 15, 9, 30, 0)


def test_handoff_writes_draft_file(tmp_path):  # TC-FUP-104
    path = Path(HandoffDraftCreator(tmp_path / "outbox", now=lambda: NOW).create_draft(EMAIL))
    assert path.name == "20261015-093000-priya-shah.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "action": "create_draft",
        "to": "priya.shah@example.com",
        "subject": "Follow-up: your open action items (2)",
        "body": "Hi Priya,\n",
        "created_at": "2026-10-15T09:30:00",
    }


def test_handoff_never_overwrites(tmp_path):
    creator = HandoffDraftCreator(tmp_path, now=lambda: NOW)
    first, second = creator.create_draft(EMAIL), creator.create_draft(EMAIL)
    assert first != second
    assert Path(second).name == "20261015-093000-priya-shah-2.json"


def test_handoff_unwritable_outbox(tmp_path):  # TC-FUP-100..102
    blocker = tmp_path / "outbox"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    with pytest.raises(DraftError, match="--dry-run"):
        HandoffDraftCreator(blocker).create_draft(EMAIL)


def test_handoff_unicode(tmp_path):
    email = Email("jose@example.com", "Follow-up", "Hi José 🚀\n")
    path = Path(HandoffDraftCreator(tmp_path).create_draft(email))
    assert json.loads(path.read_text(encoding="utf-8"))["body"] == "Hi José 🚀\n"
