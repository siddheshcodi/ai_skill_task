"""M5 Date Resolver: turn a due phrase into a calendar date.

Dates are relative to the **meeting date**, never to today, so results do
not depend on when ingest runs. Anything unclear resolves to ``None`` and
the original phrase is kept by the caller (E5). The module also exports the
vocabulary of due expressions that M3 uses to cut the due phrase off an
action item, so the extractor never takes text this module cannot read.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Callable
from datetime import date, timedelta

_WEEKDAYS = (
    r"mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?"
    r"|fri(?:day)?|sat(?:urday)?|sun(?:day)?"
)
_MONTHS = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s+\d{4})?"

# Every due expression M5 understands (case-insensitive, no leading "by"/"on").
WHEN_PATTERN = "|".join(
    [
        r"\d{4}-\d{2}-\d{2}",  # 2026-10-12
        r"\d{1,2}/\d{1,2}/\d{2,4}",  # 12/10/2026 (2-digit years resolve to none)
        rf"(?:{_MONTHS})\.?\s+{_DAY}{_YEAR}",  # Oct 12, October 12th, 2026
        rf"{_DAY}\s+(?:{_MONTHS})\.?{_YEAR}",  # 12 Oct, 12th October 2026
        rf"(?:(?:this|next)\s+)?(?:{_WEEKDAYS})",  # Friday, next Fri
        r"today|tomorrow|eod|end\s+of\s+(?:the\s+)?day",
        r"next\s+week|eow|end\s+of\s+(?:the\s+)?week",
        r"eom|end\s+of\s+(?:the\s+)?month",
    ]
)

# Unclear expressions: kept as the due phrase (E5) but resolve to no date.
VAGUE_PATTERN = "|".join(
    [
        r"soon|asap|a\.s\.a\.p\.?|later|tbd|tbc",
        r"when\s+possible|next\s+(?:month|sprint|quarter)",
        r"in\s+(?:\d+|a|one|two|three)\s+(?:days?|weeks?)",
        r"e\.o\.d\.?|e\.o\.w\.?",
    ]
)

# Words that introduce a due expression ("by Friday", "due 2026-10-12").
DUE_PREFIX_PATTERN = r"by|on|due(?:\s+by|\s+on)?|before"

FRIDAY = 4
_MONTH_NUMBERS = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}
_WEEKDAY_NUMBERS = {
    name: number for number, name in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))
}
_PREFIX_RE = re.compile(rf"^(?:{DUE_PREFIX_PATTERN})\s+")
_EDGE_PUNCTUATION = " \t()[].,!;:"

Rule = Callable[[re.Match[str], date], "date | None"]


def resolve_due_date(due_phrase: str | None, meeting_date: date) -> date | None:
    """The due date for ``due_phrase`` relative to ``meeting_date``, or None."""
    if not due_phrase:
        return None
    phrase = normalize_phrase(due_phrase)
    for pattern, rule in _RULES:
        match = pattern.fullmatch(phrase)
        if match:
            try:
                return rule(match, meeting_date)
            except ValueError:  # e.g. 2026-02-30
                return None
    return None


def normalize_phrase(phrase: str) -> str:
    """Lower-case, single spaces, no edge punctuation, no "by"/"on"/"due" prefix."""
    text = " ".join(phrase.casefold().split()).strip(_EDGE_PUNCTUATION)
    return _PREFIX_RE.sub("", text)


def next_weekday_after(day: date, weekday: int) -> date:
    """The next ``weekday`` strictly after ``day`` (1 to 7 days later; Q6)."""
    return day + timedelta(days=(weekday - day.weekday() - 1) % 7 + 1)


def week_monday(day: date) -> date:
    """Monday of the ISO week containing ``day`` (QA-19)."""
    return day - timedelta(days=day.weekday())


def month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


# ---------------------------------------------------------------- rules


def _iso(match: re.Match[str], meeting: date) -> date:
    return date.fromisoformat(match.group(0))


def _day_month_year(match: re.Match[str], meeting: date) -> date:
    # DD/MM/YYYY (QA-23)
    return date(int(match["year"]), int(match["month"]), int(match["day"]))


def _month_and_day(match: re.Match[str], meeting: date) -> date:
    month = _MONTH_NUMBERS[match["month"][:3]]
    day = int(match["day"])
    if match["year"]:
        return date(int(match["year"]), month, day)
    due = date(meeting.year, month, day)
    # "Jan 15" written in December means next January
    return due if due >= meeting else date(meeting.year + 1, month, day)


def _weekday(match: re.Match[str], meeting: date) -> date:
    # "this"/"next" follow the same rule as a bare weekday (QA-18)
    return next_weekday_after(meeting, _WEEKDAY_NUMBERS[match["weekday"][:3]])


def _same_day(match: re.Match[str], meeting: date) -> date:
    return meeting


def _tomorrow(match: re.Match[str], meeting: date) -> date:
    return meeting + timedelta(days=1)


def _next_week(match: re.Match[str], meeting: date) -> date:
    return week_monday(meeting) + timedelta(days=7)


def _end_of_week(match: re.Match[str], meeting: date) -> date:
    # Friday of the same ISO week, even for weekend meetings (QA-20)
    return week_monday(meeting) + timedelta(days=FRIDAY)


def _end_of_month(match: re.Match[str], meeting: date) -> date:
    return month_end(meeting)


_ORDINAL = r"(?:st|nd|rd|th)?"
_RULES: list[tuple[re.Pattern[str], Rule]] = [
    (re.compile(r"\d{4}-\d{2}-\d{2}"), _iso),
    (re.compile(r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})"), _day_month_year),
    (
        re.compile(
            rf"(?P<month>{_MONTHS})\.?\s+(?P<day>\d{{1,2}}){_ORDINAL}(?:,?\s+(?P<year>\d{{4}}))?"
        ),
        _month_and_day,
    ),
    (
        re.compile(
            rf"(?P<day>\d{{1,2}}){_ORDINAL}\s+(?P<month>{_MONTHS})\.?(?:,?\s+(?P<year>\d{{4}}))?"
        ),
        _month_and_day,
    ),
    (re.compile(rf"(?:(?:this|next)\s+)?(?P<weekday>{_WEEKDAYS})"), _weekday),
    (re.compile(r"today|eod|end of (?:the )?day"), _same_day),
    (re.compile(r"tomorrow"), _tomorrow),
    (re.compile(r"next week"), _next_week),
    (re.compile(r"eow|end of (?:the )?week"), _end_of_week),
    (re.compile(r"eom|end of (?:the )?month"), _end_of_month),
]
