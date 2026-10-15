"""Where a composed follow-up email goes: always a Gmail **draft**.

Safety (NFR-02, FR-FUP-04): a ``DraftCreator`` has exactly one action,
``create_draft``. Nothing in this package can deliver an email; a test
scans the source and fails if any send-type call appears.

``HandoffDraftCreator`` (default, decision D3) writes the draft to an
outbox file. The Gmail connector in the Claude session then creates the
draft from that file with its create-draft tool, so a human reviews every
email in Gmail before it goes anywhere.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from actiontrack.errors import DraftError
from actiontrack.models import Email

DEFAULT_OUTBOX = "outbox"
DRAFT_ACTION = "create_draft"


class DraftCreator(Protocol):
    def create_draft(self, email: Email) -> str:
        """Save ``email`` as a draft and return a reference to it."""
        ...


class HandoffDraftCreator:
    """Write the draft to ``outbox/`` for the Gmail connector to create."""

    def __init__(self, outbox: Path, now: Callable[[], datetime] = datetime.now) -> None:
        self.outbox = outbox
        self._now = now

    def create_draft(self, email: Email) -> str:
        payload = {
            "action": DRAFT_ACTION,
            "to": email.to,
            "subject": email.subject,
            "body": email.body,
            "created_at": self._now().replace(microsecond=0).isoformat(),
        }
        try:
            self.outbox.mkdir(parents=True, exist_ok=True)
            path = self._new_path(email.to)
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError as exc:
            raise DraftError(
                f"could not write the draft to '{self.outbox}' ({exc.strerror or exc}). "
                "Try --dry-run to see the email."
            ) from exc
        return str(path)

    def _new_path(self, recipient: str) -> Path:
        stamp = self._now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "-", recipient.split("@")[0].casefold()).strip("-")
        path = self.outbox / f"{stamp}-{slug or 'draft'}.json"
        counter = 2
        while path.exists():
            path = self.outbox / f"{stamp}-{slug or 'draft'}-{counter}.json"
            counter += 1
        return path
