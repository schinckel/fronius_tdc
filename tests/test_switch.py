"""Tests for switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import (
    DOMAIN,
    SCHEDULE_ACTIVE_SWITCH_DESCRIPTION,
    SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS,
)
from custom_components.fronius_tdc.switch import (
    FroniusBatterySwitch,
    FroniusScheduleEntity,
    FroniusScheduleFieldSwitch,
    FroniusScheduleSwitch,
    FroniusScheduleWeekdaySwitch,
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
        entry.title = "Test Inverter"
        return entry

    @pytest.fixture
    def switch(self, coordinator_mock, config_entry_mock):
        """Create a switch entity."""
        return FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)

    def test_switch_initialization(self, switch, config_entry_mock) -> None:  # noqa: ARG002
        """Test switch initialization."""
        assert switch._index == 0
        assert switch._attr_unique_id == "test_entry_123_schedule_0"
        assert switch.entity_id == "switch.test_inverter_schedule_0_active"
        assert switch.entity_description == SCHEDULE_ACTIVE_SWITCH_DESCRIPTION
        assert switch._attr_device_info["manufacturer"] == "Fronius"
        assert switch._attr_device_info["model"] == "GEN24 Plus / Symo GEN24"

    def test_schedule_entity_nested_value_lookup(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test the shared schedule helper resolves nested paths."""
        entity = FroniusScheduleEntity(coordinator_mock, config_entry_mock, 0)

        assert entity._get_schedule_value(("TimeTable", "Start")) == "18:00"
        assert entity._get_schedule_value(("Weekdays", "Mon")) is True
        assert entity._get_schedule_value(("Missing",)) is None
        assert entity._get_schedule_value(("Power", "Nested")) is None
        assert entity._get_schedule_value(()) == coordinator_mock.data[0]

    @pytest.mark.asyncio
    async def test_descriptor_switch_dispatches_configured_setter(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test generic schedule switch dispatches through its descriptor."""
        coordinator_mock.async_set_active = AsyncMock()
        switch = FroniusScheduleFieldSwitch(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_ACTIVE_SWITCH_DESCRIPTION,
        )

        await switch.async_turn_on()
        await switch.async_turn_off()

        assert switch.is_on is True
        coordinator_mock.async_set_active.assert_any_call(index=0, active=True)
        coordinator_mock.async_set_active.assert_any_call(index=0, active=False)

    @pytest.mark.asyncio
    async def test_descriptor_switch_dispatches_with_extra_setter_args(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test generic schedule switch dispatches weekday-style setter args."""
        coordinator_mock.async_set_weekday = AsyncMock()
        switch = FroniusScheduleFieldSwitch(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS[0],
        )

        await switch.async_turn_on()

        coordinator_mock.async_set_weekday.assert_called_once_with(
            0,
            "Mon",
            enabled=True,
        )

    def test_switch_name_property(self, switch) -> None:
        """Test switch name generation."""
        expected_name = "Discharge Min 5400W 18:00-21:00"
        assert switch.name == expected_name

    def test_switch_name_with_missing_data(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test switch name with incomplete schedule data."""
        coordinator_mock.data = [{}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
        assert switch.name == " 0W ?-?"

    def test_icon_charge_max(self, coordinator_mock, config_entry_mock) -> None:
        """Test icon for CHARGE_MAX schedule."""
        coordinator_mock.data = [{"ScheduleType": "CHARGE_MAX"}]
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)
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
        assert attrs["schedule_type"] == "DISCHARGE_MIN"
        assert attrs["power_w"] == 5400
        assert attrs["start"] == "18:00"
        assert attrs["end"] == "21:00"
        assert "Mon" in attrs["days"]
        assert "Sat" in attrs["days"]
        assert len(attrs["days"]) == 7

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

        switch.coordinator.async_set_active.assert_called_once_with(
            index=0, active=True
        )

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

        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        coordinator.async_config_entry_first_refresh.assert_called_once()
        async_add_entities.assert_called_once()

        # Check that entities were created for each schedule
        entities = async_add_entities.call_args[0][0]
        active_switches = [e for e in entities if isinstance(e, FroniusScheduleSwitch)]
        weekday_switches = [
            e for e in entities if isinstance(e, FroniusScheduleWeekdaySwitch)
        ]
        assert len(active_switches) == 2
        assert len(weekday_switches) == 14
        assert active_switches[0]._index == 0
        assert active_switches[1]._index == 1

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_battery_coordinator(self) -> None:
        """Test setup entry creates battery switch entities."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        # Setup TOU coordinator
        tdc_coordinator = MagicMock()
        tdc_coordinator.async_config_entry_first_refresh = AsyncMock()
        tdc_coordinator.data = []

        # Setup battery coordinator
        battery_coordinator = MagicMock()
        battery_coordinator.async_config_entry_first_refresh = AsyncMock()
        battery_coordinator.data = {
            "HYB_EVU_CHARGEFROMGRID": True,
            "HYB_BM_CHARGEFROMAC": False,
        }

        hass.data = {
            DOMAIN: {
                "test_entry": tdc_coordinator,
                "batteries_coordinator": {"test_entry": battery_coordinator},
            }
        }

        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Verify both coordinators were refreshed
        tdc_coordinator.async_config_entry_first_refresh.assert_called_once()
        battery_coordinator.async_config_entry_first_refresh.assert_called_once()

        # Check that entities were created (2 schedules + 2 battery switches)
        entities = async_add_entities.call_args[0][0]
        battery_switches = [e for e in entities if isinstance(e, FroniusBatterySwitch)]
        assert len(battery_switches) == 2
        assert all(isinstance(e, FroniusBatterySwitch) for e in battery_switches)

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_battery_coordinator(self) -> None:
        """Test setup entry when battery coordinator is missing."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = []

        hass.data = {DOMAIN: {"test_entry": coordinator}}

        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Should still be called, just with fewer entities
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Should only have TOU entities (none in this case)
        assert all(isinstance(e, FroniusScheduleSwitch) for e in entities)

    @pytest.mark.asyncio
    async def test_async_setup_entry_battery_with_no_data(self) -> None:
        """Test setup entry when battery coordinator has no data."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        tdc_coordinator = MagicMock()
        tdc_coordinator.async_config_entry_first_refresh = AsyncMock()
        tdc_coordinator.data = []

        battery_coordinator = MagicMock()
        battery_coordinator.async_config_entry_first_refresh = AsyncMock()
        battery_coordinator.data = {}  # Empty data

        hass.data = {
            DOMAIN: {
                "test_entry": tdc_coordinator,
                "batteries_coordinator": {"test_entry": battery_coordinator},
            }
        }

        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Should be called with empty list since no battery data exists
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        battery_switches = [e for e in entities if isinstance(e, FroniusBatterySwitch)]
        assert len(battery_switches) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_tou_coordinator(self) -> None:
        """Test setup entry when TOU coordinator is missing."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        # Setup only battery coordinator, no TOU coordinator
        battery_coordinator = MagicMock()
        battery_coordinator.async_config_entry_first_refresh = AsyncMock()
        battery_coordinator.data = {
            "HYB_EVU_CHARGEFROMGRID": True,
            "HYB_BM_CHARGEFROMAC": False,
        }

        hass.data = {
            DOMAIN: {
                "batteries_coordinator": {"test_entry": battery_coordinator},
            }
        }

        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        # Should still be called with battery entities only
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        # Should only have battery switch entities (no TOU)
        assert all(isinstance(e, FroniusBatterySwitch) for e in entities)
        assert len(entities) == 2


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

        coordinator_mock.async_set_active.assert_called_once_with(index=0, active=True)

    @pytest.mark.asyncio
    async def test_switch_turn_off_with_kwargs(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test turn_off with extra kwargs (should be ignored)."""
        coordinator_mock.async_set_active = AsyncMock()
        switch = FroniusScheduleSwitch(coordinator_mock, config_entry_mock, 0)

        await switch.async_turn_off(some_kwarg="value")

        coordinator_mock.async_set_active.assert_called_once_with(index=0, active=False)

    @pytest.mark.asyncio
    async def test_weekday_switch_turn_on(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test weekday switch dispatches to async_set_weekday."""
        coordinator_mock.async_set_weekday = AsyncMock()
        weekday_switch = FroniusScheduleWeekdaySwitch(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS[0],
        )

        await weekday_switch.async_turn_on()

        coordinator_mock.async_set_weekday.assert_called_once_with(
            0,
            "Mon",
            enabled=True,
        )

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
        assert switch1._attr_device_info["identifiers"] == {(DOMAIN, "test_entry_123")}  # type: ignore  # noqa: PGH003

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


class TestFroniusBatterySwitch:
    """Test FroniusBatterySwitch battery configuration entity."""

    @pytest.fixture
    def battery_coordinator_mock(self):
        """Create a mock battery coordinator."""
        coordinator = MagicMock()
        coordinator.data = {
            "HYB_EVU_CHARGEFROMGRID": True,
            "HYB_BM_CHARGEFROMAC": False,
        }
        return coordinator

    @pytest.fixture
    def config_entry_mock(self):
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_123"
        return entry

    @pytest.fixture
    def battery_switch(self, battery_coordinator_mock, config_entry_mock):
        """Create a battery switch entity."""
        return FroniusBatterySwitch(
            battery_coordinator_mock, config_entry_mock, "HYB_EVU_CHARGEFROMGRID"
        )

    def test_battery_switch_initialization(self, battery_switch) -> None:
        """Test battery switch initialization."""
        assert battery_switch._key == "HYB_EVU_CHARGEFROMGRID"
        assert (
            battery_switch._attr_unique_id
            == "test_entry_123_battery_HYB_EVU_CHARGEFROMGRID"
        )
        assert battery_switch._attr_device_info["manufacturer"] == "Fronius"
        assert battery_switch._attr_device_info["model"] == "GEN24 Plus / Symo GEN24"

    def test_battery_switch_name(self, battery_switch) -> None:
        """Test battery switch name from labels."""
        assert battery_switch.name == "Charge From Grid"

    def test_battery_switch_name_fallback(
        self, battery_coordinator_mock, config_entry_mock
    ) -> None:
        """Test battery switch name falls back to title case."""
        switch = FroniusBatterySwitch(
            battery_coordinator_mock, config_entry_mock, "UNKNOWN_KEY"
        )
        assert switch.name == "Unknown Key"

    def test_battery_switch_is_on_true(self, battery_switch) -> None:
        """Test is_on property when True."""
        assert battery_switch.is_on is True

    def test_battery_switch_is_on_false(
        self, battery_coordinator_mock, config_entry_mock
    ) -> None:
        """Test is_on property when False."""
        switch = FroniusBatterySwitch(
            battery_coordinator_mock, config_entry_mock, "HYB_BM_CHARGEFROMAC"
        )
        assert switch.is_on is False

    def test_battery_switch_is_on_missing_key(
        self, battery_coordinator_mock, config_entry_mock
    ) -> None:
        """Test is_on returns False when key is missing."""
        switch = FroniusBatterySwitch(
            battery_coordinator_mock, config_entry_mock, "MISSING_KEY"
        )
        assert switch.is_on is False

    def test_battery_switch_is_on_none_data(
        self, battery_coordinator_mock, config_entry_mock
    ) -> None:
        """Test is_on returns False when coordinator data is None."""
        battery_coordinator_mock.data = None
        switch = FroniusBatterySwitch(
            battery_coordinator_mock, config_entry_mock, "HYB_EVU_CHARGEFROMGRID"
        )
        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_battery_switch_async_turn_on(self, battery_switch) -> None:
        """Test turning on a battery switch."""
        battery_switch.coordinator.async_set_switch = AsyncMock()

        await battery_switch.async_turn_on()

        battery_switch.coordinator.async_set_switch.assert_called_once_with(
            "HYB_EVU_CHARGEFROMGRID", value=True
        )

    @pytest.mark.asyncio
    async def test_battery_switch_async_turn_off(self, battery_switch) -> None:
        """Test turning off a battery switch."""
        battery_switch.coordinator.async_set_switch = AsyncMock()

        await battery_switch.async_turn_off()

        battery_switch.coordinator.async_set_switch.assert_called_once_with(
            "HYB_EVU_CHARGEFROMGRID", value=False
        )

    def test_battery_switch_unique_id_per_key(
        self, battery_coordinator_mock, config_entry_mock
    ) -> None:
        """Test that unique IDs are different for each battery switch key."""
        switch1 = FroniusBatterySwitch(
            battery_coordinator_mock, config_entry_mock, "HYB_EVU_CHARGEFROMGRID"
        )
        switch2 = FroniusBatterySwitch(
            battery_coordinator_mock, config_entry_mock, "HYB_BM_CHARGEFROMAC"
        )

        assert switch1._attr_unique_id != switch2._attr_unique_id
        assert (
            switch1._attr_unique_id == "test_entry_123_battery_HYB_EVU_CHARGEFROMGRID"
        )
        assert switch2._attr_unique_id == "test_entry_123_battery_HYB_BM_CHARGEFROMAC"
