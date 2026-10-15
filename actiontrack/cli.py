"""M1 CLI: parse commands, validate input, dispatch, map errors to exit codes.

This module holds no business logic. Each ``_cmd_*`` handler opens the
store, calls one service function and prints its result.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import NoReturn

from actiontrack import __version__
from actiontrack.drafts import DEFAULT_OUTBOX, HandoffDraftCreator
from actiontrack.errors import (
    EXIT_FAILURE,
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_USAGE,
    ActionTrackError,
    UserInputError,
)
from actiontrack.followup import run_followup
from actiontrack.ingest import run_ingest
from actiontrack.models import FILTER_STATUSES
from actiontrack.query import DoneResult, filter_items, format_table, mark_done
from actiontrack.report import format_report
from actiontrack.store import Store

PROG = "actiontrack"
DEFAULT_STORE = "actiontrack.json"
DEFAULT_PEOPLE = "people.yaml"

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_POSITIVE_INT_RE = re.compile(r"^\d+$")


# ---------------------------------------------------------------- validators


def iso_date(value: str) -> date:
    """argparse type: a real calendar date written as YYYY-MM-DD."""
    text = value.strip()
    if _ISO_DATE_RE.match(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"invalid date '{value}'. Use YYYY-MM-DD, e.g. 2026-10-12.")


def status_choice(value: str) -> str:
    """argparse type: open, done or overdue (any case)."""
    status = value.strip().lower()
    if status not in FILTER_STATUSES:
        raise argparse.ArgumentTypeError(f"invalid status '{value}'. Use open, done or overdue.")
    return status


def positive_int(value: str) -> int:
    """argparse type: an item ID (1, 2, 3 ...)."""
    text = value.strip()
    if not _POSITIVE_INT_RE.match(text) or int(text) == 0:
        raise argparse.ArgumentTypeError(
            f"invalid ID '{value}'. The ID must be a whole number from 1 up, "
            "e.g. 'actiontrack done 12'. Run 'actiontrack list' to see IDs."
        )
    return int(text)


def owner_name(value: str) -> str:
    """argparse type: a non-blank person name."""
    name = " ".join(value.split())
    if not name:
        raise argparse.ArgumentTypeError(
            'owner name is empty. Give a full or first name, e.g. "Priya Shah".'
        )
    return name


# ---------------------------------------------------------------- parser


class _Parser(argparse.ArgumentParser):
    """ArgumentParser with friendlier error output (NFR-04)."""

    def error(self, message: str) -> NoReturn:
        self.exit(
            EXIT_USAGE,
            f"Error: {message}\nRun '{self.prog} --help' to see usage.\n",
        )


def _common_options() -> argparse.ArgumentParser:
    """Options accepted both before and after the sub-command."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--store",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help=f"store file to use (default: ./{DEFAULT_STORE})",
    )
    common.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help="show full error details for troubleshooting",
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    common = _common_options()
    parser = _Parser(
        prog=PROG,
        parents=[common],
        description=(
            "Collect action items from markdown meeting notes, track them, "
            "and prepare follow-up emails as Gmail drafts (never sent)."
        ),
        epilog="Run 'actiontrack <command> --help' for details on a command.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="<command>", parser_class=_Parser)

    p_ingest = sub.add_parser(
        "ingest",
        parents=[common],
        help="read meeting notes and save their action items",
        description=(
            "Read every .md note in FOLDER, extract action items, merge duplicates "
            "and save them to the store. Safe to run again on the same folder."
        ),
    )
    p_ingest.add_argument("folder", type=Path, help="folder containing .md meeting notes")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_list = sub.add_parser(
        "list",
        parents=[common],
        help="show action items, with optional filters",
        description="Show stored action items. Filters can be combined.",
    )
    p_list.add_argument(
        "--owner",
        type=owner_name,
        metavar="NAME",
        help="only items for this person (full or first name, any case)",
    )
    p_list.add_argument(
        "--status",
        type=status_choice,
        metavar="{open,done,overdue}",
        help="only items with this status",
    )
    p_list.add_argument(
        "--due-before",
        type=iso_date,
        metavar="YYYY-MM-DD",
        help="only items due before this date",
    )
    p_list.set_defaults(func=_cmd_list)

    p_done = sub.add_parser(
        "done",
        parents=[common],
        help="mark an action item as done",
        description="Mark the item with the given ID as done.",
    )
    p_done.add_argument("id", type=positive_int, help="item ID shown by 'actiontrack list'")
    p_done.set_defaults(func=_cmd_done)

    p_followup = sub.add_parser(
        "followup",
        parents=[common],
        help="prepare a follow-up email as a Gmail draft",
        description=(
            "Compose one reminder email listing OWNER's overdue and open items and "
            "save it as a Gmail draft for review. Emails are never sent."
        ),
    )
    p_followup.add_argument("owner", type=owner_name, help="person's full or first name")
    p_followup.add_argument(
        "--dry-run",
        action="store_true",
        help="print the email instead of creating a draft",
    )
    p_followup.add_argument(
        "--people",
        type=Path,
        metavar="PATH",
        default=Path(DEFAULT_PEOPLE),
        help=f"name-to-email list (default: ./{DEFAULT_PEOPLE})",
    )
    p_followup.add_argument(
        "--outbox",
        type=Path,
        metavar="PATH",
        default=Path(DEFAULT_OUTBOX),
        help=f"folder for draft files for the Gmail connector (default: ./{DEFAULT_OUTBOX})",
    )
    p_followup.set_defaults(func=_cmd_followup)

    return parser


# ---------------------------------------------------------------- handlers


def _store_path(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "store", DEFAULT_STORE))


