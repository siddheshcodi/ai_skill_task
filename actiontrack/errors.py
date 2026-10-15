"""Exception types shared by all modules.

Domain and service code raise these; only ``cli.main`` turns them into
messages and exit codes. Each message should say what went wrong and,
where possible, how to fix it (NFR-04).
"""

from __future__ import annotations

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


class ActionTrackError(Exception):
    """Base class for expected, user-facing errors."""

    exit_code = EXIT_FAILURE


class UserInputError(ActionTrackError):
    """Bad input that argparse could not catch (e.g. folder does not exist)."""

    exit_code = EXIT_USAGE


class NotFoundError(ActionTrackError):
    """An item ID or owner does not exist."""


class AmbiguousOwnerError(ActionTrackError):
    """An owner name matches more than one person (FR-FUP-05)."""


class StoreError(ActionTrackError):
    """The store file cannot be read or written."""


class ConfigError(ActionTrackError):
    """A configuration file such as people.yaml is missing or invalid."""


class DraftError(ActionTrackError):
    """A Gmail draft could not be created."""
