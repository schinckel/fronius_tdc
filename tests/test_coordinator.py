"""Tests for the data coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.fronius_tdc.coordinator import (
    FroniusTDCCoordinator,
    _strip_meta,
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

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_blocking_get(self, mock_get, coordinator, mock_schedule_data) -> None:
        """Test _blocking_get method."""
        mock_get.return_value = mock_schedule_data

        result = coordinator._blocking_get()

        assert len(result) == 2
        assert result[0]["Active"] is True
        assert result[0]["ScheduleType"] == "CHARGE_MAX"
        assert "_Id" not in result[0]  # Meta fields stripped
        mock_get.assert_called_once()

    @patch("custom_components.fronius_tdc.coordinator.fronius_post_json")
    def test_blocking_post(self, mock_post, coordinator) -> None:
        """Test _blocking_post method."""
        schedules = [
            {"Active": True, "ScheduleType": "CHARGE_MAX"},
            {"Active": False, "ScheduleType": "DISCHARGE_MAX"},
        ]

        coordinator._blocking_post(schedules)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == coordinator._url
        assert call_args[0][3] == {"timeofuse": schedules}

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_blocking_get_with_metadata_stripping(self, mock_get, coordinator) -> None:
        """Test that _blocking_get strips metadata fields."""
        raw_data = {
            "timeofuse": [
                {"Active": True, "_Id": 1, "_Meta": "hidden"},
            ]
        }
        mock_get.return_value = raw_data

        result = coordinator._blocking_get()

        assert len(result) == 1
        assert result[0] == {"Active": True}
        assert "_Id" not in result[0]
        assert "_Meta" not in result[0]

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_connection_error_handling(self, mock_get, coordinator) -> None:
        """Test that connection errors are handled properly."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(requests.ConnectionError):
            coordinator._blocking_get()

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_http_error_handling(self, mock_get, coordinator) -> None:
        """Test that HTTP errors are handled properly."""
        error = requests.HTTPError("401 Unauthorized")
        mock_get.side_effect = error

        with pytest.raises(requests.HTTPError):
            coordinator._blocking_get()

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_test_connection_blocking(
        self, mock_get, coordinator, mock_schedule_data
    ) -> None:
        """Test connection testing method."""
        mock_get.return_value = mock_schedule_data

        result = coordinator.test_connection_blocking()

        assert len(result) == 2
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
    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    async def test_async_update_data_timeout_handling(
        self, mock_get, coordinator_with_hass
    ):
        """Test that timeout errors during update are handled properly."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        with pytest.raises(UpdateFailed, match="Cannot reach"):
            await coordinator_with_hass._async_update_data()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    async def test_async_update_data_http_error(self, mock_get, coordinator_with_hass):
        """Test that HTTP errors during update are handled properly."""
        mock_get.side_effect = requests.HTTPError("500 Server Error")

        with pytest.raises(UpdateFailed, match="HTTP error"):
            await coordinator_with_hass._async_update_data()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    async def test_async_update_data_success(
        self, mock_get, coordinator_with_hass, mock_schedule_data
    ):
        """Test successful async update."""
        mock_get.return_value = mock_schedule_data

        result = await coordinator_with_hass._async_update_data()

        assert len(result) == 2
        assert result[0]["Active"] is True
        assert "_Id" not in result[0]
