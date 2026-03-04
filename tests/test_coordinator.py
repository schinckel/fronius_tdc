"""Tests for the data coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
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
    def coordinator_mock(self, mock_schedule_data):
        """Create a mock coordinator for testing methods."""
        coordinator = MagicMock(spec=FroniusTDCCoordinator)
        coordinator.data = mock_schedule_data["timeofuse"]
        coordinator._url = "http://192.168.1.1:80/api/config/timeofuse"
        coordinator._host = "192.168.1.1"
        coordinator._port = 80
        coordinator._username = "customer"
        coordinator._password = "password"  # noqa: S105
        # Bind the actual methods to the mock so we can test them
        coordinator._strip_meta = _strip_meta
        coordinator._blocking_get = FroniusTDCCoordinator._blocking_get.__get__(
            coordinator
        )
        coordinator._blocking_post = FroniusTDCCoordinator._blocking_post.__get__(
            coordinator
        )
        coordinator.test_connection_blocking = (
            FroniusTDCCoordinator.test_connection_blocking.__get__(coordinator)
        )
        coordinator.async_refresh = AsyncMock()
        return coordinator

    def test_coordinator_url_property(self, coordinator_mock) -> None:
        """Test URL property construction."""
        assert coordinator_mock._url == "http://192.168.1.1:80/api/config/timeofuse"

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_blocking_get(self, mock_get, coordinator_mock, mock_schedule_data) -> None:
        """Test _blocking_get method."""
        mock_get.return_value = mock_schedule_data

        result = coordinator_mock._blocking_get()

        assert len(result) == 2
        assert result[0]["Active"] is True
        assert result[0]["ScheduleType"] == "CHARGE_MAX"
        assert "_Id" not in result[0]  # Meta fields stripped
        mock_get.assert_called_once()

    @patch("custom_components.fronius_tdc.coordinator.fronius_post_json")
    def test_blocking_post(self, mock_post, coordinator_mock) -> None:
        """Test _blocking_post method."""
        schedules = [
            {"Active": True, "ScheduleType": "CHARGE_MAX"},
            {"Active": False, "ScheduleType": "DISCHARGE_MAX"},
        ]

        coordinator_mock._blocking_post(schedules)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == coordinator_mock._url
        assert call_args[0][3] == {"timeofuse": schedules}

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_blocking_get_with_metadata_stripping(
        self, mock_get, coordinator_mock
    ) -> None:
        """Test that _blocking_get strips metadata fields."""
        raw_data = {
            "timeofuse": [
                {"Active": True, "_Id": 1, "_Meta": "hidden"},
            ]
        }
        mock_get.return_value = raw_data

        result = coordinator_mock._blocking_get()

        assert len(result) == 1
        assert result[0] == {"Active": True}
        assert "_Id" not in result[0]
        assert "_Meta" not in result[0]

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_connection_error_handling(self, mock_get, coordinator_mock) -> None:
        """Test that connection errors are handled properly."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(requests.ConnectionError):
            coordinator_mock._blocking_get()

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_http_error_handling(self, mock_get, coordinator_mock) -> None:
        """Test that HTTP errors are handled properly."""
        error = requests.HTTPError("401 Unauthorized")
        mock_get.side_effect = error

        with pytest.raises(requests.HTTPError):
            coordinator_mock._blocking_get()

    @patch("custom_components.fronius_tdc.coordinator.fronius_get_json")
    def test_test_connection_blocking(
        self, mock_get, coordinator_mock, mock_schedule_data
    ) -> None:
        """Test connection testing method."""
        mock_get.return_value = mock_schedule_data

        result = coordinator_mock.test_connection_blocking()

        assert len(result) == 2
        mock_get.assert_called_once_with(
            coordinator_mock._url,
            coordinator_mock._username,
            coordinator_mock._password,
            15,
        )


