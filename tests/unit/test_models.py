"""Shared data model checks (plan.md section 5, M7 data model)."""

from __future__ import annotations

from datetime import date

from actiontrack.models import (
    FILTER_STATUSES,
    STATUS_OVERDUE,
    STORED_STATUSES,
    Item,
)


def test_overdue_is_never_a_stored_status():  # TC-STO-042
    assert STATUS_OVERDUE not in STORED_STATUSES
    assert STATUS_OVERDUE in FILTER_STATUSES


def test_item_defaults_do_not_share_lists():
    meeting = date(2026, 10, 6)
    a = Item("Priya Shah", "send quote", "Priya to send quote", "open", meeting, meeting)
    b = Item("Rahul Mehta", "update CRM", "Rahul will update CRM", "open", meeting, meeting)
    a.source_files.append("a.md")
    assert b.source_files == []
    assert a.id is None
    assert a.due_date is None
