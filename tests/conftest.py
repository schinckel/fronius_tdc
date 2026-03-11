"""Shared test fixtures and utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

data = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def mock_schedule_data():
    """Return mock schedule data from inverter."""
    return json.loads((data / "timeofuse.json").read_text())
