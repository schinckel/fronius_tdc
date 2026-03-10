"""Tests for the TOU data coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.fronius_tdc.tdc_coordinator import (
    FroniusTDCCoordinator,
    _ensure_power,
    _ensure_weekdays,
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

    def test_strip_meta_list(self) -> None:
        """It should recurse through list items as well as dicts."""
        result = _strip_meta(
            [
                {"_Id": 1, "Active": True},
                {"TimeTable": {"_Tmp": 1, "Start": "00:00", "End": "01:00"}},
            ]
        )
        assert result == [
            {"Active": True},
            {"TimeTable": {"Start": "00:00", "End": "01:00"}},
        ]

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

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_update_http_error(self, mock_get, coordinator):
        """HTTPError should be wrapped with HTTP-specific UpdateFailed message."""
        mock_get.side_effect = requests.HTTPError("bad status")
        with pytest.raises(UpdateFailed, match="HTTP error from inverter"):
            await coordinator._async_update_data()

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_blocking_get_rejects_non_list_payload(self, mock_get, coordinator):
        """Inverter payload must provide a list for timeofuse."""
        mock_get.return_value = {"timeofuse": {"not": "a list"}}
        with pytest.raises(TypeError, match="timeofuse must be a list"):
            coordinator._blocking_get()

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_rule_set_changed_flag(self, mock_get, coordinator):
        """Changing the ordered rule IDs should set and then clear the marker."""
        first = {
            "timeofuse": [
                {
                    "_Id": "1",
                    "Active": True,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 1000,
                    "TimeTable": {"Start": "00:00", "End": "01:00"},
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
        }
        second = {
            "timeofuse": [
                {
                    "_Id": "2",
                    "Active": True,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 1000,
                    "TimeTable": {"Start": "00:00", "End": "01:00"},
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
        }

        mock_get.return_value = first
        coordinator._blocking_get()
        assert coordinator.consume_rule_set_changed() is False

        mock_get.return_value = second
        coordinator._blocking_get()
        assert coordinator.consume_rule_set_changed() is True
        assert coordinator.consume_rule_set_changed() is False

    async def test_derive_rule_id_hash_and_collision(self, coordinator):
        """Fallback IDs should be deterministic and collision-safe."""
        raw_schedule = {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1000,
            "TimeTable": {"Start": "00:00", "End": "01:00"},
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
        normalized = validate_schedule(raw_schedule)

        collisions: dict[str, int] = {}
        first = coordinator._derive_rule_id({}, normalized, collisions)
        second = coordinator._derive_rule_id({}, normalized, collisions)

        assert first.startswith("hash_")
        assert second == f"{first}_2"

        # With a fresh collision map, previous generated ID should be reused.
        third = coordinator._derive_rule_id({}, normalized, {})
        assert third == second

    async def test_resolve_rule_index_int_and_out_of_range(self, coordinator):
        """Integer index resolution should support valid and invalid indices."""
        coordinator.data = [
            {
                "rule_id": "1",
                "Active": True,
                "ScheduleType": "CHARGE_MAX",
                "Power": 1000,
                "TimeTable": {"Start": "00:00", "End": "01:00"},
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

        assert coordinator.resolve_rule_index(0) == 0
        with pytest.raises(ValueError, match="Schedule index out of range"):
            coordinator.resolve_rule_index(2)

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_write_schedules_wraps_post_errors(
        self, mock_post, coordinator
    ):
        """Request exceptions from POST should become UpdateFailed."""
        schedule = {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1000,
            "TimeTable": {"Start": "00:00", "End": "01:00"},
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
        mock_post.side_effect = requests.Timeout("slow")
        coordinator.async_refresh = AsyncMock()

        with pytest.raises(UpdateFailed, match="Failed to update schedules"):
            await coordinator._async_write_schedules([schedule])

        coordinator.async_refresh.assert_not_called()

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_test_connection_blocking(
        self, mock_get, coordinator, mock_schedule_data
    ):
        """test_connection_blocking should delegate to _blocking_get."""
        mock_get.return_value = mock_schedule_data
        data = coordinator.test_connection_blocking()
        assert len(data) == 2


class TestValidationFunctions:
    """Test validation helper functions."""

    def test_ensure_power_out_of_range_low(self) -> None:
        """Test _ensure_power with value below minimum."""
        with pytest.raises(ValueError, match=r"Power.*out of range"):
            _ensure_power(-100)

    def test_ensure_power_out_of_range_high(self) -> None:
        """Test _ensure_power with value above maximum."""
        with pytest.raises(ValueError, match=r"Power.*out of range"):
            _ensure_power(25000)

    def test_ensure_weekdays_missing_day(self) -> None:
        """Test _ensure_weekdays with missing weekday."""
        # Missing "Sun"
        weekdays = {
            "Mon": True,
            "Tue": True,
            "Wed": True,
            "Thu": True,
            "Fri": True,
            "Sat": False,
        }

        with pytest.raises(ValueError, match="Missing weekday"):
            _ensure_weekdays(weekdays)

    def test_ensure_weekdays_non_boolean(self) -> None:
        """Test _ensure_weekdays with non-boolean value."""
        weekdays = {
            "Mon": True,
            "Tue": True,
            "Wed": True,
            "Thu": True,
            "Fri": True,
            "Sat": False,
            "Sun": "yes",  # Should be boolean
        }

        with pytest.raises(TypeError, match="must be boolean"):
            _ensure_weekdays(weekdays)

    def test_validate_schedule_missing_keys(self) -> None:
        """Test validate_schedule with missing required keys."""
        schedule = {
            "Active": True,
            "Power": 1000,
            # Missing ScheduleType, TimeTable, Weekdays
        }

        with pytest.raises(ValueError, match="Missing schedule keys"):
            validate_schedule(schedule)

    def test_validate_schedule_timetable_not_dict(self) -> None:
        """Test validate_schedule with TimeTable not being a dict."""
        schedule = {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1000,
            "TimeTable": "not_a_dict",  # Should be dict
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

        with pytest.raises(TypeError, match="TimeTable must be an object"):
            validate_schedule(schedule)

    def test_validate_schedule_timetable_missing_start(self) -> None:
        """Test validate_schedule with TimeTable missing Start."""
        schedule = {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1000,
            "TimeTable": {"End": "23:59"},  # Missing Start
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

        with pytest.raises(ValueError, match="TimeTable requires Start and End"):
            validate_schedule(schedule)

    def test_validate_schedule_weekdays_not_dict(self) -> None:
        """Test validate_schedule with Weekdays not being a dict."""
        schedule = {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1000,
            "TimeTable": {"Start": "00:00", "End": "23:59"},
            "Weekdays": "not_a_dict",  # Should be dict
        }

        with pytest.raises(TypeError, match="Weekdays must be an object"):
            validate_schedule(schedule)
