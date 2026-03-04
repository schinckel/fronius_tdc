"""Shared test fixtures and utilities."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.fronius_tdc.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DEFAULT_PORT,
    DOMAIN,
)


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return {
        "entry_id": "test_entry_123",
        "domain": DOMAIN,
        "title": "Fronius Gen24 (192.168.1.1)",
        "data": {
            CONF_HOST: "192.168.1.1",
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "customer",
            CONF_PASSWORD: "password",
        },
        "options": {},
        "version": 1,
    }


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


@pytest.fixture
def mock_response():
    """Return a mock HTTP response."""
    response = Mock()
    response.status_code = 200
    response.headers = {}
    response.raise_for_status = Mock()
    return response
