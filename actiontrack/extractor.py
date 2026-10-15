"""M3 Action Item Extractor: find checkbox lines and split them.

Each checkbox line becomes a ``RawItem`` with an owner phrase, task text
and due phrase. This module only splits text: M4 decides who the owner is
and M5 turns the due phrase into a date.

Split order: clean markdown -> cut the due phrase off the end -> cut the
owner off the start -> the rest is the task.
"""

from __future__ import annotations

import re

from actiontrack.dates import DUE_PREFIX_PATTERN, VAGUE_PATTERN, WHEN_PATTERN
from actiontrack.models import STATUS_DONE, STATUS_OPEN, Note, RawItem

_CHECKBOX_RE = re.compile(r"^\s*[-*+]\s*\[(?P<mark>[^\]]{0,3})\]\s*(?P<body>.*?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_QUOTE_RE = re.compile(r"^\s*>")

_LINK_RE = re.compile(r"\[([^\[\]]+)\]\([^()]*\)")  # no nested brackets: linear time
_STRONG_RE = re.compile(r"\*\*|__|`")

_DUE_RE = re.compile(
    rf"(?:^|\s)\(?(?P<due>(?:(?:{DUE_PREFIX_PATTERN})\s+)?(?:{WHEN_PATTERN}|{VAGUE_PATTERN}))"
    r"\)?[\s.!,;:]*$",
    re.I,
)

_WORD = r"[^\W\d_][\w'’-]*\.?"
_NAME = rf"{_WORD}(?:\s+{_WORD})?(?:\s+(?:and|&)\s+{_WORD}(?:\s+{_WORD})?)*"
_OWNER_RE = re.compile(rf"^(?P<name>{_NAME})(?:\s*:\s*|\s+(?:to|will)\s+)(?P<rest>.+)$")
_AT_OWNER_RE = re.compile(rf"^@(?P<name>{_WORD})(?:\s+(?P<rest>.+))?$")
_NEXT_WORD_RE = re.compile(rf"^(?P<word>{_WORD})\s+(?P<rest>.+)$")

# Capitalised words that start a sentence but are not people (QA-11).
NOT_OWNERS = frozenset(
    {
        "action", "add", "arrange", "ask", "book", "call", "check", "confirm", "create",
        "discuss", "draft", "email", "everyone", "finalise", "finalize", "fix", "follow",
        "fyi", "get", "i", "make", "need", "note", "organise", "organize", "plan", "please",
        "prepare", "remove", "review", "schedule", "send", "set", "share", "someone",
        "submit", "todo", "update", "we", "write",
    }
)  # fmt: skip


def extract_items(note: Note) -> list[RawItem]:
    """All checkbox items in the note, in line order."""
    items: list[RawItem] = []
    in_code_block = False
    for line_number, line in enumerate(note.text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block or _QUOTE_RE.match(line):
            continue
        checkbox = parse_checkbox(line)
        if checkbox is None:
            continue
        status, body = checkbox
        owner, task, due = split_line(body)
        items.append(
            RawItem(
                raw_text=body,
                owner_phrase=owner,
                task=task,
                due_phrase=due,
                status=status,
                line_number=line_number,
            )
        )
    return items


def parse_checkbox(line: str) -> tuple[str, str] | None:
    """``(status, body)`` for a checkbox line with text, else ``None``."""
    match = _CHECKBOX_RE.match(line)
    if not match or not match.group("body"):
        return None
    mark = match.group("mark").strip()
    if mark == "":
        return STATUS_OPEN, match.group("body")
    if mark in ("x", "X"):
        return STATUS_DONE, match.group("body")
    return None  # [-], [~], [✓] ... are not supported markers (QA-9)


def split_line(body: str) -> tuple[str | None, str, str | None]:
    """Split item text into ``(owner_phrase, task, due_phrase)``."""
    text = clean_markdown(body)
    text, due = _take_due_phrase(text)
    owner, text = _take_owner(text)
    task = text.strip(" \t-–—,;:")
    if not task:  # e.g. the whole line was a due phrase
        task = text.strip() or clean_markdown(body)
    return owner, task, due


def clean_markdown(text: str) -> str:
    text = _LINK_RE.sub(r"\1", text)
    text = _STRONG_RE.sub("", text)
    return " ".join(text.split())


def _take_due_phrase(text: str) -> tuple[str, str | None]:
    match = _DUE_RE.search(text)
    if not match or match.start() == 0:
        return text, None
    return text[: match.start()].rstrip(" ,;:-("), match.group("due")


def _take_owner(text: str) -> tuple[str | None, str]:
    if text.startswith("@"):
        return _take_at_owner(text)
    match = _OWNER_RE.match(text)
    if not match:
        return None, text
    name = match.group("name")
    words = [word for word in name.split() if word.casefold() not in ("and", "&")]
    if words[0].casefold() in NOT_OWNERS or not all(word[0].isupper() for word in words):
        return None, text
    return name, match.group("rest")


def _take_at_owner(text: str) -> tuple[str | None, str]:
    match = _AT_OWNER_RE.match(text)
    if not match or not match.group("rest"):
        return None, text
    name, rest = match.group("name"), match.group("rest")
    # "@Priya Shah send ..." -> include a capitalised last name or initial
    following = _NEXT_WORD_RE.match(rest)
    if following and following.group("word")[0].isupper():
        name, rest = f"{name} {following.group('word')}", following.group("rest")
    return name, rest.lstrip(" :,-")
