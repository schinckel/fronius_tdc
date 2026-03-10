"""Tests for battery configuration entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.number import FroniusBatteryNumber
from custom_components.fronius_tdc.select import FroniusBatterySelect
from custom_components.fronius_tdc.switch import FroniusBatterySwitch


@pytest.fixture
def batteries_coordinator():
    """Create a mock batteries coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "ChargePowerLimit": True,
        "ChargePowerMax": 5000,
        "OperatingMode": "charge",
    }
    coordinator.async_set_switch = AsyncMock()
    coordinator.async_set_number = AsyncMock()
    coordinator.async_set_select = AsyncMock()
    return coordinator


class TestBatterySwitch:
    """Test battery switch entity."""

    def test_battery_switch_is_on_true(self, batteries_coordinator) -> None:
        """Test battery switch is_on returns True when value is True."""
        entry = MagicMock(entry_id="entry1")
        switch = FroniusBatterySwitch(batteries_coordinator, entry, "ChargePowerLimit")
        assert switch.is_on is True

    def test_battery_switch_is_on_false(self, batteries_coordinator) -> None:
        """Test battery switch is_on returns False when value is False."""
        entry = MagicMock(entry_id="entry1")
        batteries_coordinator.data["ChargePowerLimit"] = False
        switch = FroniusBatterySwitch(batteries_coordinator, entry, "ChargePowerLimit")
        assert switch.is_on is False

    def test_battery_switch_is_on_missing_key(self, batteries_coordinator) -> None:
        """Test battery switch is_on returns False when key is missing."""
        entry = MagicMock(entry_id="entry1")
        batteries_coordinator.data = {}
        switch = FroniusBatterySwitch(batteries_coordinator, entry, "ChargePowerLimit")
        assert switch.is_on is False

    def test_battery_switch_is_on_none_data(self, batteries_coordinator) -> None:
        """Test battery switch is_on returns False when data is None."""
        entry = MagicMock(entry_id="entry1")
        batteries_coordinator.data = None
        switch = FroniusBatterySwitch(batteries_coordinator, entry, "ChargePowerLimit")
        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_battery_switch_async_turn_on(self, batteries_coordinator) -> None:
        """Test battery switch async_turn_on calls coordinator."""
        entry = MagicMock(entry_id="entry1")
        switch = FroniusBatterySwitch(batteries_coordinator, entry, "ChargePowerLimit")
        await switch.async_turn_on()
        batteries_coordinator.async_set_switch.assert_called_once_with(
            "ChargePowerLimit", value=True
        )

    @pytest.mark.asyncio
    async def test_battery_switch_async_turn_off(self, batteries_coordinator) -> None:
        """Test battery switch async_turn_off calls coordinator."""
        entry = MagicMock(entry_id="entry1")
        switch = FroniusBatterySwitch(batteries_coordinator, entry, "ChargePowerLimit")
        await switch.async_turn_off()
        batteries_coordinator.async_set_switch.assert_called_once_with(
            "ChargePowerLimit", value=False
        )


class TestBatteryNumber:
    """Test battery number entity."""

    def test_battery_number_native_value(self, batteries_coordinator) -> None:
        """Test battery number native_value property."""
        entry = MagicMock(entry_id="entry1")
        number = FroniusBatteryNumber(batteries_coordinator, entry, "ChargePowerMax")
        assert number.native_value == 5000

    def test_battery_number_native_value_missing_key(
        self, batteries_coordinator
    ) -> None:
        """Test battery number native_value with missing key in coordinator data."""
        entry = MagicMock(entry_id="entry1")
        # The coordinator data doesn't have the key
        batteries_coordinator.data = {"OtherKey": 1000}
        number = FroniusBatteryNumber(batteries_coordinator, entry, "ChargePowerMax")
        # When data doesn't contain the key, get() returns None,
        # which defaults to 0 in native_value
        assert number.native_value is None or number.native_value == 0

    def test_battery_number_native_value_none_data(self, batteries_coordinator) -> None:
        """Test battery number native_value when data is None."""
        entry = MagicMock(entry_id="entry1")
        batteries_coordinator.data = None
        number = FroniusBatteryNumber(batteries_coordinator, entry, "ChargePowerMax")
        # When data is None, the or [] handles it
        assert number.native_value is None or number.native_value == 0

    @pytest.mark.asyncio
    async def test_battery_number_async_set_native_value(
        self, batteries_coordinator
    ) -> None:
        """Test battery number async_set_native_value calls coordinator."""
        entry = MagicMock(entry_id="entry1")
        number = FroniusBatteryNumber(batteries_coordinator, entry, "ChargePowerMax")
        await number.async_set_native_value(6000)
        batteries_coordinator.async_set_number.assert_called_once_with(
            "ChargePowerMax", 6000
        )


class TestBatterySelect:
    """Test battery select entity."""

    def test_battery_select_current_option_valid(self, batteries_coordinator) -> None:
        """Test battery select current_option returns value when present."""
        entry = MagicMock(entry_id="entry1")
        select = FroniusBatterySelect(batteries_coordinator, entry, "OperatingMode")
        assert select.current_option == "charge"

    def test_battery_select_current_option_missing_key(
        self, batteries_coordinator
    ) -> None:
        """Test battery select current_option returns None when key is missing."""
        entry = MagicMock(entry_id="entry1")
        batteries_coordinator.data = {}
        select = FroniusBatterySelect(batteries_coordinator, entry, "OperatingMode")
        assert select.current_option is None

    def test_battery_select_current_option_none_data(
        self, batteries_coordinator
    ) -> None:
        """Test battery select current_option returns None when data is None."""
        entry = MagicMock(entry_id="entry1")
        batteries_coordinator.data = None
        select = FroniusBatterySelect(batteries_coordinator, entry, "OperatingMode")
        assert select.current_option is None

    @pytest.mark.asyncio
    async def test_battery_select_async_select_option_valid(
        self, batteries_coordinator
    ) -> None:
        """Test battery select async_select_option calls coordinator."""
        entry = MagicMock(entry_id="entry1")
        select = FroniusBatterySelect(batteries_coordinator, entry, "OperatingMode")
        await select.async_select_option("discharge")
        batteries_coordinator.async_set_select.assert_called_once_with(
            "OperatingMode", "discharge"
        )
