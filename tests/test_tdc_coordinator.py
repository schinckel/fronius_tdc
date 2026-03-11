"""Tests for the data coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.fronius_tdc.tdc_coordinator import (
    FroniusTDCCoordinator,
    _normalize_rule,
    _normalize_schedules,
    _strip_meta,
    _validate_schedule_type,
    _validate_time_value,
    _validate_weekdays,
)


class TestStripMeta:
    """Test _strip_meta function."""

    def test_strip_meta_dict(self) -> None:
        """Test stripping metadata keys from dict."""
        data = {
            "Active": True,
            "_Id": 1,
            "Power": 3000,
            "_Meta": "hidden",
        }
        result = _strip_meta(data)
        assert result == {"Active": True, "Power": 3000}
        assert "_Id" not in result
        assert "_Meta" not in result

    def test_strip_meta_nested(self) -> None:
        """Test stripping metadata from nested structures."""
        data = {
            "Active": True,
            "_Id": 1,
            "TimeTable": {
                "Start": "22:00",
                "_Calculated": "yes",
            },
        }
        result = _strip_meta(data)
        assert result == {
            "Active": True,
            "TimeTable": {"Start": "22:00"},
        }

    def test_strip_meta_list(self) -> None:
        """Test stripping metadata from lists."""
        data = [
            {"Active": True, "_Id": 1},
            {"Active": False, "_Id": 2},
        ]
        result = _strip_meta(data)
        assert result == [{"Active": True}, {"Active": False}]

    def test_strip_meta_scalar(self) -> None:
        """Test that scalar values pass through unchanged."""
        assert _strip_meta("test") == "test"
        assert _strip_meta(42) == 42
        assert _strip_meta(True) is True  # noqa: FBT003


class TestFroniusTDCCoordinator:
    """Test FroniusTDCCoordinator."""

    @pytest.fixture
    def coordinator(self, mocker):
        """Create a real coordinator instance with mocked dependencies."""
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
        return FroniusTDCCoordinator(
            config_entry=config_entry,
            hass=MagicMock(),
            logger=MagicMock(),
        )

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    def test_blocking_get(self, mock_get, coordinator, mock_schedule_data) -> None:
        """Test _blocking_get method."""
        mock_get.return_value = mock_schedule_data

        result = coordinator._blocking_get()

        assert len(result) == 5
        assert result[0]["Active"] is True
        assert result[0]["ScheduleType"] == "DISCHARGE_MIN"
        assert "_Active_meta" not in result[0]  # Meta fields stripped
        mock_get.assert_called_once()

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    def test_blocking_post(self, mock_post, coordinator, mock_schedule_data) -> None:
        """Test _blocking_post method."""
        schedules = mock_schedule_data["timeofuse"]

        coordinator._blocking_post(schedules)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == coordinator._url
        assert call_args[0][3] == {
            "timeofuse": _normalize_schedules([_strip_meta(rule) for rule in schedules])
        }

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    def test_blocking_get_with_metadata_stripping(self, mock_get, coordinator) -> None:
        """Test that _blocking_get strips metadata fields."""
        raw_data = {
            "timeofuse": [
                {
                    "Active": True,
                    "ScheduleType": "DISCHARGE_MIN",
                    "Power": 1000,
                    "TimeTable": {
                        "Start": "09:00",
                        "End": "11:00",
                        "_Meta": "hidden",
                    },
                    "Weekdays": {
                        "Mon": True,
                        "Tue": False,
                        "Wed": True,
                        "Thu": False,
                        "Fri": True,
                        "Sat": False,
                        "Sun": False,
                        "_Meta": "hidden",
                    },
                    "_Id": 1,
                    "_Meta": "hidden",
                },
            ]
        }
        mock_get.return_value = raw_data

        result = coordinator._blocking_get()

        assert len(result) == 1
        assert result[0]["Active"] is True
        assert result[0]["ScheduleType"] == "DISCHARGE_MIN"
        assert result[0]["Power"] == 1000
        assert result[0]["TimeTable"] == {"Start": "09:00", "End": "11:00"}
        assert "_Id" not in result[0]
        assert "_Meta" not in result[0]

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    def test_connection_error_handling(self, mock_get, coordinator) -> None:
        """Test that connection errors are handled properly."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(requests.ConnectionError):
            coordinator._blocking_get()

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    def test_http_error_handling(self, mock_get, coordinator) -> None:
        """Test that HTTP errors are handled properly."""
        error = requests.HTTPError("401 Unauthorized")
        mock_get.side_effect = error

        with pytest.raises(requests.HTTPError):
            coordinator._blocking_get()

    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    def test_test_connection_blocking(
        self, mock_get, coordinator, mock_schedule_data
    ) -> None:
        """Test connection testing method."""
        mock_get.return_value = mock_schedule_data

        result = coordinator.test_connection_blocking()

        assert len(result) == 5
        mock_get.assert_called_once_with(
            coordinator._url,
            coordinator._username,
            coordinator._password,
            15,
        )

    @patch("homeassistant.helpers.frame.report_usage")
    def test_url(self, mock_report_usage) -> None:  # NOQA: ARG002
        config_entry = MagicMock(
            data={
                "host": "example.com",
                "port": 80,
                "username": "user",
                "password": "pass",
            },
            spec=ConfigEntry,
        )
        coordinator = FroniusTDCCoordinator(
            config_entry=config_entry,
            hass=MagicMock(),
            logger=MagicMock(),
        )
        assert coordinator._url == "http://example.com:80/api/config/timeofuse"


