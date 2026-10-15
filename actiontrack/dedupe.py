"""M6 Deduplicator: store each real task once.

Two items are the same when they have the same resolved owner and their
cleaned task texts are at least ``SIMILARITY_THRESHOLD`` similar, unless
they name different people, companies or numbers ("call Rahul" vs
"call Anita"), which blocks the merge (QA-26).

Notes must be fed oldest meeting first (``ingest`` does this) so that the
newest meeting's due date wins (E1) without extra bookkeeping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from actiontrack.models import AMBIGUOUS, STATUS_DONE, Item, ResolvedItem
from actiontrack.store import Store

SIMILARITY_THRESHOLD = 0.85

_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_TOKEN_RE = re.compile(r"[\w'’]+")


@dataclass(frozen=True)
class DedupeOutcome:
    """What happened to one incoming item."""

    item: Item
    created: bool


def normalize_task(task: str, due_phrase: str | None = None) -> str:
    """Lower-case, no due phrase, no punctuation, single spaces."""
    text = task.casefold()
    if due_phrase:
        text = text.replace(due_phrase.casefold(), " ")
    text = _PUNCTUATION_RE.sub("", text)
    return " ".join(text.split())


def owner_key(owner: str, candidates: list[str]) -> str:
    if owner == AMBIGUOUS:
        return "ambiguous:" + "|".join(sorted(c.casefold() for c in candidates))
    return owner.casefold()


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def significant_tokens(task: str) -> set[str]:
    """Numbers and capitalised words after the first word (names, products)."""
    words = _TOKEN_RE.findall(task)
    return {
        word.casefold()
        for position, word in enumerate(words)
        if any(ch.isdigit() for ch in word) or (position > 0 and word[0].isupper())
    }


def conflicting_tokens(a: str, b: str) -> bool:
    """True if one task names something the other does not mention at all."""
    return _Text(a).conflicts_with(_Text(b))


class _Text:
    """A task text with everything the matcher needs, computed once."""

    __slots__ = ("normalized", "significant", "words")

    def __init__(self, task: str, due_phrase: str | None = None) -> None:
        self.normalized = normalize_task(task, due_phrase)
        self.words = {word.casefold() for word in _TOKEN_RE.findall(task)}
        self.significant = significant_tokens(task)

    def conflicts_with(self, other: _Text) -> bool:
        return bool(self.significant - other.words or other.significant - self.words)


@dataclass
class _Entry:
    item: Item
    text: _Text


class DedupeIndex:
    """Stored items grouped by owner, for matching during one ingest run."""

    def __init__(self, items: list[Item], threshold: float = SIMILARITY_THRESHOLD) -> None:
        self.threshold = threshold
        self._by_owner: dict[str, list[_Entry]] = {}
        for item in items:
            self.add(item)

    def add(self, item: Item) -> None:
        entry = _Entry(item, _Text(item.task, item.due_phrase))
        self._by_owner.setdefault(owner_key(item.owner, item.owner_candidates), []).append(entry)

    def find(self, incoming: ResolvedItem) -> Item | None:
        """Best stored match for ``incoming`` (highest score, then lowest ID)."""
        raw = incoming.raw
        key = owner_key(incoming.owner.owner, incoming.owner.candidates)
        wanted = _Text(raw.task, raw.due_phrase)
        best: tuple[float, int] | None = None
        best_item: Item | None = None
        for entry in self._by_owner.get(key, []):
            score = self._score(raw.raw_text, wanted, entry)
            if score is None:
                continue
            rank = (score, -(entry.item.id or 0))
            if best is None or rank > best:
                best, best_item = rank, entry.item
        return best_item

    def _score(self, raw_text: str, wanted: _Text, entry: _Entry) -> float | None:
        """Similarity if ``entry`` may be the same task, else None (cheap checks first)."""
        stored = entry.text
        if not wanted.normalized or not stored.normalized:  # nothing to compare (QA-25)
            return 1.0 if raw_text.casefold() == entry.item.raw_text.casefold() else None
        if wanted.normalized == stored.normalized:
            return 1.0
        if wanted.conflicts_with(stored):
            return None
        matcher = SequenceMatcher(None, wanted.normalized, stored.normalized, autojunk=False)
        # real_quick_ratio and quick_ratio are upper bounds of ratio
        if matcher.real_quick_ratio() < self.threshold or matcher.quick_ratio() < self.threshold:
            return None
        score = matcher.ratio()
        return score if score >= self.threshold else None


def to_new_item(incoming: ResolvedItem) -> Item:
    raw, note, owner = incoming.raw, incoming.note, incoming.owner
    return Item(
        owner=owner.owner,
        owner_candidates=list(owner.candidates),
        task=raw.task,
        raw_text=raw.raw_text,
        status=raw.status,
        meeting_date=note.meeting_date,
        last_seen_meeting_date=note.meeting_date,
        due_date=incoming.due_date,
        due_phrase=raw.due_phrase,
        source_files=[note.file_name],
        meeting_title=note.title,
        not_in_attendees=owner.not_in_attendees,
    )


def merge(existing: Item, incoming: ResolvedItem) -> bool:
    """Apply the merge rules; return True if ``existing`` changed."""
    changed = False
    note = incoming.note

    if note.file_name not in existing.source_files:
        existing.source_files.append(note.file_name)
        changed = True

    if note.meeting_date >= existing.last_seen_meeting_date:
        if note.meeting_date > existing.last_seen_meeting_date:
            existing.last_seen_meeting_date = note.meeting_date
            changed = True
        # newest meeting's date wins, but a missing date never erases one (QA-28)
        new_due = (incoming.due_date, incoming.raw.due_phrase)
        if incoming.due_date is not None and new_due != (existing.due_date, existing.due_phrase):
            existing.due_date, existing.due_phrase = new_due
            changed = True

    # done anywhere means done; ingest never re-opens an item (E2, QA-29)
    if incoming.raw.status == STATUS_DONE and existing.status != STATUS_DONE:
        existing.status = STATUS_DONE
        changed = True

    return changed


def dedupe_into(
    store: Store, incoming: list[ResolvedItem], index: DedupeIndex
) -> list[DedupeOutcome]:
    """Add new items to ``store`` or merge them into existing ones."""
    outcomes = []
    for resolved in incoming:
        match = index.find(resolved)
        if match is None:
            item = store.add(to_new_item(resolved))
            index.add(item)
            outcomes.append(DedupeOutcome(item, created=True))
        else:
            if merge(match, resolved):
                store.update(match)
            outcomes.append(DedupeOutcome(match, created=False))
    return outcomes
