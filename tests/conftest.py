"""Shared test fixtures and utilities."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_schedule_data():
    """Return mock schedule data from inverter."""
    return {
        "timeofuse": [
            {
                "_Id": 1,
                "Active": True,
                "ScheduleType": "CHARGE_MAX",
                "Power": 3000,
                "TimeTable": {
                    "Start": "22:00",
                    "End": "06:00",
                },
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": False,
                    "Sun": False,
                },
            },
            {
                "_Id": 2,
                "Active": False,
                "ScheduleType": "DISCHARGE_MAX",
                "Power": 2000,
                "TimeTable": {
                    "Start": "16:00",
                    "End": "22:00",
                },
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": True,
                    "Sun": True,
                },
            },
        ]
    }
