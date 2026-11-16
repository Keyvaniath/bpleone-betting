"""Shared test fixtures."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


@pytest.fixture(autouse=True)
def _nba_lean_gate_off(monkeypatch):
    """(2026-11-16) NBA leans wait for the 5 PM ET injury report (play_of_day.NBA_LEAN_HOUR_ET). Tests
    written before that rule build same-day NBA leans at arbitrary clock times; the gate is off for
    them (hour 0) and its own test turns it back on explicitly."""
    import play_of_day
    monkeypatch.setattr(play_of_day, "NBA_LEAN_HOUR_ET", 0)
