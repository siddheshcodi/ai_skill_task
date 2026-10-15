"""M9 Follow-up: collect a person's open items and compose one reminder email.

The email is handed to a ``DraftCreator`` (drafts.py), which can only
create drafts. Unassigned and ambiguous items never get an email (Q5).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TextIO

from actiontrack.drafts import DraftCreator
from actiontrack.errors import AmbiguousOwnerError, ConfigError, NotFoundError
from actiontrack.models import AMBIGUOUS, STATUS_OPEN, UNASSIGNED, Email, Item
from actiontrack.owners import clean_phrase, name_matches
from actiontrack.people import load_people
from actiontrack.query import is_overdue

SENDER_ENV = "ACTIONTRACK_SENDER"
DEFAULT_SENDER = "actiontrack"
UNKNOWN_RECIPIENT = "<unknown>"


def resolve_followup_owner(items: list[Item], query: str) -> str:
    """The one real owner ``query`` names (full or first name, any case)."""
    wanted = clean_phrase(query)
    if wanted.casefold() in (UNASSIGNED, AMBIGUOUS):
        raise NotFoundError(
            f"'{wanted}' is not a person; {wanted} items get no follow-up email. "
            f"See them with: actiontrack list --owner {wanted.casefold()}"
        )
    owners = sorted(
        {
            item.owner
            for item in items
            if item.owner not in (UNASSIGNED, AMBIGUOUS) and name_matches(wanted, item.owner)
        }
    )
    if not owners:
        raise NotFoundError(f"No items found for '{wanted}'. Run 'actiontrack list' to see owners.")
    if len(owners) > 1:
        raise AmbiguousOwnerError(
            f"'{wanted}' matches more than one person: {', '.join(owners)}. "
            f'Use the full name, e.g. actiontrack followup "{owners[0]}"'
        )
    return owners[0]


def collect_items(items: list[Item], owner: str, today: date) -> tuple[list[Item], list[Item]]:
    """``(overdue, open)`` items owned by ``owner``, each sorted by due date."""
    mine = [item for item in items if item.owner == owner and item.status == STATUS_OPEN]
    mine.sort(key=lambda i: (i.due_date is None, i.due_date or date.max, i.id or 0))
    overdue = [item for item in mine if is_overdue(item, today)]
    open_ = [item for item in mine if not is_overdue(item, today)]
    return overdue, open_


def compose_email(
    owner: str, to: str, overdue: list[Item], open_: list[Item], sender: str
) -> Email:
    count = len(overdue) + len(open_)
    lines = [
        f"Hi {owner.split()[0]},",
        "",
        "A quick reminder of your action items from recent meetings:",
    ]
    for heading, section in (("Overdue", overdue), ("Open", open_)):
        if section:
            lines += ["", heading, *(f"  • {_describe(item)}" for item in section)]
    lines += [
        "",
        "Please reply if any of these are already done or need a new date.",
        "",
        "Thanks,",
        sender,
    ]
    return Email(
        to=to,
        subject=f"Follow-up: your open action items ({count})",
        body="\n".join(lines) + "\n",
    )


def render(email: Email) -> str:
    return f"To: {email.to}\nSubject: {email.subject}\n\n{email.body}"


def run_followup(
    query: str,
    items: list[Item],
    people_path: Path,
    make_creator: Callable[[], DraftCreator],
    *,
    dry_run: bool,
    today: date,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> None:
    """The ``followup`` command. Never sends: drafts or prints only."""
    out = out or sys.stdout  # resolved per call so redirected output is honoured
    err = err or sys.stderr
    owner = resolve_followup_owner(items, query)
    overdue, open_ = collect_items(items, owner, today)
    if not overdue and not open_:
        print(f"{owner} has no open action items. No draft created.", file=out)
        return

    try:
        people = load_people(people_path)
        to = people.email_for(owner)
        sender = os.environ.get(SENDER_ENV) or people.sender or DEFAULT_SENDER
    except ConfigError as exc:
        if not dry_run:
            raise
        print(f"Warning: {exc}", file=err)  # QA-40: still show the email
        to = UNKNOWN_RECIPIENT
        sender = os.environ.get(SENDER_ENV) or DEFAULT_SENDER

    email = compose_email(owner, to, overdue, open_, sender)
    if dry_run:
        print(render(email), file=out)
        print("(dry run: no draft created)", file=out)
        return

    reference = make_creator().create_draft(email)
    print(f"Draft for {owner} <{to}> prepared: {reference}", file=out)
    print(
        "Ask Claude to create the Gmail draft from this file. "
        "It is saved as a draft for you to review; nothing is sent.",
        file=out,
    )


def _describe(item: Item) -> str:
    task = item.task[:1].upper() + item.task[1:]
    due = f"due {item.due_date.isoformat()}" if item.due_date else "no due date"
    source = item.meeting_title or (item.source_files[0] if item.source_files else None)
    return f"{task} ({due}, from {source})" if source else f"{task} ({due})"
