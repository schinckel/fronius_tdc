"""Tests for select entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import (
    DOMAIN,
)
from custom_components.fronius_tdc.select import (
    FroniusBatterySelect,
    async_setup_entry,
)


class TestFroniusBatterySelect:
    """Test FroniusBatterySelect entity."""

    @pytest.fixture
    def coordinator_mock(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.data = {
            "HYB_EM_MODE": 0,
            "BAT_M0_SOC_MODE": "auto",
        }
        return coordinator

    @pytest.fixture
    def config_entry_mock(self):
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_123"
        return entry

    @pytest.fixture
    def em_mode_select(self, coordinator_mock, config_entry_mock):
        """Create an EM mode select entity."""
        return FroniusBatterySelect(coordinator_mock, config_entry_mock, "HYB_EM_MODE")

    @pytest.fixture
    def soc_mode_select(self, coordinator_mock, config_entry_mock):
        """Create an SOC mode select entity."""
        return FroniusBatterySelect(coordinator_mock, config_entry_mock, "BAT_M0_SOC_MODE")

    def test_select_initialization_em_mode(self, em_mode_select) -> None:
        """Test select entity initialization for EM mode."""
        assert em_mode_select._key == "HYB_EM_MODE"
        assert em_mode_select._attr_unique_id == "test_entry_123_battery_select_HYB_EM_MODE"
        assert em_mode_select._attr_device_info["manufacturer"] == "Fronius"
        assert em_mode_select._attr_device_info["model"] == "GEN24 Plus / Symo GEN24"

    def test_select_options_em_mode(self, em_mode_select) -> None:
        """Test select options for EM mode."""
        assert "Automatic" in em_mode_select._attr_options
        assert "Manual" in em_mode_select._attr_options
        assert len(em_mode_select._attr_options) == 2

    def test_select_options_soc_mode(self, soc_mode_select) -> None:
        """Test select options for SOC mode."""
        assert "Manual" in soc_mode_select._attr_options
        assert "Auto" in soc_mode_select._attr_options
        assert len(soc_mode_select._attr_options) == 2

    def test_label_to_value_mapping_em_mode(self, em_mode_select) -> None:
        """Test reverse label-to-value mapping for EM mode."""
        assert em_mode_select._label_to_value["Automatic"] == 0
        assert em_mode_select._label_to_value["Manual"] == 1

    def test_label_to_value_mapping_soc_mode(self, soc_mode_select) -> None:
        """Test reverse label-to-value mapping for SOC mode."""
        assert soc_mode_select._label_to_value["Auto"] == "auto"
        assert soc_mode_select._label_to_value["Manual"] == "manual"

    def test_name_property(self, em_mode_select) -> None:
        """Test name property uses label from const."""
        assert em_mode_select.name == "Energy Management Mode"

    def test_name_property_soc(self, soc_mode_select) -> None:
        """Test name property for SOC mode."""
        assert soc_mode_select.name == "Battery SOC Mode"

    def test_name_property_with_fallback(self, coordinator_mock, config_entry_mock) -> None:
        """Test name property falls back to title-cased key."""
        # Use a key that's not in BATTERY_CONFIG_LABELS
        select = FroniusBatterySelect(coordinator_mock, config_entry_mock, "UNKNOWN_KEY")
        assert select.name == "Unknown Key"

    def test_current_option_property(self, em_mode_select) -> None:
        """Test current_option property returns label for current value."""
        assert em_mode_select.current_option == "Automatic"

    def test_current_option_property_manual(self, coordinator_mock, config_entry_mock) -> None:
        """Test current_option property when set to Manual."""
        coordinator_mock.data = {"HYB_EM_MODE": 1}
        select = FroniusBatterySelect(coordinator_mock, config_entry_mock, "HYB_EM_MODE")
        assert select.current_option == "Manual"

    def test_current_option_property_soc_mode(self, soc_mode_select) -> None:
        """Test current_option property for SOC mode."""
        assert soc_mode_select.current_option == "Auto"

    def test_current_option_with_missing_key(self, coordinator_mock, config_entry_mock) -> None:
        """Test current_option returns None when key is missing."""
        coordinator_mock.data = {}
        select = FroniusBatterySelect(coordinator_mock, config_entry_mock, "HYB_EM_MODE")
        assert select.current_option is None

    def test_current_option_with_none_coordinator_data(self, coordinator_mock, config_entry_mock) -> None:
        """Test current_option returns None when coordinator data is None."""
        coordinator_mock.data = None
        select = FroniusBatterySelect(coordinator_mock, config_entry_mock, "HYB_EM_MODE")
        assert select.current_option is None

    def test_current_option_with_unknown_value(self, coordinator_mock, config_entry_mock) -> None:
        """Test current_option returns None for unknown values."""
        coordinator_mock.data = {"HYB_EM_MODE": 999}
        select = FroniusBatterySelect(coordinator_mock, config_entry_mock, "HYB_EM_MODE")
        assert select.current_option is None

    @pytest.mark.asyncio
    async def test_async_select_option_automatic(self, em_mode_select) -> None:
        """Test selecting the Automatic option."""
        em_mode_select.coordinator.async_set_select = AsyncMock()

        await em_mode_select.async_select_option("Automatic")

        em_mode_select.coordinator.async_set_select.assert_called_once_with("HYB_EM_MODE", 0)

    @pytest.mark.asyncio
    async def test_async_select_option_manual(self, em_mode_select) -> None:
        """Test selecting the Manual option."""
        em_mode_select.coordinator.async_set_select = AsyncMock()

        await em_mode_select.async_select_option("Manual")

        em_mode_select.coordinator.async_set_select.assert_called_once_with("HYB_EM_MODE", 1)

    @pytest.mark.asyncio
    async def test_async_select_option_soc_auto(self, soc_mode_select) -> None:
        """Test selecting the Auto option for SOC mode."""
        soc_mode_select.coordinator.async_set_select = AsyncMock()

        await soc_mode_select.async_select_option("Auto")

        soc_mode_select.coordinator.async_set_select.assert_called_once_with("BAT_M0_SOC_MODE", "auto")

    @pytest.mark.asyncio
    async def test_async_select_option_soc_manual(self, soc_mode_select) -> None:
        """Test selecting the Manual option for SOC mode."""
        soc_mode_select.coordinator.async_set_select = AsyncMock()

        await soc_mode_select.async_select_option("Manual")

        soc_mode_select.coordinator.async_set_select.assert_called_once_with("BAT_M0_SOC_MODE", "manual")

    @pytest.mark.asyncio
    async def test_async_select_option_unknown(self, coordinator_mock, config_entry_mock) -> None:
        """Test selecting an unknown option (call is skipped, error logged)."""
        select = FroniusBatterySelect(coordinator_mock, config_entry_mock, "HYB_EM_MODE")
        select.coordinator.async_set_select = AsyncMock()

        await select.async_select_option("UnknownOption")

        # async_set_select should not be called for unknown options
        select.coordinator.async_set_select.assert_not_called()


class TestAsyncSetupEntry:
    """Test async_setup_entry function for select entities."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_coordinator(self) -> None:
        """Test setup entry creates select entities."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = {
            "HYB_EM_MODE": 0,
            "BAT_M0_SOC_MODE": "auto",
        }

        hass.data = {DOMAIN: {"batteries_coordinator": {config_entry.entry_id: coordinator}}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        coordinator.async_config_entry_first_refresh.assert_called_once()
        async_add_entities.assert_called_once()

        # Check that 2 select entities were created
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 2
        assert all(isinstance(e, FroniusBatterySelect) for e in entities)

    @pytest.mark.asyncio
    async def test_async_setup_entry_without_coordinator(self) -> None:
        """Test setup entry returns early if no coordinator."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        hass.data = {DOMAIN: {}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_empty_data(self) -> None:
        """Test setup entry with coordinator returning no data."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = {}

        hass.data = {DOMAIN: {"batteries_coordinator": {config_entry.entry_id: coordinator}}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # No entities should be created if coordinator data is empty
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_partial_data(self) -> None:
        """Test setup entry with coordinator returning partial data."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        # Only provide EM mode
        coordinator.data = {
            "HYB_EM_MODE": 0,
        }

        hass.data = {DOMAIN: {"batteries_coordinator": {config_entry.entry_id: coordinator}}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Only 1 entity should be created
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert entities[0]._key == "HYB_EM_MODE"

    @pytest.mark.asyncio
    async def test_async_setup_entry_filters_unknown_keys(self) -> None:
        """Test setup entry filters out keys not in BATTERY_SELECT_OPTIONS."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        # Include an unknown key that's not in BATTERY_SELECT_OPTIONS
        coordinator.data = {
            "HYB_EM_MODE": 0,
            "UNKNOWN_KEY": "value",
        }

        hass.data = {DOMAIN: {"batteries_coordinator": {config_entry.entry_id: coordinator}}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Only 1 entity should be created
        # (only HYB_EM_MODE is in BATTERY_SELECT_OPTIONS)
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert entities[0]._key == "HYB_EM_MODE"
