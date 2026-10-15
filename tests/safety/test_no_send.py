"""NFR-02 / FR-FUP-04: the code must never be able to send email.

Scans every module in the package. Fails if any function, method, call or
attribute is named like a send action, or if a mail-sending library is imported.
Runs from milestone 2 so the guarantee holds from the first line of M9.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import actiontrack

PACKAGE_DIR = Path(actiontrack.__file__).parent
FORBIDDEN_MODULES = {"smtplib", "imaplib", "poplib"}

pytestmark = pytest.mark.safety


def _sources() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


_SEND_NAME_RE = re.compile(r"^(?:(?:send|Send|SEND)(?:$|_)|[sS]end[A-Z])")


def _is_send_name(name: str) -> bool:
    """send, send_message, sendMail, SendDraft ... but not sender or sending."""
    return bool(_SEND_NAME_RE.match(name))


def _violations(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_send_name(node.name):
            found.append(f"defines '{node.name}' (line {node.lineno})")
        elif isinstance(node, ast.Attribute) and _is_send_name(node.attr):
            found.append(f"uses '.{node.attr}' (line {node.lineno})")
        elif isinstance(node, ast.Name) and _is_send_name(node.id):
            found.append(f"uses '{node.id}' (line {node.lineno})")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.lower() in {"send_message", "send_draft", "send_email", "messages.send"}:
                found.append(f"names tool '{node.value}' (line {node.lineno})")
        elif isinstance(node, ast.Import):
            found += [
                f"imports '{alias.name}' (line {node.lineno})"
                for alias in node.names
                if alias.name.split(".")[0] in FORBIDDEN_MODULES
            ]
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".")[0] in FORBIDDEN_MODULES
        ):
            found.append(f"imports from '{node.module}' (line {node.lineno})")
    return found


def test_package_has_sources():
    assert _sources(), "no package sources found to scan"


@pytest.mark.parametrize("path", _sources(), ids=lambda p: p.name)
def test_no_send_code(path: Path):  # TC-FUP-120, TC-FUP-122
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = _violations(tree)
    assert not violations, f"{path.name} " + "; ".join(violations)


def test_scanner_catches_send_code():
    """Guard the guard: the scanner must flag the patterns it is meant to block."""
    sample = (
        "import smtplib\n"
        "def send_email(): pass\n"
        "client.drafts.send(id=1)\n"
        "call_tool('send_message')\n"
    )
    assert len(_violations(ast.parse(sample))) == 4


@pytest.mark.parametrize(
    ("name", "blocked"),
    [
        ("send", True),
        ("send_message", True),
        ("sendMail", True),
        ("SendDraft", True),
        ("SEND", True),
        ("SEND_MESSAGE", True),
        ("SENDER_ENV", False),
        ("sender", False),
        ("sender_name", False),
        ("sending", False),
        ("create_draft", False),
    ],
)
def test_send_name_rule(name, blocked):
    assert _is_send_name(name) is blocked
