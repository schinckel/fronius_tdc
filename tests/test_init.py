"""Tests for the integration lifecycle (__init__.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.fronius_tdc import (
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.fronius_tdc.const import DOMAIN


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_creates_coordinator(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that setup creates a coordinator and stores it."""
        # Setup mocks
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_123"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        # Call setup
        result = await async_setup_entry(hass, config_entry)

        # Verify result
        assert result is True

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_stores_coordinator_in_hass_data(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that coordinator is stored in hass.data[DOMAIN]."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify coordinator is stored
        assert DOMAIN in hass.data
        assert hass.data[DOMAIN]["entry_1"] is mock_tdc

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_calls_first_refresh(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that first_refresh is called during setup."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify first_refresh was called
        mock_tdc.async_config_entry_first_refresh.assert_called_once()
        mock_batteries.async_config_entry_first_refresh.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_forwards_entry_setups(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that entry setup forwards to platforms."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify platforms are setup
        hass.config_entries.async_forward_entry_setups.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_registers_update_listener(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that update listener is registered."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify update listener is added
        config_entry.add_update_listener.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_multiple_entries(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test setup with multiple config entries."""
        mock_tdc1 = AsyncMock()
        mock_tdc1.async_config_entry_first_refresh = AsyncMock()
        mock_tdc2 = AsyncMock()
        mock_tdc2.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.side_effect = [mock_tdc1, mock_tdc2]

        mock_batteries1 = AsyncMock()
        mock_batteries1.async_config_entry_first_refresh = AsyncMock()
        mock_batteries2 = AsyncMock()
        mock_batteries2.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.side_effect = [
            mock_batteries1,
            mock_batteries2,
        ]

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        config_entry1 = MagicMock()
        config_entry1.entry_id = "entry_1"
        config_entry1.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry1.add_update_listener = MagicMock()

        config_entry2 = MagicMock()
        config_entry2.entry_id = "entry_2"
        config_entry2.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry2.add_update_listener = MagicMock()

        # Setup both entries
        await async_setup_entry(hass, config_entry1)
        await async_setup_entry(hass, config_entry2)

        # Verify both are stored
        assert hass.data[DOMAIN]["entry_1"] is mock_tdc1
        assert hass.data[DOMAIN]["entry_2"] is mock_tdc2


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    @pytest.mark.asyncio
    async def test_async_unload_entry_unloads_platforms(self):
        """Test that unload removes entry platforms."""
        hass = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        hass.config_entries.async_unload_platforms.assert_called_once_with(
            config_entry, ["switch", "number", "select"]
        )

    @pytest.mark.asyncio
    async def test_async_unload_entry_handles_failure(self):
        """Test unload when platform unload fails."""
        hass = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        result = await async_unload_entry(hass, config_entry)

        assert result is False


class TestAsyncReloadEntry:
    """Test async_reload_entry function."""

    @pytest.mark.asyncio
    async def test_async_reload_entry_reloads_config(self):
        """Test that reload triggers entry reload."""
        hass = AsyncMock()
        hass.config_entries.async_reload = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        await async_reload_entry(hass, config_entry)

        hass.config_entries.async_reload.assert_called_once_with("entry_1")

    @pytest.mark.asyncio
    async def test_async_reload_entry_return_value(self):
        """Test that reload doesn't return anything."""
        hass = AsyncMock()
        hass.config_entries.async_reload = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        result = await async_reload_entry(hass, config_entry)

        assert result is None


class TestIntegrationLifecycle:
    """Integration tests for the full lifecycle."""

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_full_setup_unload_cycle(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test complete setup and unload cycle."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        # Setup
        setup_result = await async_setup_entry(hass, config_entry)
        assert setup_result is True
        assert DOMAIN in hass.data

        # Unload
        unload_result = await async_unload_entry(hass, config_entry)
        assert unload_result is True

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_setup_reload_cycle(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test setup followed by reload."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.config_entries.async_reload = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        # Setup
        await async_setup_entry(hass, config_entry)

        # Reload
        await async_reload_entry(hass, config_entry)

        # Verify reload was called
        hass.config_entries.async_reload.assert_called_once()
