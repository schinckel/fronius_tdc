"""Tests for number entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import PERCENTAGE, UnitOfPower

from custom_components.fronius_tdc.const import DOMAIN
from custom_components.fronius_tdc.number import (
    NUMBER_MIN_MAX,
    PERCENTAGE_KEYS,
    FroniusBatteryNumber,
    FroniusSchedulePowerNumber,
    async_setup_entry,
)


class TestFroniusBatteryNumber:
    """Test FroniusBatteryNumber entity."""

    @pytest.fixture
    def coordinator_mock(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.data = {
            "HYB_EM_POWER": 5000,
            "HYB_BM_PACMIN": 500,
            "HYB_BACKUP_CRITICALSOC": 10,
            "HYB_BACKUP_RESERVED": 20,
            "BAT_M0_SOC_MAX": 100,
            "BAT_M0_SOC_MIN": 0,
        }
        return coordinator

    @pytest.fixture
    def config_entry_mock(self):
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_123"
        return entry

    @pytest.fixture
    def power_number(self, coordinator_mock, config_entry_mock):
        """Create a power number entity."""
        return FroniusBatteryNumber(coordinator_mock, config_entry_mock, "HYB_EM_POWER")

    @pytest.fixture
    def soc_number(self, coordinator_mock, config_entry_mock):
        """Create an SOC (percentage) number entity."""
        return FroniusBatteryNumber(
            coordinator_mock, config_entry_mock, "BAT_M0_SOC_MAX"
        )

    def test_number_initialization_power(self, power_number) -> None:
        """Test number entity initialization for power."""
        assert power_number._key == "HYB_EM_POWER"
        assert (
            power_number._attr_unique_id == "test_entry_123_battery_number_HYB_EM_POWER"
        )
        assert power_number._attr_device_info["manufacturer"] == "Fronius"
        assert power_number._attr_device_info["model"] == "GEN24 Plus / Symo GEN24"
        assert power_number._attr_native_min_value == -200000
        assert power_number._attr_native_max_value == 200000
        assert power_number._attr_native_unit_of_measurement == UnitOfPower.WATT

    def test_number_initialization_percentage(self, soc_number) -> None:
        """Test number entity initialization for percentage."""
        assert soc_number._key == "BAT_M0_SOC_MAX"
        assert soc_number._attr_native_min_value == 0
        assert soc_number._attr_native_max_value == 100
        assert soc_number._attr_native_unit_of_measurement == PERCENTAGE

    def test_name_property(self, power_number) -> None:
        """Test name property uses label from const."""
        assert power_number.name == "Energy Management Power"

    def test_name_property_percentage(self, soc_number) -> None:
        """Test name property for percentage entity."""
        assert soc_number.name == "Battery Max SOC"

    def test_name_property_with_fallback(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test name property falls back to title-cased key."""
        # Use a key that's not in BATTERY_CONFIG_LABELS
        number = FroniusBatteryNumber(
            coordinator_mock, config_entry_mock, "UNKNOWN_KEY"
        )
        assert number.name == "Unknown Key"

    def test_native_value_property(self, power_number) -> None:
        """Test native_value property returns current value."""
        assert power_number.native_value == 5000.0

    def test_native_value_property_with_missing_data(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None when key is missing."""
        coordinator_mock.data = {}
        number = FroniusBatteryNumber(
            coordinator_mock, config_entry_mock, "HYB_EM_POWER"
        )
        assert number.native_value is None

    def test_native_value_property_with_none_coordinator_data(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None when coordinator data is None."""
        coordinator_mock.data = None
        number = FroniusBatteryNumber(
            coordinator_mock, config_entry_mock, "HYB_EM_POWER"
        )
        assert number.native_value is None

    def test_native_value_converts_to_float(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value converts integer values to float."""
        coordinator_mock.data = {"HYB_EM_POWER": 3000}
        number = FroniusBatteryNumber(
            coordinator_mock, config_entry_mock, "HYB_EM_POWER"
        )
        assert number.native_value == 3000.0
        assert isinstance(number.native_value, float)

    def test_unit_of_measurement_for_all_percentage_keys(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test that all percentage keys have PERCENTAGE unit."""
        for key in PERCENTAGE_KEYS:
            number = FroniusBatteryNumber(coordinator_mock, config_entry_mock, key)
            assert number._attr_native_unit_of_measurement == PERCENTAGE, (
                f"{key} should have PERCENTAGE unit"
            )

    def test_min_max_values_for_all_keys(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test that all keys in NUMBER_MIN_MAX have proper min/max values."""
        for key in NUMBER_MIN_MAX:
            number = FroniusBatteryNumber(coordinator_mock, config_entry_mock, key)
            min_val, max_val = NUMBER_MIN_MAX[key]
            assert number._attr_native_min_value == min_val, f"{key} min value mismatch"
            assert number._attr_native_max_value == max_val, f"{key} max value mismatch"

    @pytest.mark.asyncio
    async def test_async_set_native_value_int(self, power_number) -> None:
        """Test setting an integer value."""
        power_number.coordinator.async_set_number = AsyncMock()

        await power_number.async_set_native_value(6000.0)

        power_number.coordinator.async_set_number.assert_called_once_with(
            "HYB_EM_POWER", 6000
        )

    @pytest.mark.asyncio
    async def test_async_set_native_value_float(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test setting a float value (non-integer)."""
        number = FroniusBatteryNumber(
            coordinator_mock, config_entry_mock, "HYB_EM_POWER"
        )
        number.coordinator.async_set_number = AsyncMock()

        await number.async_set_native_value(5500.5)

        number.coordinator.async_set_number.assert_called_once_with(
            "HYB_EM_POWER", 5500.5
        )

    @pytest.mark.asyncio
    async def test_async_set_native_value_percentage(self, soc_number) -> None:
        """Test setting a percentage value."""
        soc_number.coordinator.async_set_number = AsyncMock()

        await soc_number.async_set_native_value(95.0)

        soc_number.coordinator.async_set_number.assert_called_once_with(
            "BAT_M0_SOC_MAX", 95
        )


class TestAsyncSetupEntry:
    """Test async_setup_entry function for number entities."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_coordinator(self) -> None:
        """Test setup entry creates number entities."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = {
            "HYB_EM_POWER": 5000,
            "HYB_BM_PACMIN": 500,
            "HYB_BACKUP_CRITICALSOC": 10,
            "HYB_BACKUP_RESERVED": 20,
            "BAT_M0_SOC_MAX": 100,
            "BAT_M0_SOC_MIN": 0,
        }

        hass.data = {
            DOMAIN: {"batteries_coordinator": {config_entry.entry_id: coordinator}}
        }
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        coordinator.async_config_entry_first_refresh.assert_called_once()
        async_add_entities.assert_called_once()

        # Check that 6 number entities were created (all numeric keys)
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 6
        assert all(isinstance(e, FroniusBatteryNumber) for e in entities)

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

        hass.data = {
            DOMAIN: {"batteries_coordinator": {config_entry.entry_id: coordinator}}
        }
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
        # Only provide some numeric keys
        coordinator.data = {
            "HYB_EM_POWER": 5000,
            "BAT_M0_SOC_MAX": 100,
        }

        hass.data = {
            DOMAIN: {"batteries_coordinator": {config_entry.entry_id: coordinator}}
        }
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Only 2 entities should be created
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 2
        keys = [e._key for e in entities]
        assert "HYB_EM_POWER" in keys
        assert "BAT_M0_SOC_MAX" in keys

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_schedule_coordinator_only(self) -> None:
        """Test setup entry creates schedule power numbers without battery data."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        tdc_coordinator = MagicMock()
        tdc_coordinator.async_config_entry_first_refresh = AsyncMock()
        tdc_coordinator.data = [
            {"Power": 1000, "TimeTable": {"Start": "08:00", "End": "10:00"}},
            {"Power": 2000, "TimeTable": {"Start": "12:00", "End": "14:00"}},
        ]

        hass.data = {DOMAIN: {config_entry.entry_id: tdc_coordinator}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        tdc_coordinator.async_config_entry_first_refresh.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 2
        assert all(isinstance(e, FroniusSchedulePowerNumber) for e in entities)


class TestFroniusSchedulePowerNumber:
    """Test FroniusSchedulePowerNumber entity."""

    @pytest.fixture
    def coordinator_mock(self):
        """Create a mock TOU coordinator."""
        coordinator = MagicMock()
        coordinator.data = [
            {"Power": 5400, "TimeTable": {"Start": "18:00", "End": "21:00"}}
        ]
        return coordinator

    @pytest.fixture
    def config_entry_mock(self):
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_123"
        entry.title = "Test Inverter"
        return entry

    def test_schedule_power_initialization(self, coordinator_mock, config_entry_mock):
        """Test schedule power entity initialization."""
        entity = FroniusSchedulePowerNumber(coordinator_mock, config_entry_mock, 0)

        assert entity._attr_unique_id == "test_entry_123_schedule_0_power"
        assert entity.entity_id == "number.test_inverter_schedule_0_power"
        assert entity.native_value == 5400.0
        assert entity.name == "Schedule 1 Power"

    def test_schedule_power_out_of_range_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test schedule power returns None when index is out of range."""
        entity = FroniusSchedulePowerNumber(coordinator_mock, config_entry_mock, 5)

        assert entity.native_value is None

    def test_schedule_power_missing_value_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test schedule power returns None when the power field is missing."""
        coordinator_mock.data = [{"TimeTable": {"Start": "00:00", "End": "01:00"}}]
        entity = FroniusSchedulePowerNumber(coordinator_mock, config_entry_mock, 0)

        assert entity.native_value is None

    @pytest.mark.asyncio
    async def test_schedule_power_set_value(self, coordinator_mock, config_entry_mock):
        """Test schedule power setter uses coordinator mutator."""
        coordinator_mock.async_set_power = AsyncMock()
        entity = FroniusSchedulePowerNumber(coordinator_mock, config_entry_mock, 0)

        await entity.async_set_native_value(3200.0)

        coordinator_mock.async_set_power.assert_called_once_with(index=0, power=3200)
