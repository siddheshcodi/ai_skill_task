"""M4 Owner Resolver tests (modules/m04-owner-resolver/test_cases.md)."""

from __future__ import annotations

import pytest

from actiontrack.models import AMBIGUOUS, UNASSIGNED, OwnerResult
from actiontrack.owners import name_matches, resolve_owner

A1 = ["Priya Shah", "Rahul Mehta", "Anita Rao"]
A2 = ["Priya Shah", "Priya Kumar", "Rahul Mehta"]
A3 = ["Priya Shah", "Priya Kumar", "Priya Khan", "Rahul Mehta"]


def found(name: str) -> OwnerResult:
    return OwnerResult(name)


def ambiguous(*names: str) -> OwnerResult:
    return OwnerResult(AMBIGUOUS, candidates=list(names))


def flagged(name: str) -> OwnerResult:
    return OwnerResult(name, not_in_attendees=True)


# ---------------------------------------------------------------- basic


@pytest.mark.parametrize(
    ("phrase", "attendees", "expected"),
    [
        ("Priya", A1, found("Priya Shah")),  # TC-OWN-001
        ("Rahul Mehta", A1, found("Rahul Mehta")),  # TC-OWN-002
        ("rahul", A1, found("Rahul Mehta")),  # TC-OWN-003
        ("RAHUL", A1, found("Rahul Mehta")),
        ("rAhUl", A1, found("Rahul Mehta")),
        ("@Anita", A1, found("Anita Rao")),  # TC-OWN-004
        ("  Priya  ", A1, found("Priya Shah")),  # TC-OWN-005
        ("Priya:", A1, found("Priya Shah")),
        ("priya", A1, found("Priya Shah")),  # TC-OWN-007 attendee spelling
    ],
)
def test_basic_resolution(phrase, attendees, expected):
    assert resolve_owner(phrase, attendees) == expected


@pytest.mark.edge("E3")
@pytest.mark.parametrize("phrase", [None, "", "   ", "@"])
def test_no_owner_is_unassigned(phrase):  # TC-OWN-006
    assert resolve_owner(phrase, A1) == OwnerResult(UNASSIGNED)


# ---------------------------------------------------------------- same first name (E6)


@pytest.mark.edge("E6")
@pytest.mark.parametrize(
    ("phrase", "attendees", "expected"),
    [
        ("Priya", A2, ambiguous("Priya Shah", "Priya Kumar")),  # TC-OWN-020
        ("Priya S.", A2, found("Priya Shah")),  # TC-OWN-021
        ("Priya K", A2, found("Priya Kumar")),  # TC-OWN-022
        ("Priya Kumar", A2, found("Priya Kumar")),  # TC-OWN-023
        ("priya shah", A2, found("Priya Shah")),  # TC-OWN-024
        ("Priya K.", A3, ambiguous("Priya Kumar", "Priya Khan")),  # TC-OWN-025
        ("Priya Kh", A3, found("Priya Khan")),  # TC-OWN-026
        ("Priya", A1, found("Priya Shah")),  # TC-OWN-027 only this meeting counts
        ("Priya", ["Priya Shah", "Priya Shah"], found("Priya Shah")),  # TC-OWN-029
    ],
)
def test_same_first_name(phrase, attendees, expected):
    assert resolve_owner(phrase, attendees) == expected


@pytest.mark.edge("E6")
def test_never_guesses_between_people():  # TC-OWN-028
    result = resolve_owner("Priya", A3)
    assert result.owner == AMBIGUOUS
    assert result.candidates == ["Priya Shah", "Priya Kumar", "Priya Khan"]


# ---------------------------------------------------------------- not in attendees (E7)


@pytest.mark.edge("E7")
@pytest.mark.parametrize(
    ("phrase", "attendees", "expected"),
    [
        ("Vikram", A1, flagged("Vikram")),  # TC-OWN-040
        ("Vikram Singh", A1, flagged("Vikram Singh")),  # TC-OWN-041
        ("Priya Patel", A1, flagged("Priya Patel")),  # TC-OWN-042 (QA-15)
        ("Priya", [], flagged("Priya")),  # TC-OWN-043
        ("Pri", A1, flagged("Pri")),  # TC-OWN-044
        ("Shah", A1, flagged("Shah")),  # TC-OWN-045 (QA-16)
        ("Raj", ["Rajesh Iyer"], flagged("Raj")),  # TC-OWN-046
        ("Finance", A1, flagged("Finance")),  # TC-OWN-047 (QA-12)
        ("Priya and Rahul", A1, flagged("Priya and Rahul")),  # TC-OWN-048 (QA-13)
        ("Priya & Rahul", A1, flagged("Priya & Rahul")),
        ("@Vikram:", A1, flagged("Vikram")),
    ],
)
def test_owner_not_in_attendees_is_kept_and_flagged(phrase, attendees, expected):
    assert resolve_owner(phrase, attendees) == expected


# ---------------------------------------------------------------- name formats


@pytest.mark.parametrize(
    ("phrase", "attendees", "expected"),
    [
        ("Priya", ["Priya Ann Shah"], found("Priya Ann Shah")),  # TC-OWN-060
        ("Priya Shah", ["Priya Ann Shah"], found("Priya Ann Shah")),  # TC-OWN-061
        ("Anita", ["Anita"], found("Anita")),  # TC-OWN-062
        ("Anita R", ["Anita"], flagged("Anita R")),
        ("José", ["José Núñez"], found("José Núñez")),  # TC-OWN-063
        ("Jose", ["José Núñez"], flagged("Jose")),  # TC-OWN-064 (QA-17)
        ("Zoë O'Brien", ["Zoë O'Brien"], found("Zoë O'Brien")),  # TC-OWN-065
        ("Anne-Marie", ["Anne-Marie Dubois"], found("Anne-Marie Dubois")),
    ],
)
def test_name_formats(phrase, attendees, expected):
    assert resolve_owner(phrase, attendees) == expected


def test_reserved_word_is_not_the_reserved_value():  # TC-OWN-066
    result = resolve_owner("Unassigned", A1)
    assert result == flagged("Unassigned")
    assert result.owner != UNASSIGNED


def test_result_is_always_an_attendee_or_the_written_name():
    for phrase in ("Priya", "priya s", "Rahul", "Vikram", "Anita Rao"):
        result = resolve_owner(phrase, A2 + ["Anita Rao"])
        if result.owner != AMBIGUOUS:
            assert result.owner in A2 + ["Anita Rao"] or result.not_in_attendees


# ---------------------------------------------------------------- name_matches (M8 / M9)


@pytest.mark.parametrize(
    ("query", "full_name", "expected"),
    [
        ("Priya Shah", "Priya Shah", True),
        ("priya shah", "Priya Shah", True),
        ("  Priya   Shah ", "Priya Shah", True),
        ("priya", "Priya Shah", True),
        ("PRIYA", "Priya Kumar", True),
        ("Pri", "Priya Shah", False),  # TC-QRY-048 (QA-34)
        ("Shah", "Priya Shah", False),  # TC-QRY-049
        ("Priya Kumar", "Priya Shah", False),
        ("", "Priya Shah", False),
        ("Priya", "", False),
    ],
)
def test_name_matches(query, full_name, expected):
    assert name_matches(query, full_name) is expected
