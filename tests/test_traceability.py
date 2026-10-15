"""NFR-06: every edge case has a test, and every P1 test case is automated."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
EDGE_CASES = [f"E{n}" for n in range(1, 12)]


def load_traceability():
    spec = importlib.util.spec_from_file_location("traceability", ROOT / "tools/traceability.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_edge_case_is_tagged():  # NFR-06, Acceptance #8
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").rglob("*.py"))
    tagged = set(re.findall(r'edge\("(E\d+)"\)', source))
    assert sorted(set(EDGE_CASES) - tagged, key=lambda e: int(e[1:])) == []


def test_every_p1_case_has_a_test(capsys):
    assert load_traceability().main([]) == 0, capsys.readouterr().out