class TestCoordinatorAsyncOperations:
    """Test async operations of the coordinator."""

    @pytest.mark.asyncio
    async def test_async_update_data_timeout_handling(self, hass_mock):
        """Test that timeout errors during update are handled properly."""
        coordinator = MagicMock(spec=FroniusTDCCoordinator)
        coordinator.hass = hass_mock
        coordinator._username = "customer"
        coordinator._password = "password"  # noqa: S105
        coordinator._url = "http://192.168.1.1:80/api/config/timeofuse"

        async def failing_job(func, *args):  # noqa: ANN202, ARG001
            raise requests.Timeout("Request timed out")  # noqa: EM101, TRY003

        hass_mock.async_add_executor_job = AsyncMock(side_effect=failing_job)
        coordinator._async_update_data = (
            FroniusTDCCoordinator._async_update_data.__get__(coordinator)
        )

        with pytest.raises(UpdateFailed, match="Cannot reach"):
            await coordinator._async_update_data()

    def test_blocking_get_with_metadata_stripping(self):
        """Test that blocking_get strips metadata fields."""
        coordinator = MagicMock(spec=FroniusTDCCoordinator)
        coordinator._url = "http://192.168.1.1:80/api/config/timeofuse"
        coordinator._username = "customer"
        coordinator._password = "password"  # noqa: S105

        data_with_meta = {
            "timeofuse": [
                {
                    "_Id": 123,
                    "_Version": "1.0",
                    "Active": True,
                    "Power": 3000,
                    "TimeTable": {"_Calculated": True, "Start": "22:00"},
                }
            ]
        }

        with patch(
            "custom_components.fronius_tdc.coordinator.fronius_get_json"
        ) as mock_get:
            mock_get.return_value = data_with_meta

            coordinator._blocking_get = FroniusTDCCoordinator._blocking_get.__get__(
                coordinator
            )
            result = coordinator._blocking_get()

            # Verify metadata is stripped
            assert len(result) == 1
            assert "_Id" not in result[0]
            assert "_Version" not in result[0]
            assert "_Calculated" not in result[0]["TimeTable"]
            assert result[0]["Active"] is True
            assert result[0]["TimeTable"]["Start"] == "22:00"

    def test_blocking_post_with_schedules(self):
        """Test blocking_post serializes and posts schedule data."""
        coordinator = MagicMock(spec=FroniusTDCCoordinator)
        coordinator._url = "http://192.168.1.1:80/api/config/timeofuse"
        coordinator._username = "customer"
        coordinator._password = "password"  # noqa: S105

        test_schedules = [
            {
                "Active": True,
                "ScheduleType": "CHARGE_MAX",
                "Power": 3000,
                "TimeTable": {"Start": "22:00", "End": "06:00"},
            }
        ]

        with patch(
            "custom_components.fronius_tdc.coordinator.fronius_post_json"
        ) as mock_post:
            coordinator._blocking_post = FroniusTDCCoordinator._blocking_post.__get__(
                coordinator
            )
            coordinator._blocking_post(test_schedules)

            mock_post.assert_called_once()
            args = mock_post.call_args[0]
            assert args[3] == {"timeofuse": test_schedules}

    @pytest.mark.asyncio
    async def test_async_set_active_out_of_range_index(self, hass_mock):
        """Test async_set_active with an out-of-range index."""
        coordinator = MagicMock(spec=FroniusTDCCoordinator)
        coordinator.data = [{"Active": True}]
        coordinator.hass = hass_mock

        async def blocking_job(func, *args):  # noqa: ANN202
            pass

        hass_mock.async_add_executor_job = AsyncMock(side_effect=blocking_job)
        coordinator.async_set_active = FroniusTDCCoordinator.async_set_active.__get__(
            coordinator
        )

        with patch(
            "custom_components.fronius_tdc.coordinator.fronius_post_json"
        ) as mock_post:
            # Should not post when index is out of range
            await coordinator.async_set_active(10, active=True)
            mock_post.assert_not_called()
