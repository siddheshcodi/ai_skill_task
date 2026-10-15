"""M4 Owner Resolver: turn an owner phrase into one attendee of the meeting.

Matching cascade (first rule that finds anyone decides):

1. exact full name                  "Rahul Mehta"  -> Rahul Mehta
2. first name + last name / initial "Priya S."     -> Priya Shah
3. first name only                  "Priya"        -> the only Priya, or ambiguous

Nobody found -> the name is kept as written and flagged (E7). The resolver
never guesses between two people (E6).
"""

from __future__ import annotations

from actiontrack.models import AMBIGUOUS, UNASSIGNED, OwnerResult

_GROUP_WORDS = ("and", "&")


def resolve_owner(owner_phrase: str | None, attendees: list[str]) -> OwnerResult:
    """Resolve ``owner_phrase`` against this meeting's ``attendees``."""
    written = clean_phrase(owner_phrase)
    if not written:
        return OwnerResult(UNASSIGNED)

    query = _tokens(written)
    if any(word in _GROUP_WORDS for word in query):  # "Priya and Rahul" (QA-13)
        return OwnerResult(written, not_in_attendees=True)

    people = _unique(attendees)
    matches = [person for person in people if _tokens(person) == query]
    if not matches:
        matches = [person for person in people if _matches_parts(query, _tokens(person))]

    if len(matches) == 1:
        return OwnerResult(matches[0])
    if len(matches) > 1:
        return OwnerResult(AMBIGUOUS, candidates=matches)
    return OwnerResult(written, not_in_attendees=True)


def name_matches(query: str, full_name: str) -> bool:
    """True if ``query`` is ``full_name`` or its first name (any case).

    The single owner-matching rule shared by ``list --owner`` and
    ``followup`` so every command treats names the same way.
    """
    wanted = _tokens(clean_phrase(query))
    name = _tokens(full_name)
    if not wanted or not name:
        return False
    return wanted == name or (len(wanted) == 1 and wanted[0] == name[0])


def clean_phrase(phrase: str | None) -> str:
    """Trim spacing and the ``@`` / ``:`` decoration around a written name."""
    if phrase is None:
        return ""
    return " ".join(phrase.strip().lstrip("@").rstrip(":").split())


def _tokens(name: str) -> list[str]:
    return name.replace(".", " ").casefold().split()


def _matches_parts(query: list[str], person: list[str]) -> bool:
    """First name equal and, if given, the last part starts the surname."""
    if query[0] != person[0]:
        return False
    if len(query) == 1:
        return True
    if len(person) == 1:
        return False
    return person[-1].startswith(query[-1])


def _unique(names: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for name in names:
        key = " ".join(_tokens(name))
        if key not in seen:
            seen.add(key)
            result.append(name)
    return result
