"""Traceability: which test cases in modules/*/test_cases.md have automated tests.

Test functions reference cases in comments, e.g. ``# TC-DAT-020``,
``# TC-STO-021..023, TC-STO-027`` or ``# TC-FUP-040..046, 051``.

Usage:
    python tools/traceability.py            # summary per module
    python tools/traceability.py --missing  # also list uncovered cases
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_ROW_RE = re.compile(r"^\|\s*(TC-[A-Z]{3}-\d{3})\s*\|(.*)$")
PRIORITY_RE = re.compile(r"\|\s*(P[123])\s*\|")
# "TC-STO-021..023", "TC-FUP-040..046, 051", "TC-DUP-054/055"; a new "TC-" starts a new match
REFERENCE_RE = re.compile(
    r"TC-(?P<area>[A-Z]{3})-(?P<first>\d{3})(?P<rest>(?:\s*(?:\.\.|,|/)\s*\d{3})*)"
)

# Covered by a manual release check rather than an automated test.
MANUAL = {
    "TC-FUP-081": "Draft visible in Gmail: verified with the Gmail connector",
    "TC-FUP-082": "Nothing in Sent: verified (label DRAFT only)",
    "TC-FUP-142": "Draft readable on mobile Gmail",
    "TC-FUP-103": "N/A: the hand-off adapter makes no network call, so it cannot time out",
    "TC-QRY-109": "N/A: no reopen command in v1 (QA-37)",
    "TC-STO-083": "N/A: single user at a time is a documented assumption (req §11)",
}


def documented_cases() -> dict[str, tuple[str, str, str]]:
    """``{case_id: (module, priority, row)}`` from every test_cases.md."""
    cases = {}
    for path in sorted(ROOT.glob("modules/*/test_cases.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = CASE_ROW_RE.match(line)
            if match:
                priority = PRIORITY_RE.search(line)
                cases[match[1]] = (path.parent.name, priority[1] if priority else "?", line)
    return cases


def referenced_cases() -> set[str]:
    found: set[str] = set()
    for path in ROOT.glob("tests/**/*.py"):
        for match in REFERENCE_RE.finditer(path.read_text(encoding="utf-8")):
            area = match["area"]
            previous = int(match["first"])
            found.add(f"TC-{area}-{previous:03}")
            for sep, number in re.findall(r"(\.\.|,|/)\s*(\d{3})", match["rest"]):
                current = int(number)
                start = previous + 1 if sep == ".." else current
                found.update(f"TC-{area}-{n:03}" for n in range(start, current + 1))
                previous = current
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--missing", action="store_true", help="list uncovered cases")
    args = parser.parse_args(argv)

    cases = documented_cases()
    covered = referenced_cases() | set(MANUAL)
    by_module: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for case_id, (module, priority, _) in cases.items():
        by_module[module][priority].append(case_id)

    print(f"{'Module':<26}{'Cases':>6}{'Covered':>9}{'P1 gaps':>9}")
    total = total_covered = p1_gaps = 0
    for module in sorted(by_module):
        ids = [c for group in by_module[module].values() for c in group]
        hit = sum(c in covered for c in ids)
        gaps = sum(c not in covered for c in by_module[module].get("P1", []))
        total, total_covered, p1_gaps = total + len(ids), total_covered + hit, p1_gaps + gaps
        print(f"{module:<26}{len(ids):>6}{hit:>9}{gaps:>9}")
    print(f"{'TOTAL':<26}{total:>6}{total_covered:>9}{p1_gaps:>9}")
    print(f"\nCoverage: {total_covered / total:.0%} of documented cases; {len(MANUAL)} manual.")

    if args.missing:
        print("\nUncovered cases:")
        for case_id in sorted(cases):
            if case_id not in covered:
                module, priority, row = cases[case_id]
                title = row.split("|")[2].strip()
                print(f"  {priority} {case_id}  {title}")
    return 0 if p1_gaps == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
