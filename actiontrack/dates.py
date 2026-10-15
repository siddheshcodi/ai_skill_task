"""M5 Date Resolver.

Milestone 3 provides only the shared vocabulary of due-date expressions.
M3 uses it to cut the due phrase off an action item, so the extractor
never takes text that M5 cannot interpret. ``resolve_due_date`` arrives
in milestone 4.
"""

from __future__ import annotations

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
