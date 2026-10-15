"""People list (``people.yaml``): full name -> email address (Q3).

Example::

    sender: Team Lead          # optional: name used to sign emails
    Priya Shah: priya.shah@example.com
    Rahul Mehta: rahul.mehta@example.com
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from actiontrack.errors import ConfigError

SENDER_KEY = "sender"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class People:
    def __init__(self, path: Path, emails: dict[str, str], sender: str | None) -> None:
        self.path = path
        self.sender = sender
        self._emails = {" ".join(name.casefold().split()): email for name, email in emails.items()}

    def email_for(self, full_name: str) -> str:
        """Email for ``full_name`` (any case); clear error if missing or invalid (QA-39)."""
        email = self._emails.get(" ".join(full_name.casefold().split()), "").strip()
        if not email:
            raise ConfigError(
                f"No email address for {full_name} in {self.path}. "
                f"Add a line like:  {full_name}: name@example.com"
            )
        if not _EMAIL_RE.match(email):
            raise ConfigError(
                f"Email address '{email}' for {full_name} in {self.path} is not valid. "
                "Fix it, e.g. name@example.com"
            )
        return email


def load_people(path: Path) -> People:
    if not path.exists():
        raise ConfigError(
            f"People file '{path}' not found. Copy people.yaml.example to {path} "
            "and add each person's email address."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Cannot read people file '{path}' ({exc}).") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"People file '{path}' is not valid YAML: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"People file '{path}' must contain lines like  Name: email@example.com")

    sender = data.pop(SENDER_KEY, None)
    emails = {
        str(name): "" if email is None else str(email)
        for name, email in data.items()
        if name is not None
    }
    return People(path, emails, None if sender is None else str(sender).strip() or None)