def _cmd_ingest(args: argparse.Namespace) -> int:
    folder: Path = args.folder
    if not folder.exists():
        raise UserInputError(f"folder '{folder}' not found. Check the path and try again.")
    if not folder.is_dir():
        raise UserInputError(f"'{folder}' is not a folder. Give the folder that holds the notes.")
    store = _open_store(args)
    print(format_report(run_ingest(folder, store)))
    return EXIT_OK


def _cmd_list(args: argparse.Namespace) -> int:
    store = _open_store(args)
    today = _today()
    items = filter_items(
        store.load_all(),
        today=today,
        owner=args.owner,
        status=args.status,
        due_before=args.due_before,
    )
    interactive = sys.stdout.isatty()
    width = shutil.get_terminal_size().columns if interactive else None
    print(format_table(items, today, color=interactive and _color_enabled(), max_width=width))
    return EXIT_OK


def _cmd_done(args: argparse.Namespace) -> int:
    store = _open_store(args)
    result, item = mark_done(store, args.id)
    if result is DoneResult.ALREADY_DONE:
        print(f"Item {item.id} is already done: {item.task}")
        return EXIT_OK
    store.save()
    print(f"Item {item.id} marked as done: {item.task}")
    return EXIT_OK


def _open_store(args: argparse.Namespace) -> Store:
    store = Store(_store_path(args))
    store.load_all()  # surface store errors and warnings before doing anything else
    for warning in store.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return store


def _today() -> date:
    """Today's date for overdue checks (§11); patched in tests."""
    return date.today()


def _color_enabled() -> bool:
    """Colour unless NO_COLOR is set; on Windows, switch on ANSI support first."""
    if "NO_COLOR" in os.environ:
        return False
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))  # VT processing
    except (AttributeError, OSError):
        return False


def _cmd_followup(args: argparse.Namespace) -> int:
    store = _open_store(args)
    run_followup(
        args.owner,
        store.load_all(),
        args.people,
        lambda: HandoffDraftCreator(args.outbox),
        dry_run=args.dry_run,
        today=_today(),
    )
    return EXIT_OK


# ---------------------------------------------------------------- entry point


def _use_utf8_output() -> None:
    """Avoid UnicodeEncodeError for non-ASCII names on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _use_utf8_output()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help, --version and usage errors
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE

    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    debug = getattr(args, "debug", False)
    try:
        return args.func(args)
    except ActionTrackError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("Cancelled. No changes were saved.", file=sys.stderr)
        return EXIT_INTERRUPTED
    except Exception as exc:
        if debug:
            traceback.print_exc()
        print(
            f"Unexpected error: {exc} (run with --debug for details)",
            file=sys.stderr,
        )
        return EXIT_FAILURE
