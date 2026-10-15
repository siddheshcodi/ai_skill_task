"""M5 Date Resolver tests (modules/m05-date-resolver/test_cases.md).

Default meeting: Tue 2026-10-06 (ISO week Mon 10-05 .. Sun 10-11).
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pytest

from actiontrack import dates
from actiontrack.dates import next_weekday_after, resolve_due_date
from actiontrack.extractor import split_line

TUE = date(2026, 10, 6)
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def d(text: str) -> date:
    return date.fromisoformat(text)


# ---------------------------------------------------------------- requirement table


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("2026-10-12", "2026-10-12"),  # TC-DAT-001
        ("by 2026-10-12", "2026-10-12"),
        ("12/10/2026", "2026-10-12"),  # TC-DAT-002
        ("Oct 12", "2026-10-12"),  # TC-DAT-003
        ("by Friday", "2026-10-09"),  # TC-DAT-004
        ("on Monday", "2026-10-12"),  # TC-DAT-005
        ("tomorrow", "2026-10-07"),  # TC-DAT-006
        ("today", "2026-10-06"),  # TC-DAT-007
        ("EOD", "2026-10-06"),  # TC-DAT-008
        ("next week", "2026-10-12"),  # TC-DAT-009
        ("end of week", "2026-10-09"),  # TC-DAT-010
        ("EOW", "2026-10-09"),  # TC-DAT-011
        ("end of month", "2026-10-31"),  # TC-DAT-012
    ],
)
def test_requirement_table(phrase, expected):
    assert resolve_due_date(phrase, TUE) == d(expected)


@pytest.mark.edge("E4")
@pytest.mark.parametrize("phrase", [None, "", "   "])
def test_no_phrase_gives_no_date(phrase):  # TC-DAT-013, TC-DAT-083
    assert resolve_due_date(phrase, TUE) is None


@pytest.mark.edge("E5")
@pytest.mark.parametrize(
    "phrase",
    [
        "soon",  # TC-DAT-014, TC-DAT-080
        "ASAP",
        "by ASAP",
        "later",
        "TBD",
        "when possible",
        "next sprint",
        "Q4",
        "in 2 days",  # TC-DAT-081 (QA-24)
        "in a week",
        "next month",  # TC-DAT-082
        "EOD Friday",  # TC-DAT-084
        "by Friday or Monday",
        "viernes",  # TC-DAT-085
        "demain",
    ],
)
def test_unclear_phrases_give_no_date(phrase):
    assert resolve_due_date(phrase, TUE) is None


def test_result_is_a_date_object():  # TC-DAT-015
    due = resolve_due_date("by Friday", TUE)
    assert type(due) is date
    assert due.isoformat() == "2026-10-09"


def test_relative_to_meeting_not_today():  # TC-DAT-017 (clock check: test_does_not_read_the_clock)
    assert resolve_due_date("tomorrow", TUE) == d("2026-10-07")
    assert resolve_due_date("tomorrow", d("2030-01-01")) == d("2030-01-02")


# ---------------------------------------------------------------- weekday rule


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("by Monday", "2026-10-12"),  # TC-DAT-020
        ("by Tuesday", "2026-10-13"),  # TC-DAT-021 same weekday -> next week
        ("by Wednesday", "2026-10-07"),
        ("by Thursday", "2026-10-08"),
        ("by Friday", "2026-10-09"),
        ("by Saturday", "2026-10-10"),
        ("by Sunday", "2026-10-11"),
    ],
)
def test_every_weekday_from_tuesday(phrase, expected):
    assert resolve_due_date(phrase, TUE) == d(expected)


@pytest.mark.parametrize("meeting_offset", range(7))
@pytest.mark.parametrize("weekday", range(7))
def test_weekday_grid_is_always_strictly_after(meeting_offset, weekday):  # 49 cases
    meeting = d("2026-10-05") + timedelta(days=meeting_offset)  # Mon .. Sun
    due = resolve_due_date(f"by {WEEKDAY_NAMES[weekday]}", meeting)
    assert due.weekday() == weekday
    assert 1 <= (due - meeting).days <= 7


@pytest.mark.parametrize(
    ("phrase", "meeting", "expected"),
    [
        ("by Friday", "2026-10-09", "2026-10-16"),  # TC-DAT-022 (Q6)
        ("by Monday", "2026-10-11", "2026-10-12"),  # TC-DAT-023
        ("by Friday", "2026-10-10", "2026-10-16"),  # TC-DAT-024
        ("by Monday", "2026-10-29", "2026-11-02"),  # TC-DAT-029
        ("by Friday", "2026-12-30", "2027-01-01"),  # TC-DAT-030
    ],
)
def test_weekday_boundaries(phrase, meeting, expected):
    assert resolve_due_date(phrase, d(meeting)) == d(expected)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("by Fri", "2026-10-09"),  # TC-DAT-025
        ("on Mon", "2026-10-12"),
        ("Thu", "2026-10-08"),
        ("by Tues", "2026-10-13"),
        ("by Thurs", "2026-10-08"),
        ("BY FRIDAY", "2026-10-09"),  # TC-DAT-026
        ("by friday", "2026-10-09"),
        ("eod", "2026-10-06"),
        ("Eow", "2026-10-09"),
        ("End Of Month", "2026-10-31"),
        ("by Friday.", "2026-10-09"),  # TC-DAT-027
        ("by Friday!", "2026-10-09"),
        ("(by Friday)", "2026-10-09"),
        ("this Friday", "2026-10-09"),  # TC-DAT-028 (QA-18)
        ("next Friday", "2026-10-09"),
        ("due by Friday", "2026-10-09"),
        ("before Friday", "2026-10-09"),
    ],
)
def test_weekday_spellings(phrase, expected):
    assert resolve_due_date(phrase, TUE) == d(expected)


# ---------------------------------------------------------------- relative keywords


@pytest.mark.parametrize(
    ("phrase", "meeting", "expected"),
    [
        ("tomorrow", "2026-10-31", "2026-11-01"),  # TC-DAT-040
        ("tomorrow", "2026-12-31", "2027-01-01"),  # TC-DAT-041
        ("tomorrow", "2028-02-28", "2028-02-29"),  # TC-DAT-042
        ("tomorrow", "2027-02-28", "2027-03-01"),  # TC-DAT-043
        ("next week", "2026-10-05", "2026-10-12"),  # TC-DAT-044
        ("next week", "2026-10-11", "2026-10-12"),  # TC-DAT-045 (QA-19)
        ("next week", "2026-12-30", "2027-01-04"),  # TC-DAT-046
        ("EOW", "2026-10-09", "2026-10-09"),  # TC-DAT-047
        ("EOW", "2026-10-10", "2026-10-09"),  # TC-DAT-048 (QA-20)
        ("EOW", "2026-10-11", "2026-10-09"),  # TC-DAT-049
        ("end of month", "2028-02-10", "2028-02-29"),  # TC-DAT-050
        ("end of month", "2027-02-10", "2027-02-28"),  # TC-DAT-051
        ("end of month", "2026-11-03", "2026-11-30"),  # TC-DAT-052
        ("end of month", "2026-12-15", "2026-12-31"),  # TC-DAT-053
        ("end of month", "2026-10-31", "2026-10-31"),  # TC-DAT-054
        ("end of the month", "2026-10-06", "2026-10-31"),
        ("EOM", "2026-10-06", "2026-10-31"),  # TC-DAT-056 (QA-21)
        ("end of day", "2026-10-06", "2026-10-06"),  # TC-DAT-055
        ("by EOD", "2026-10-06", "2026-10-06"),
    ],
)
def test_relative_boundaries(phrase, meeting, expected):
    assert resolve_due_date(phrase, d(meeting)) == d(expected)


def test_dotted_eod_is_not_supported():  # TC-DAT-055 (QA-21)
    assert resolve_due_date("e.o.d.", TUE) is None


# ---------------------------------------------------------------- explicit dates


@pytest.mark.parametrize(
    ("phrase", "meeting", "expected"),
    [
        ("12 Oct", "2026-10-06", "2026-10-12"),  # TC-DAT-060
        ("October 12", "2026-10-06", "2026-10-12"),  # TC-DAT-061
        ("12 October", "2026-10-06", "2026-10-12"),
        ("Oct 12, 2026", "2026-10-06", "2026-10-12"),  # TC-DAT-062
        ("12 Oct 2026", "2026-10-06", "2026-10-12"),
        ("Oct 12th", "2026-10-06", "2026-10-12"),  # TC-DAT-063
        ("12th October", "2026-10-06", "2026-10-12"),
        ("Sept 3", "2026-08-20", "2026-09-03"),
        ("Oct. 12", "2026-10-06", "2026-10-12"),
        ("Jan 15", "2026-12-10", "2027-01-15"),  # TC-DAT-064 next year
        ("Oct 6", "2026-10-06", "2026-10-06"),  # same day stays this year
        ("2026-10-01", "2026-10-06", "2026-10-01"),  # TC-DAT-065 (QA-22)
        ("05/10/2026", "2026-10-06", "2026-10-05"),  # TC-DAT-066 (QA-23)
        ("25/10/2026", "2026-10-06", "2026-10-25"),  # TC-DAT-067
        ("2028-02-29", "2026-10-06", "2028-02-29"),  # TC-DAT-072
    ],
)
def test_explicit_dates(phrase, meeting, expected):
    assert resolve_due_date(phrase, d(meeting)) == d(expected)


@pytest.mark.edge("E5")
@pytest.mark.parametrize(
    "phrase",
    [
        "12/10/26",  # TC-DAT-068 (QA-23)
        "2026-02-30",  # TC-DAT-069
        "2026-13-01",
        "31/02/2026",  # TC-DAT-070
        "13/13/2026",
        "Octember 12",  # TC-DAT-071
        "Oct 32",
        "2027-02-29",  # TC-DAT-072
        "Feb 29, 2027",
        "by Friday 5pm",  # TC-DAT-073
    ],
)
def test_invalid_dates_give_no_date(phrase):
    assert resolve_due_date(phrase, TUE) is None


def test_feb_29_without_year_in_non_leap_year():
    assert resolve_due_date("Feb 29", d("2027-01-10")) is None


# ---------------------------------------------------------------- M3 <-> M5 contract


@pytest.mark.parametrize(
    "phrase",
    [
        "by 2026-10-12",
        "by 12/10/2026",
        "by Oct 12",
        "by 12 October 2026",
        "on Monday",
        "by next Fri",
        "tomorrow",
        "today",
        "EOD",
        "end of day",
        "next week",
        "EOW",
        "end of the week",
        "end of month",
        "EOM",
        "due Friday",
        "before Oct 12",
    ],
)
def test_every_phrase_m3_extracts_m5_resolves(phrase):
    _, _, due = split_line(f"Rahul to send the report {phrase}")
    assert due == phrase
    assert resolve_due_date(due, TUE) is not None


# ---------------------------------------------------------------- helpers and NFRs


def test_next_weekday_after_is_one_to_seven_days():
    for offset in range(7):
        day = TUE + timedelta(days=offset)
        assert next_weekday_after(day, day.weekday()) == day + timedelta(days=7)


def test_does_not_read_the_clock(monkeypatch):  # TC-DAT-090
    class FrozenDate(date):
        @classmethod
        def today(cls):
            raise AssertionError("resolver must not read today's date")

    monkeypatch.setattr(dates, "date", FrozenDate)
    assert resolve_due_date("tomorrow", TUE) == d("2026-10-07")


@pytest.mark.perf
def test_ten_thousand_phrases_are_fast():  # TC-DAT-092
    phrases = ["by Friday", "2026-10-12", "Oct 12", "end of month", "soon"] * 2_000
    start = time.perf_counter()
    for phrase in phrases:
        resolve_due_date(phrase, TUE)
    assert time.perf_counter() - start < 1.0