class TestCoordinatorAsyncOperations:
    """Test async operations of the coordinator."""

    @pytest.fixture
    def coordinator_with_hass(self, mocker):
        """Create a coordinator with a real hass mock."""
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

        # Configure async_add_executor_job to execute the blocking function
        async def executor_job_handler(func, *args):
            return func(*args)

        hass_mock.async_add_executor_job = AsyncMock(side_effect=executor_job_handler)

        return FroniusTDCCoordinator(
            config_entry=config_entry,
            hass=hass_mock,
            logger=MagicMock(),
        )

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_update_data_timeout_handling(
        self, mock_get, coordinator_with_hass
    ):
        """Test that timeout errors during update are handled properly."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        with pytest.raises(UpdateFailed, match="Cannot reach"):
            await coordinator_with_hass._async_update_data()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_update_data_http_error(self, mock_get, coordinator_with_hass):
        """Test that HTTP errors during update are handled properly."""
        mock_get.side_effect = requests.HTTPError("500 Server Error")

        with pytest.raises(UpdateFailed, match="HTTP error"):
            await coordinator_with_hass._async_update_data()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_update_data_success(
        self, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test successful async update."""
        mock_get.return_value = mock_schedule_data

        result = await coordinator_with_hass._async_update_data()

        assert len(result) == 5
        assert result[0]["Active"] is True
        assert "_Active_meta" not in result[0]

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_update_data_invalid_payload(
        self, mock_get, coordinator_with_hass
    ):
        """Test malformed inverter schedule payload is surfaced as UpdateFailed."""
        mock_get.return_value = {"timeofuse": [{"Active": True}]}

        with pytest.raises(UpdateFailed, match="Invalid schedule payload"):
            await coordinator_with_hass._async_update_data()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_set_active_to_true(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test toggling a schedule to active."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()

        await coordinator_with_hass.async_set_active(0, active=True)

        mock_post.assert_called_once()
        call_args = mock_post.call_args[0]
        assert call_args[3]["timeofuse"][0]["Active"] is True
        coordinator_with_hass.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_set_active_to_false(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test toggling a schedule to inactive."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()

        await coordinator_with_hass.async_set_active(0, active=False)

        mock_post.assert_called_once()
        call_args = mock_post.call_args[0]
        assert call_args[3]["timeofuse"][0]["Active"] is False
        coordinator_with_hass.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_active_out_of_range(
        self, coordinator_with_hass, mock_schedule_data
    ):
        """Test that out-of-range index returns early with error log."""
        with patch(
            "custom_components.fronius_tdc.tdc_coordinator.fronius_get_json"
        ) as mock_get:
            mock_get.return_value = mock_schedule_data

            await coordinator_with_hass.async_set_active(99, active=True)

        # Method should return early without raising; async_refresh should not be called

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_set_active_out_of_range_skips_post_and_refresh(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test that out-of-range index does not post or refresh."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()

        await coordinator_with_hass.async_set_active(99, active=True)

        mock_post.assert_not_called()
        coordinator_with_hass.async_refresh.assert_not_called()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_set_active_get_http_error(
        self, mock_get, coordinator_with_hass
    ):
        """Test that HTTP errors during write read phase raise UpdateFailed."""
        mock_get.side_effect = requests.HTTPError("500 Server Error")

        with pytest.raises(UpdateFailed, match="HTTP error"):
            await coordinator_with_hass.async_set_active(0, active=True)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_set_active_get_request_error(
        self, mock_get, coordinator_with_hass
    ):
        """Test that request errors during write read phase raise UpdateFailed."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(UpdateFailed, match="Cannot reach"):
            await coordinator_with_hass.async_set_active(0, active=True)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_set_active_get_value_error(
        self, mock_get, coordinator_with_hass
    ):
        """Test invalid inverter payload during write read phase raises UpdateFailed."""
        mock_get.return_value = {"timeofuse": [{"Active": True}]}

        with pytest.raises(UpdateFailed, match="Invalid schedule payload"):
            await coordinator_with_hass.async_set_active(0, active=True)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_set_active_uses_latest_fetched_schedules(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test that write path uses fresh inverter data, not stale coordinator data."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()
        coordinator_with_hass.data = [{"Active": False}]

        await coordinator_with_hass.async_set_active(0, active=False)

        schedules = mock_post.call_args[0][3]["timeofuse"]
        assert len(schedules) == len(mock_schedule_data["timeofuse"])
        assert schedules[0]["Active"] is False
        assert schedules[1]["Active"] == mock_schedule_data["timeofuse"][1]["Active"]

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_set_active_request_error(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test that request errors are properly raised as UpdateFailed."""
        mock_get.return_value = mock_schedule_data
        mock_post.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(UpdateFailed, match="Failed to set active for schedule"):
            await coordinator_with_hass.async_set_active(0, active=True)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_set_active_preserves_other_schedules(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test that toggling one schedule doesn't affect others."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()

        await coordinator_with_hass.async_set_active(1, active=False)

        call_args = mock_post.call_args[0]
        schedules = call_args[3]["timeofuse"]
        # First schedule should remain unchanged
        assert schedules[0]["Active"] is True
        # Second schedule should be toggled
        assert schedules[1]["Active"] is False

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_set_active_invalid_update_value(
        self, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test invalid field update value is rejected before POST."""
        mock_get.return_value = mock_schedule_data

        with pytest.raises(UpdateFailed, match="Invalid schedule update"):
            await coordinator_with_hass.async_set_active(0, active="yes")

    @pytest.mark.asyncio
    async def test_async_update_rule_field_requires_path(self, coordinator_with_hass):
        """Test update helper requires a non-empty field path."""
        with pytest.raises(ValueError, match="field_path must not be empty"):
            await coordinator_with_hass._async_update_rule_field(
                0,
                field_path=(),
                value=True,
                operation="set value",
            )

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_update_rule_field_invalid_nested_path(
        self, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test update helper rejects nested path when parent object is missing."""
        mock_get.return_value = mock_schedule_data

        with pytest.raises(UpdateFailed, match="must be an object"):
            await coordinator_with_hass._async_update_rule_field(
                0,
                field_path=("NotThere", "Value"),
                value=True,
                operation="set nested value",
            )

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_set_active_post_value_error(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test ValueError from post phase is raised as UpdateFailed."""
        mock_get.return_value = mock_schedule_data
        mock_post.side_effect = ValueError("invalid payload")

        with pytest.raises(UpdateFailed, match="Invalid schedule update"):
            await coordinator_with_hass.async_set_active(0, active=True)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_update_rule_field_nested_success(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test nested field updates traverse and mutate child object path."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()

        await coordinator_with_hass._async_update_rule_field(
            0,
            field_path=("TimeTable", "Start"),
            value="12:00",
            operation="set start",
        )

        schedules = mock_post.call_args[0][3]["timeofuse"]
        assert schedules[0]["TimeTable"]["Start"] == "12:00"

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_add_schedule_appends_rule(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test adding a schedule appends it to the fetched list."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()
        new_schedule = {
            "Active": False,
            "ScheduleType": "CHARGE_MAX",
            "Power": 1500,
            "TimeTable": {"Start": "12:00", "End": "13:00"},
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

        await coordinator_with_hass.async_add_schedule(new_schedule)

        schedules = mock_post.call_args[0][3]["timeofuse"]
        assert len(schedules) == len(mock_schedule_data["timeofuse"]) + 1
        assert schedules[-1] == new_schedule
        coordinator_with_hass.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_add_schedule_invalid_rule(self, coordinator_with_hass):
        """Test adding an invalid schedule raises UpdateFailed."""
        with pytest.raises(UpdateFailed, match="Invalid schedule update"):
            await coordinator_with_hass.async_add_schedule({"Active": True})

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_add_schedule_get_request_error(
        self, mock_get, coordinator_with_hass
    ):
        """Test add_schedule surfaces GET request failures."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(UpdateFailed, match="Cannot reach"):
            await coordinator_with_hass.async_add_schedule(
                {
                    "Active": False,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 1000,
                    "TimeTable": {"Start": "12:00", "End": "13:00"},
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

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_add_schedule_get_invalid_payload(
        self, mock_get, coordinator_with_hass
    ):
        """Test add_schedule surfaces invalid fetched payloads."""
        mock_get.return_value = {"timeofuse": [{"Active": True}]}

        with pytest.raises(UpdateFailed, match="Invalid schedule payload"):
            await coordinator_with_hass.async_add_schedule(
                {
                    "Active": False,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 1000,
                    "TimeTable": {"Start": "12:00", "End": "13:00"},
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

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_add_schedule_get_http_error(
        self, mock_get, coordinator_with_hass
    ):
        """Test add_schedule surfaces GET HTTP failures."""
        mock_get.side_effect = requests.HTTPError("500 Server Error")

        with pytest.raises(UpdateFailed, match="HTTP error"):
            await coordinator_with_hass.async_add_schedule(
                {
                    "Active": False,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 1000,
                    "TimeTable": {"Start": "12:00", "End": "13:00"},
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

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_add_schedule_post_request_error(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test add_schedule surfaces POST request failures."""
        mock_get.return_value = mock_schedule_data
        mock_post.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(UpdateFailed, match="Failed to add schedule"):
            await coordinator_with_hass.async_add_schedule(
                {
                    "Active": False,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 1000,
                    "TimeTable": {"Start": "12:00", "End": "13:00"},
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

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_remove_schedule_removes_rule(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test removing a schedule deletes only the targeted entry."""
        mock_get.return_value = mock_schedule_data
        coordinator_with_hass.async_refresh = AsyncMock()

        await coordinator_with_hass.async_remove_schedule(1)

        schedules = mock_post.call_args[0][3]["timeofuse"]
        assert len(schedules) == len(mock_schedule_data["timeofuse"]) - 1
        assert schedules[0] == _normalize_rule(
            _strip_meta(mock_schedule_data["timeofuse"][0])
        )
        assert (
            _normalize_rule(_strip_meta(mock_schedule_data["timeofuse"][1]))
            not in schedules
        )
        coordinator_with_hass.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_remove_schedule_out_of_range(
        self, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test removing an unknown schedule index raises UpdateFailed."""
        mock_get.return_value = mock_schedule_data

        with pytest.raises(UpdateFailed, match="out of range"):
            await coordinator_with_hass.async_remove_schedule(99)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_remove_schedule_get_http_error(
        self, mock_get, coordinator_with_hass
    ):
        """Test remove_schedule surfaces GET HTTP failures."""
        mock_get.side_effect = requests.HTTPError("500 Server Error")

        with pytest.raises(UpdateFailed, match="HTTP error"):
            await coordinator_with_hass.async_remove_schedule(0)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_remove_schedule_get_invalid_payload(
        self, mock_get, coordinator_with_hass
    ):
        """Test remove_schedule surfaces invalid fetched payloads."""
        mock_get.return_value = {"timeofuse": [{"Active": True}]}

        with pytest.raises(UpdateFailed, match="Invalid schedule payload"):
            await coordinator_with_hass.async_remove_schedule(0)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    async def test_async_remove_schedule_get_request_error(
        self, mock_get, coordinator_with_hass
    ):
        """Test remove_schedule surfaces GET request failures."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(UpdateFailed, match="Cannot reach"):
            await coordinator_with_hass.async_remove_schedule(0)

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_get_json")
    @patch("custom_components.fronius_tdc.tdc_coordinator.fronius_post_json")
    async def test_async_remove_schedule_post_request_error(
        self, mock_post, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test remove_schedule surfaces POST request failures."""
        mock_get.return_value = mock_schedule_data
        mock_post.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(UpdateFailed, match="Failed to remove schedule 1"):
            await coordinator_with_hass.async_remove_schedule(1)


class TestCoordinatorMutators:
    """Test explicit coordinator mutator methods used by schedule entities."""

    @pytest.fixture
    def coordinator(self, mocker):
        """Create a coordinator with frame-reporting patched."""
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
        return FroniusTDCCoordinator(
            config_entry=config_entry,
            hass=MagicMock(),
            logger=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_async_set_power_dispatch(self, coordinator):
        """Test set_power dispatches through the shared field updater."""
        coordinator._async_update_rule_field = AsyncMock()

        await coordinator.async_set_power(2, power=4500)

        coordinator._async_update_rule_field.assert_called_once_with(
            2,
            field_path=("Power",),
            value=4500,
            operation="set power",
        )

    @pytest.mark.asyncio
    async def test_async_set_schedule_type_dispatch(self, coordinator):
        """Test set_schedule_type dispatches through the shared field updater."""
        coordinator._async_update_rule_field = AsyncMock()

        await coordinator.async_set_schedule_type(1, schedule_type="CHARGE_MAX")

        coordinator._async_update_rule_field.assert_called_once_with(
            1,
            field_path=("ScheduleType",),
            value="CHARGE_MAX",
            operation="set schedule type",
        )

    @pytest.mark.asyncio
    async def test_async_set_weekday_dispatch(self, coordinator):
        """Test set_weekday dispatches through the shared field updater."""
        coordinator._async_update_rule_field = AsyncMock()

        await coordinator.async_set_weekday(0, "Mon", enabled=True)

        coordinator._async_update_rule_field.assert_called_once_with(
            0,
            field_path=("Weekdays", "Mon"),
            value=True,
            operation="set weekday Mon",
        )

    @pytest.mark.asyncio
    async def test_async_set_start_time_dispatch(self, coordinator):
        """Test set_start_time dispatches through the shared field updater."""
        coordinator._async_update_rule_field = AsyncMock()

        await coordinator.async_set_start_time(0, start="09:30")

        coordinator._async_update_rule_field.assert_called_once_with(
            0,
            field_path=("TimeTable", "Start"),
            value="09:30",
            operation="set start time",
        )

    @pytest.mark.asyncio
    async def test_async_set_end_time_dispatch(self, coordinator):
        """Test set_end_time dispatches through the shared field updater."""
        coordinator._async_update_rule_field = AsyncMock()

        await coordinator.async_set_end_time(0, end="23:59")

        coordinator._async_update_rule_field.assert_called_once_with(
            0,
            field_path=("TimeTable", "End"),
            value="23:59",
            operation="set end time",
        )

    @pytest.mark.asyncio
    async def test_async_set_time_rejects_invalid_format(self, coordinator):
        """Test invalid time values are rejected before write."""
        coordinator._async_update_rule_field = AsyncMock()

        with pytest.raises(UpdateFailed, match="HH:MM"):
            await coordinator.async_set_start_time(0, start="24:00")

        coordinator._async_update_rule_field.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_power_rejects_non_int(self, coordinator):
        """Test set_power rejects non-integer values before write."""
        coordinator._async_update_rule_field = AsyncMock()

        with pytest.raises(UpdateFailed, match="Power must be an integer"):
            await coordinator.async_set_power(0, power=True)

        coordinator._async_update_rule_field.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_schedule_type_rejects_invalid(self, coordinator):
        """Test set_schedule_type rejects unsupported values before write."""
        coordinator._async_update_rule_field = AsyncMock()

        with pytest.raises(UpdateFailed, match="Unsupported ScheduleType"):
            await coordinator.async_set_schedule_type(0, schedule_type="INVALID")

        coordinator._async_update_rule_field.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_end_time_rejects_invalid_format(self, coordinator):
        """Test invalid end times are rejected before write."""
        coordinator._async_update_rule_field = AsyncMock()

        with pytest.raises(UpdateFailed, match="HH:MM"):
            await coordinator.async_set_end_time(0, end="9:30")

        coordinator._async_update_rule_field.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_weekday_rejects_invalid_day(self, coordinator):
        """Test set_weekday rejects unsupported day values before write."""
        coordinator._async_update_rule_field = AsyncMock()

        with pytest.raises(UpdateFailed, match="Unsupported weekday"):
            await coordinator.async_set_weekday(0, "Foo", enabled=True)

        coordinator._async_update_rule_field.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_weekday_rejects_non_bool_enabled(self, coordinator):
        """Test set_weekday rejects non-boolean enabled values before write."""
        coordinator._async_update_rule_field = AsyncMock()

        with pytest.raises(UpdateFailed, match="enabled must be boolean"):
            await coordinator.async_set_weekday(0, "Mon", enabled="yes")

        coordinator._async_update_rule_field.assert_not_called()


class TestScheduleValidationHelpers:
    """Test schema normalization and validator helpers."""

    def test_validate_schedule_type_valid(self) -> None:
        """Test all supported schedule types are accepted."""
        for value in ("CHARGE_MAX", "CHARGE_MIN", "DISCHARGE_MAX", "DISCHARGE_MIN"):
            _validate_schedule_type(value)

    def test_validate_schedule_type_invalid(self) -> None:
        """Test unsupported schedule type is rejected."""
        with pytest.raises(ValueError, match="Unsupported ScheduleType"):
            _validate_schedule_type("INVALID")

    def test_validate_schedule_type_requires_string(self) -> None:
        """Test non-string schedule type is rejected."""
        with pytest.raises(TypeError, match="must be a string"):
            _validate_schedule_type(123)

    def test_validate_time_value_rejects_non_hhmm(self) -> None:
        """Test strict HH:MM validation."""
        with pytest.raises(ValueError, match="HH:MM"):
            _validate_time_value("9:00", "TimeTable.Start")

    def test_validate_time_value_rejects_non_string(self) -> None:
        """Test non-string time values are rejected."""
        with pytest.raises(TypeError, match="HH:MM"):
            _validate_time_value(900, "TimeTable.Start")

    def test_validate_weekdays_requires_object(self) -> None:
        """Test weekday validator rejects non-object payloads."""
        with pytest.raises(TypeError, match="must be an object"):
            _validate_weekdays([])

    def test_validate_weekdays_missing_day(self) -> None:
        """Test weekday validator rejects incomplete maps."""
        with pytest.raises(ValueError, match="missing keys"):
            _validate_weekdays(
                {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": True,
                }
            )

    def test_validate_weekdays_rejects_non_boolean_value(self) -> None:
        """Test weekday validator rejects non-boolean day values."""
        with pytest.raises(TypeError, match="must be a boolean"):
            _validate_weekdays(
                {
                    "Mon": 1,
                    "Tue": False,
                    "Wed": True,
                    "Thu": False,
                    "Fri": True,
                    "Sat": False,
                    "Sun": False,
                }
            )

    def test_normalize_rule_requires_object(self) -> None:
        """Test rule normalizer rejects non-object payloads."""
        with pytest.raises(TypeError, match="must be an object"):
            _normalize_rule([])

    def test_normalize_rule_missing_required_keys(self) -> None:
        """Test rule normalizer rejects partial payloads."""
        with pytest.raises(ValueError, match="missing required keys"):
            _normalize_rule({"Active": True})

    def test_normalize_rule_requires_boolean_active(self) -> None:
        """Test Active must be a boolean."""
        with pytest.raises(TypeError, match="Active must be a boolean"):
            _normalize_rule(
                {
                    "Active": "true",
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 3000,
                    "TimeTable": {"Start": "08:00", "End": "10:00"},
                    "Weekdays": {
                        "Mon": True,
                        "Tue": False,
                        "Wed": True,
                        "Thu": False,
                        "Fri": True,
                        "Sat": False,
                        "Sun": False,
                    },
                }
            )

    def test_normalize_rule_rejects_boolean_power(self) -> None:
        """Test Power rejects booleans even though bool is int-like in Python."""
        with pytest.raises(TypeError, match="Power must be an integer"):
            _normalize_rule(
                {
                    "Active": True,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": True,
                    "TimeTable": {"Start": "08:00", "End": "10:00"},
                    "Weekdays": {
                        "Mon": True,
                        "Tue": False,
                        "Wed": True,
                        "Thu": False,
                        "Fri": True,
                        "Sat": False,
                        "Sun": False,
                    },
                }
            )

    def test_normalize_rule_requires_timetable_object(self) -> None:
        """Test TimeTable must be an object."""
        with pytest.raises(TypeError, match="TimeTable must be an object"):
            _normalize_rule(
                {
                    "Active": True,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 3000,
                    "TimeTable": "08:00-10:00",
                    "Weekdays": {
                        "Mon": True,
                        "Tue": False,
                        "Wed": True,
                        "Thu": False,
                        "Fri": True,
                        "Sat": False,
                        "Sun": False,
                    },
                }
            )

    def test_normalize_rule_missing_timetable_keys(self) -> None:
        """Test TimeTable requires Start and End keys."""
        with pytest.raises(ValueError, match="TimeTable missing required keys"):
            _normalize_rule(
                {
                    "Active": True,
                    "ScheduleType": "CHARGE_MAX",
                    "Power": 3000,
                    "TimeTable": {"Start": "08:00"},
                    "Weekdays": {
                        "Mon": True,
                        "Tue": False,
                        "Wed": True,
                        "Thu": False,
                        "Fri": True,
                        "Sat": False,
                        "Sun": False,
                    },
                }
            )

    def test_normalize_rule_keeps_canonical_shape(self) -> None:
        """Test normalization keeps the canonical rule shape."""
        result = _normalize_rule(
            {
                "Active": True,
                "ScheduleType": "CHARGE_MAX",
                "Power": 3000,
                "TimeTable": {"Start": "08:00", "End": "10:00", "Extra": "x"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": False,
                    "Wed": True,
                    "Thu": False,
                    "Fri": True,
                    "Sat": False,
                    "Sun": False,
                    "Extra": True,
                },
                "Extra": "ignored",
            }
        )

        assert result == {
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 3000,
            "TimeTable": {"Start": "08:00", "End": "10:00"},
            "Weekdays": {
                "Mon": True,
                "Tue": False,
                "Wed": True,
                "Thu": False,
                "Fri": True,
                "Sat": False,
                "Sun": False,
            },
        }

    def test_normalize_schedules_requires_list(self) -> None:
        """Test schedule list normalization rejects non-list payload."""
        with pytest.raises(TypeError, match="must be a list"):
            _normalize_schedules({"not": "a list"})
