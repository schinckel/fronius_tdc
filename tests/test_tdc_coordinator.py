"""Tests for the TOU data coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.fronius_tdc.tdc_coordinator import (
    FroniusTDCCoordinator,
    _strip_meta,
    validate_schedule,
)


@pytest.fixture
def coordinator(mocker):
    """Create a coordinator with mock hass executor."""
    mocker.patch("homeassistant.helpers.frame.report_usage")
    config_entry = MagicMock(
        data={
            "host": "192.168.1.1",
            "port": 80,
            "username": "customer",
            "password": "password",
        },
        spec=ConfigEntry,
    )
    hass_mock = AsyncMock()

    async def executor_job_handler(func, *args):
        return func(*args)

    hass_mock.async_add_executor_job = AsyncMock(side_effect=executor_job_handler)
    return FroniusTDCCoordinator(
        config_entry=config_entry, hass=hass_mock, logger=MagicMock()
    )


class TestHelpers:
    """Test helper functions for data manipulation."""

    def test_strip_meta(self) -> None:
        result = _strip_meta(
            {"Active": True, "_Id": 1, "TimeTable": {"_A": 1, "Start": "01:00"}}
        )
        assert result == {"Active": True, "TimeTable": {"Start": "01:00"}}

    def test_validate_schedule_happy_path(self) -> None:
        schedule = {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1000,
            "TimeTable": {"Start": "00:00", "End": "23:59"},
            "Weekdays": {
                "Mon": True,
                "Tue": True,
                "Wed": True,
                "Thu": True,
                "Fri": True,
                "Sat": False,
                "Sun": False,
            },
        }
        assert validate_schedule(schedule)["Power"] == 1000

    def test_validate_schedule_invalid_time(self) -> None:
        schedule = {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1000,
            "TimeTable": {"Start": "25:00", "End": "23:59"},
            "Weekdays": {
                "Mon": True,
                "Tue": True,
                "Wed": True,
                "Thu": True,
                "Fri": True,
                "Sat": False,
                "Sun": False,
            },
        }
        with pytest.raises(ValueError, match=r"Invalid.*time.*expected HH:MM"):
            validate_schedule(schedule)


@pytest.mark.asyncio
class TestCoordinatorOperations:
    """Test TDC coordinator refresh and mutation operations."""

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_refresh_creates_rule_ids(
        self, mock_get, coordinator, mock_schedule_data
    ):
        mock_get.return_value = mock_schedule_data
        data = await coordinator._async_update_data()
        assert len(data) == 2
        assert data[0]["rule_id"] == "1"
        assert coordinator.get_rule_ids() == ["1", "2"]

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_setters_and_add_remove(self, mock_post, coordinator):
        coordinator.data = [
            {
                "rule_id": "1",
                "Active": True,
                "ScheduleType": "CHARGE_MAX",
                "Power": 3000,
                "TimeTable": {"Start": "22:00", "End": "06:00"},
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
                "rule_id": "2",
                "Active": False,
                "ScheduleType": "DISCHARGE_MAX",
                "Power": 2000,
                "TimeTable": {"Start": "16:00", "End": "22:00"},
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
        coordinator._rule_id_to_index = {"1": 0, "2": 1}
        coordinator.async_refresh = AsyncMock()

        await coordinator.async_set_active("1", active=False)
        await coordinator.async_set_power("1", 2500)
        await coordinator.async_set_schedule_type("1", "CHARGE_MIN")
        await coordinator.async_set_start_time("1", "00:00")
        await coordinator.async_set_end_time("1", "23:59")
        await coordinator.async_set_weekday("1", "Sun", enabled=True)

        await coordinator.async_add_schedule(
            {
                "Active": True,
                "ScheduleType": "DISCHARGE_MIN",
                "Power": 1500,
                "TimeTable": {"Start": "08:00", "End": "10:00"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": False,
                    "Wed": False,
                    "Thu": False,
                    "Fri": False,
                    "Sat": False,
                    "Sun": False,
                },
            }
        )
        await coordinator.async_remove_schedule("2")

        assert mock_post.call_count == 8

    async def test_invalid_inputs(self, coordinator):
        coordinator.data = [
            {
                "rule_id": "1",
                "Active": True,
                "ScheduleType": "CHARGE_MAX",
                "Power": 3000,
                "TimeTable": {"Start": "22:00", "End": "06:00"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": False,
                    "Sun": False,
                },
            }
        ]
        coordinator._rule_id_to_index = {"1": 0}

        with pytest.raises(ValueError, match=r"Invalid.*time.*expected HH:MM"):
            await coordinator.async_set_start_time("1", "99:99")
        with pytest.raises(ValueError, match="Invalid schedule type"):
            await coordinator.async_set_schedule_type("1", "NOPE")
        with pytest.raises(ValueError, match="Invalid weekday"):
            await coordinator.async_set_weekday("1", "XXX", enabled=True)
        with pytest.raises(ValueError, match="Unknown rule_id"):
            coordinator.resolve_rule_index("does-not-exist")

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_update_errors(self, mock_get, coordinator):
        mock_get.side_effect = requests.ConnectionError("boom")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
