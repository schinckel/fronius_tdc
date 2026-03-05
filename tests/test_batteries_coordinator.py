"""Tests for the batteries coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.fronius_tdc.batteries_coordinator import (
    FroniusBatteriesCoordinator,
    _strip_meta,
)


class TestStripMeta:
    """Test _strip_meta function."""

    def test_strip_meta_dict(self) -> None:
        """Test stripping metadata keys from dict."""
        data = {
            "HYB_EVU_CHARGEFROMGRID": True,
            "_Id": 1,
            "HYB_EM_POWER": 5000,
            "_Meta": "hidden",
        }
        result = _strip_meta(data)
        assert result == {"HYB_EVU_CHARGEFROMGRID": True, "HYB_EM_POWER": 5000}
        assert "_Id" not in result
        assert "_Meta" not in result

    def test_strip_meta_nested(self) -> None:
        """Test stripping metadata from nested structures."""
        data = {
            "HYB_EVU_CHARGEFROMGRID": True,
            "_Id": 1,
            "NestedConfig": {
                "Value": 100,
                "_Internal": "hidden",
            },
        }
        result = _strip_meta(data)
        assert result == {
            "HYB_EVU_CHARGEFROMGRID": True,
            "NestedConfig": {"Value": 100},
        }

    def test_strip_meta_list(self) -> None:
        """Test stripping metadata from lists."""
        data = [
            {"Value": 1, "_Id": 1},
            {"Value": 2, "_Id": 2},
        ]
        result = _strip_meta(data)
        assert result == [{"Value": 1}, {"Value": 2}]

    def test_strip_meta_scalar(self) -> None:
        """Test that scalar values pass through unchanged."""
        assert _strip_meta("test") == "test"
        assert _strip_meta(42) == 42
        assert _strip_meta(True) is True  # noqa: FBT003


class TestFroniusBatteriesCoordinator:
    """Test FroniusBatteriesCoordinator."""

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
        return FroniusBatteriesCoordinator(
            config_entry=config_entry,
            hass=MagicMock(),
            logger=MagicMock(),
        )

    @pytest.fixture
    def battery_config_data(self):
        """Sample battery configuration data."""
        return {
            "HYB_EVU_CHARGEFROMGRID": True,
            "HYB_BM_CHARGEFROMAC": False,
            "HYB_EM_POWER": 5000,
            "HYB_BM_PACMIN": 500,
            "HYB_BACKUP_CRITICALSOC": 10,
            "HYB_BACKUP_RESERVED": 20,
            "BAT_M0_SOC_MAX": 100,
            "BAT_M0_SOC_MIN": 0,
            "HYB_EM_MODE": 0,
            "BAT_M0_SOC_MODE": "auto",
            "_Id": 1,
        }

    @patch("custom_components.fronius_tdc.batteries_coordinator.fronius_get_json")
    def test_blocking_get(self, mock_get, coordinator, battery_config_data) -> None:
        """Test _blocking_get method."""
        mock_get.return_value = battery_config_data

        result = coordinator._blocking_get()

        assert result["HYB_EVU_CHARGEFROMGRID"] is True
        assert result["HYB_EM_POWER"] == 5000
        assert result["HYB_EM_MODE"] == 0
        assert "_Id" not in result  # Meta fields stripped
        mock_get.assert_called_once()

    @patch("custom_components.fronius_tdc.batteries_coordinator.fronius_post_json")
    def test_blocking_post(self, mock_post, coordinator) -> None:
        """Test _blocking_post method."""
        coordinator._blocking_post("HYB_EVU_CHARGEFROMGRID", value=True)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == coordinator._url
        assert call_args[0][3] == {"HYB_EVU_CHARGEFROMGRID": True}

    @patch("custom_components.fronius_tdc.batteries_coordinator.fronius_get_json")
    def test_blocking_get_with_metadata_stripping(self, mock_get, coordinator) -> None:
        """Test that _blocking_get strips metadata fields."""
        raw_data = {
            "HYB_EVU_CHARGEFROMGRID": True,
            "_Id": 1,
            "_Meta": "hidden",
        }
        mock_get.return_value = raw_data

        result = coordinator._blocking_get()

        assert result == {"HYB_EVU_CHARGEFROMGRID": True}
        assert "_Id" not in result
        assert "_Meta" not in result

    @patch("custom_components.fronius_tdc.batteries_coordinator.fronius_get_json")
    def test_blocking_get_handles_read_not_supported(
        self, mock_get, coordinator
    ) -> None:
        """Test that _blocking_get gracefully handles read not supported (404)."""
        error = requests.HTTPError("404 Not Found")
        mock_get.side_effect = error

        result = coordinator._blocking_get()

        # Should return empty dict on read error
        assert result == {}
        mock_get.assert_called_once()

    @patch("custom_components.fronius_tdc.batteries_coordinator.fronius_get_json")
    def test_connection_error_handling(self, mock_get, coordinator) -> None:
        """Test that connection errors raise UpdateFailed."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        # _blocking_get doesn't raise, but _async_update_data should
        # We're testing the blocking method directly here
        with pytest.raises(requests.ConnectionError):
            coordinator._blocking_get()

    @patch("custom_components.fronius_tdc.batteries_coordinator.fronius_post_json")
    def test_blocking_post_http_error(self, mock_post, coordinator) -> None:
        """Test that HTTP errors are raised during POST."""
        mock_post.side_effect = requests.HTTPError("401 Unauthorized")

        with pytest.raises(requests.HTTPError):
            coordinator._blocking_post("HYB_EVU_CHARGEFROMGRID", value=True)

    @pytest.mark.asyncio
    async def test_async_set_switch(self, coordinator) -> None:
        """Test async_set_switch method."""
        coordinator.data = {"HYB_EVU_CHARGEFROMGRID": False}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(coordinator, "_blocking_post") as mock_post,
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)
            await coordinator.async_set_switch("HYB_EVU_CHARGEFROMGRID", value=True)
            # Verify the correct key and value were passed
            call_args = mock_post.call_args
            assert call_args[0][0] == "HYB_EVU_CHARGEFROMGRID"
            assert call_args[0][1] is True

    @pytest.mark.asyncio
    async def test_async_set_number(self, coordinator) -> None:
        """Test async_set_number method."""
        coordinator.data = {"HYB_EM_POWER": 3000}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(coordinator, "_blocking_post") as mock_post,
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)
            await coordinator.async_set_number("HYB_EM_POWER", 5000)
            # Verify the correct key and value were passed
            call_args = mock_post.call_args
            assert call_args[0][0] == "HYB_EM_POWER"
            assert call_args[0][1] == 5000

    @pytest.mark.asyncio
    async def test_async_set_select(self, coordinator) -> None:
        """Test async_set_select method."""
        coordinator.data = {"HYB_EM_MODE": 0}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(coordinator, "_blocking_post") as mock_post,
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)
            await coordinator.async_set_select("HYB_EM_MODE", 1)
            # Verify the correct key and value were passed
            call_args = mock_post.call_args
            assert call_args[0][0] == "HYB_EM_MODE"
            assert call_args[0][1] == 1

    def test_test_connection_blocking(self, coordinator) -> None:
        """Test test_connection_blocking method."""
        with patch.object(
            coordinator, "_blocking_get", return_value={"HYB_EVU_CHARGEFROMGRID": True}
        ):
            result = coordinator.test_connection_blocking()
            assert result == {"HYB_EVU_CHARGEFROMGRID": True}

    @pytest.mark.asyncio
    async def test_async_set_switch_with_request_exception(self, coordinator) -> None:
        """Test async_set_switch raises UpdateFailed on RequestException."""
        coordinator.data = {"HYB_EVU_CHARGEFROMGRID": False}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(
                coordinator,
                "_blocking_post",
                side_effect=requests.ConnectionError("Connection error"),
            ),
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)

            with pytest.raises(UpdateFailed) as exc_info:
                await coordinator.async_set_switch("HYB_EVU_CHARGEFROMGRID", value=True)

            assert "Failed to set HYB_EVU_CHARGEFROMGRID to True" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_set_number_with_request_exception(self, coordinator) -> None:
        """Test async_set_number raises UpdateFailed on RequestException."""
        coordinator.data = {"HYB_EM_POWER": 3000}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(
                coordinator,
                "_blocking_post",
                side_effect=requests.Timeout("Request timeout"),
            ),
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)

            with pytest.raises(UpdateFailed) as exc_info:
                await coordinator.async_set_number("HYB_EM_POWER", 5000)

            assert "Failed to set HYB_EM_POWER to 5000" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_set_select_with_request_exception(self, coordinator) -> None:
        """Test async_set_select raises UpdateFailed on RequestException."""
        coordinator.data = {"HYB_EM_MODE": 0}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(
                coordinator,
                "_blocking_post",
                side_effect=requests.HTTPError("401 Unauthorized"),
            ),
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)

            with pytest.raises(UpdateFailed) as exc_info:
                await coordinator.async_set_select("HYB_EM_MODE", 1)

            assert "Failed to set HYB_EM_MODE to 1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_set_switch_calls_refresh(self, coordinator) -> None:
        """Test async_set_switch calls async_refresh after successful update."""
        coordinator.data = {"HYB_EVU_CHARGEFROMGRID": False}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(coordinator, "_blocking_post"),
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)
            await coordinator.async_set_switch("HYB_EVU_CHARGEFROMGRID", value=True)

            # Verify refresh was called after successful update
            coordinator.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_number_calls_refresh(self, coordinator) -> None:
        """Test async_set_number calls async_refresh after successful update."""
        coordinator.data = {"HYB_EM_POWER": 3000}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(coordinator, "_blocking_post"),
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)
            await coordinator.async_set_number("HYB_EM_POWER", 5000)

            # Verify refresh was called after successful update
            coordinator.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_select_calls_refresh(self, coordinator) -> None:
        """Test async_set_select calls async_refresh after successful update."""
        coordinator.data = {"HYB_EM_MODE": 0}
        coordinator.async_refresh = AsyncMock()

        with (
            patch.object(coordinator, "_blocking_post"),
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)
            await coordinator.async_set_select("HYB_EM_MODE", 1)

            # Verify refresh was called after successful update
            coordinator.async_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_with_exception(self, coordinator) -> None:
        """Test _async_update_data raises UpdateFailed on RequestException."""
        with (
            patch.object(
                coordinator,
                "_blocking_get",
                side_effect=requests.ConnectionError("Connection error"),
            ),
            patch.object(
                coordinator.hass, "async_add_executor_job", new_callable=AsyncMock
            ) as mock_executor,
        ):
            mock_executor.side_effect = lambda fn, *args: fn(*args)

            with pytest.raises(UpdateFailed) as exc_info:
                await coordinator._async_update_data()

            assert "Cannot reach Fronius inverter" in str(exc_info.value)

    @patch("custom_components.fronius_tdc.batteries_coordinator.fronius_get_json")
    def test_blocking_get_with_connection_error_raises(
        self, mock_get, coordinator
    ) -> None:
        """Test _blocking_get raises ConnectionError."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        with pytest.raises(requests.ConnectionError):
            coordinator._blocking_get()
