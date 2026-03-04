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


class TestSwitchEdgeCases:
    """Test edge cases and error conditions for switch entities."""

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

    def test_switch_with_empty_weekdays(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test switch with no active weekdays."""
        coordinator_mock.data = [
            {
                "Active": True,
                "ScheduleType": "CHARGE_MAX",
                "Power": 1000,
                "TimeTable": {"Start": "10:00", "End": "14:00"},
                "Weekdays": {
                    "Mon": False,
                    "Tue": False,
                    "Wed": False,
                    "Thu": False,
                    "Fri": False,
                    "Sat": False,
                    "Sun": False,
                },
            }
        ]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        attrs = switch.extra_state_attributes

        assert attrs["days"] == []

    def test_switch_with_all_weekdays_active(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test switch with all weekdays active."""
        coordinator_mock.data = [
            {
                "Active": True,
                "ScheduleType": "DISCHARGE_MAX",
                "Power": 2000,
                "TimeTable": {"Start": "08:00", "End": "18:00"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": True,
                    "Sun": True,
                },
            }
        ]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        attrs = switch.extra_state_attributes

        assert len(attrs["days"]) == 7
        assert set(attrs["days"]) == {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}

    def test_switch_with_zero_power(self, coordinator_mock, config_entry_mock) -> None:
        """Test switch with zero power value."""
        coordinator_mock.data = [
            {
                "Active": False,
                "ScheduleType": "CHARGE_MAX",
                "Power": 0,
                "TimeTable": {"Start": "00:00", "End": "00:00"},
            }
        ]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.name == "Charge Max 0W 00:00-00:00"

    def test_switch_name_with_special_characters_in_time(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test that switch name handles times correctly."""
        coordinator_mock.data = [
            {
                "Active": True,
                "ScheduleType": "CHARGE_MIN",
                "Power": 500,
                "TimeTable": {"Start": "09:30", "End": "17:45"},
            }
        ]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.name == "Charge Min 500W 09:30-17:45"

    def test_switch_coordinator_data_changes(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test switch behavior when coordinator data changes."""
        coordinator_mock.data = [
            {"Active": True, "ScheduleType": "CHARGE_MAX", "Power": 3000}
        ]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)

        initial_is_on = switch.is_on
        assert initial_is_on is True

        # Simulate coordinator data update
        coordinator_mock.data = [
            {"Active": False, "ScheduleType": "CHARGE_MAX", "Power": 3000}
        ]

        updated_is_on = switch.is_on
        assert updated_is_on is False

    def test_switch_with_missing_schedule_type(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test switch with missing schedule type."""
        coordinator_mock.data = [
            {
                "Active": True,
                "Power": 3000,
                "TimeTable": {"Start": "22:00", "End": "06:00"},
            }
        ]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.icon == "mdi:battery-clock"
        assert switch.name == " 3000W 22:00-06:00"

    @pytest.mark.asyncio
    async def test_switch_turn_on_with_kwargs(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test turn_on with extra kwargs (should be ignored)."""
        coordinator_mock.async_set_active = AsyncMock()
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)

        await switch.async_turn_on(extra_param="ignored")

        coordinator_mock.async_set_active.assert_called_once_with(0, active=True)

    @pytest.mark.asyncio
    async def test_switch_turn_off_with_kwargs(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test turn_off with extra kwargs (should be ignored)."""
        coordinator_mock.async_set_active = AsyncMock()
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)

        await switch.async_turn_off(some_kwarg="value")

        coordinator_mock.async_set_active.assert_called_once_with(index=0, active=False)

    def test_switch_device_info_consistent(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test that device info is consistent across switches."""
        coordinator_mock.data = [
            {"Active": True, "ScheduleType": "CHARGE_MAX"},
            {"Active": False, "ScheduleType": "DISCHARGE_MAX"},
        ]

        switch1 = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        switch2 = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 1)

        # Device info should be the same for both
        assert switch1._attr_device_info == switch2._attr_device_info
        assert switch1._attr_device_info["identifiers"] == {(DOMAIN, "test_entry_123")}

    def test_schedule_out_of_range_index(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test switch behavior when index is out of range."""
        coordinator_mock.data = [{"Active": True, "ScheduleType": "CHARGE_MAX"}]
        # Create switch with index 5 but only 1 schedule exists
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 5)

        # _schedule should return empty dict
        assert switch._schedule == {}
        # name should gracefully handle missing data
        assert switch.name == " 0W ?-?"
        # is_on should return False with missing data
        assert switch.is_on is False

    def test_switch_unique_id_varies_by_index(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test that unique IDs are different for each switch."""
        switches = [
            FroniusScheduleSwitch(coordinator_mock, config_entry_mock, i)
            for i in range(3)
        ]

        unique_ids = [switch._attr_unique_id for switch in switches]
        assert len(set(unique_ids)) == 3  # All unique
        assert unique_ids[0] == "test_entry_123_schedule_0"
        assert unique_ids[1] == "test_entry_123_schedule_1"
        assert unique_ids[2] == "test_entry_123_schedule_2"
