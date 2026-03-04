"""Tests for switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN
from custom_components.fronius_tdc.switch import (
    FroniusScheduleSwitch,
    async_setup_entry,
)


class TestFroniusScheduleSwitch:
    """Test FroniusScheduleSwitch entity."""

    @pytest.fixture
    def coordinator_mock(self, mock_schedule_data):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.data = mock_schedule_data["timeofuse"]
        return coordinator

    @pytest.fixture
    def config_entry_mock(self):
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_123"
        return entry

    @pytest.fixture
    def switch(self, coordinator_mock, config_entry_mock):
        """Create a switch entity."""
        return FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)

    def test_switch_initialization(self, switch, config_entry_mock) -> None:  # noqa: ARG002
        """Test switch initialization."""
        assert switch._index == 0
        assert switch._attr_unique_id == "test_entry_123_schedule_0"
        assert switch._attr_device_info["manufacturer"] == "Fronius"
        assert switch._attr_device_info["model"] == "GEN24 Plus / Symo GEN24"

    def test_switch_name_property(self, switch) -> None:
        """Test switch name generation."""
        expected_name = "Charge Max 3000W 22:00-06:00"
        assert switch.name == expected_name

    def test_switch_name_with_missing_data(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test switch name with incomplete schedule data."""
        coordinator_mock.data = [{}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.name == " 0W ?-?"

    def test_icon_charge_max(self, switch) -> None:
        """Test icon for CHARGE_MAX schedule."""
        assert switch.icon == "mdi:battery-arrow-up"

    def test_icon_charge_min(self, coordinator_mock, config_entry_mock) -> None:
        """Test icon for CHARGE_MIN schedule."""
        coordinator_mock.data = [{"ScheduleType": "CHARGE_MIN"}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.icon == "mdi:battery-plus-outline"

    def test_icon_discharge_max(self, coordinator_mock, config_entry_mock) -> None:
        """Test icon for DISCHARGE_MAX schedule."""
        coordinator_mock.data = [{"ScheduleType": "DISCHARGE_MAX"}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.icon == "mdi:battery-arrow-down"

    def test_icon_discharge_min(self, coordinator_mock, config_entry_mock) -> None:
        """Test icon for DISCHARGE_MIN schedule."""
        coordinator_mock.data = [{"ScheduleType": "DISCHARGE_MIN"}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.icon == "mdi:battery-minus-outline"

    def test_icon_default(self, coordinator_mock, config_entry_mock) -> None:
        """Test default icon for unknown schedule type."""
        coordinator_mock.data = [{"ScheduleType": "UNKNOWN"}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.icon == "mdi:battery-clock"

    def test_is_on_when_active(self, switch) -> None:
        """Test is_on property when schedule is active."""
        assert switch.is_on is True

    def test_is_on_when_inactive(self, coordinator_mock, config_entry_mock) -> None:
        """Test is_on property when schedule is inactive."""
        coordinator_mock.data = [{"Active": False}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.is_on is False

    def test_is_on_with_missing_data(self, coordinator_mock, config_entry_mock) -> None:
        """Test is_on property with missing Active field."""
        coordinator_mock.data = [{}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.is_on is False

    def test_extra_state_attributes(self, switch) -> None:
        """Test extra state attributes."""
        attrs = switch.extra_state_attributes
        assert attrs["schedule_type"] == "CHARGE_MAX"
        assert attrs["power_w"] == 3000
        assert attrs["start"] == "22:00"
        assert attrs["end"] == "06:00"
        assert "Mon" in attrs["days"]
        assert "Sat" not in attrs["days"]

    def test_extra_state_attributes_with_missing_data(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test extra state attributes with incomplete data."""
        coordinator_mock.data = [
            {
                "TimeTable": {"Start": "10:00"},
                "Weekdays": {"Mon": True, "Tue": False},
            }
        ]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        attrs = switch.extra_state_attributes
        assert attrs["start"] == "10:00"
        assert attrs["end"] is None
        assert attrs["days"] == ["Mon"]

    @pytest.mark.asyncio
    async def test_async_turn_on(self, switch) -> None:
        """Test turning on the schedule."""
        switch.coordinator.async_set_active = AsyncMock()

        await switch.async_turn_on()

        switch.coordinator.async_set_active.assert_called_once_with(0, active=True)

    @pytest.mark.asyncio
    async def test_async_turn_off(self, switch) -> None:
        """Test turning off the schedule."""
        switch.coordinator.async_set_active = AsyncMock()

        await switch.async_turn_off()

        switch.coordinator.async_set_active.assert_called_once_with(
            index=0, active=False
        )


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_async_setup_entry(self) -> None:
        """Test setup entry creates entities."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = [
            {"Active": True, "ScheduleType": "CHARGE_MAX"},
            {"Active": False, "ScheduleType": "DISCHARGE_MAX"},
        ]

        hass.data = {DOMAIN: {"test_entry": coordinator}}

        async_add_entities = AsyncMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        coordinator.async_config_entry_first_refresh.assert_called_once()
        async_add_entities.assert_called_once()

        # Check that entities were created for each schedule
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 2
        assert all(isinstance(e, FroniusScheduleSwitch) for e in entities)
        assert entities[0]._index == 0
        assert entities[1]._index == 1
