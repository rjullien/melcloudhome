"""Tests for cloud schedule next-entry summarisation."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.melcloudhome.api.parsing import summarize_cloud_schedule


def test_empty_schedule() -> None:
    assert summarize_cloud_schedule([]) == (0, None)
    assert summarize_cloud_schedule(None) == (0, None)


def test_next_entry_label() -> None:
    # Fixed "now": Wednesday 2026-10-21 10:00 in Europe/Paris
    now = datetime(2026, 10, 21, 10, 0, tzinfo=ZoneInfo("Europe/Paris"))
    schedule = [
        {
            "days": [0, 1, 2, 3, 4, 5, 6],
            "time": "07:00:00",
            "power": True,
        },
        {
            "days": [0, 1, 2, 3, 4, 5, 6],
            "time": "18:30:00",
            "power": False,
        },
    ]
    count, nxt = summarize_cloud_schedule(
        schedule, "Europe/Paris", now=now
    )
    assert count == 2
    assert nxt == "Wed 18:30"
