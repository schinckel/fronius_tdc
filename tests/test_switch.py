"""Tests for switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN, SCHEDULE_SWITCH_DESCRIPTIONS
from custom_components.fronius_tdc.switch import (
    FroniusBatterySwitch,
    FroniusScheduleSwitch,
    async_setup_entry,
)


@pytest.fixture
def schedule_coordinator():
    """Create a mock TDC coordinator with sample schedule data."""
    coordinator = MagicMock()
    coordinator.data = [
        {
            "rule_id": "1",
            "Active": True,
            "ScheduleType": "CHARGE_MAX",
            "Power": 3000,
            "TimeTable": {"Start": "22:00", "End": "06:00"},
            "Weekdays": {
                "Mon": True,
                "Tue": True,
                "Wed": True,
                "Thu": True,
                "Fri": True,
                "Sat": False,
                "Sun": False,
            },
        }
    ]
    coordinator.resolve_rule_index = MagicMock(return_value=0)
    coordinator.get_rule_ids = MagicMock(return_value=["1"])
    coordinator.async_config_entry_first_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def batteries_coordinator():
    """Create a mock batteries coordinator with sample battery data."""
    coordinator = MagicMock()
    coordinator.data = {
        "HYB_EVU_CHARGEFROMGRID": True,
        "HYB_BM_CHARGEFROMAC": False,
        "HYB_EM_POWER": 5000,
    }
    coordinator.async_config_entry_first_refresh = AsyncMock()
    return coordinator


def test_schedule_switch_active(schedule_coordinator) -> None:
    """Test that FroniusScheduleSwitch reports correct on/off state."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)
    assert switch.is_on is True
    assert switch.extra_state_attributes["rule_id"] == "1"


@pytest.mark.asyncio
async def test_schedule_switch_weekday_toggle(schedule_coordinator) -> None:
    """Test that weekday switch calls async_set_weekday with correct parameters."""
    entry = MagicMock(entry_id="entry1")
    weekday_desc = next(
        desc for desc in SCHEDULE_SWITCH_DESCRIPTIONS if desc.weekday == "Sun"
    )
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", weekday_desc)

    schedule_coordinator.async_set_weekday = AsyncMock()
    await switch.async_turn_on()
    schedule_coordinator.async_set_weekday.assert_called_once_with(
        "1", "Sun", enabled=True
    )


@pytest.mark.asyncio
async def test_async_setup_entry_creates_schedule_switches(
    schedule_coordinator,
) -> None:
    """Test that async_setup_entry creates schedule switch entities."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")
    hass.data = {DOMAIN: {"entry1": schedule_coordinator}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)


@pytest.mark.asyncio
async def test_async_setup_entry_without_batteries_coordinator(
    schedule_coordinator,
) -> None:
    """Test setup when batteries coordinator is missing."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")
    # No batteries coordinator
    hass.data = {DOMAIN: {"entry1": schedule_coordinator}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    # Should still call add_entities with schedule switches
    entities = add_entities.call_args[0][0]
    assert len(entities) > 0

    entities = add_entities.call_args[0][0]
    assert len([e for e in entities if isinstance(e, FroniusScheduleSwitch)]) == len(
        SCHEDULE_SWITCH_DESCRIPTIONS
    )


@pytest.mark.asyncio
async def test_async_setup_entry_with_batteries_coordinator(
    schedule_coordinator, batteries_coordinator
) -> None:
    """Test setup when both coordinators are present."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")
    # Both coordinators present
    hass.data = {
        DOMAIN: {
            "entry1": schedule_coordinator,
            "batteries_coordinator": {"entry1": batteries_coordinator},
        }
    }
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    # Should have both schedule and battery switches
    schedule_switches = [e for e in entities if isinstance(e, FroniusScheduleSwitch)]
    battery_switches = [e for e in entities if isinstance(e, FroniusBatterySwitch)]

    assert len(schedule_switches) == len(SCHEDULE_SWITCH_DESCRIPTIONS)
    # Should have created battery switches for keys present in coordinator data
    assert len(battery_switches) > 0


@pytest.mark.asyncio
async def test_async_setup_entry_battery_only(batteries_coordinator) -> None:
    """Test setup with only batteries coordinator (no TDC coordinator)."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    # No schedule coordinator, only batteries
    hass.data = {DOMAIN: {"batteries_coordinator": {"entry1": batteries_coordinator}}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    # Should have only battery switches
    battery_switches = [e for e in entities if isinstance(e, FroniusBatterySwitch)]
    assert len(battery_switches) > 0


def test_schedule_switch_name(schedule_coordinator) -> None:
    """Test that FroniusScheduleSwitch name property formats correctly."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)
    name = switch.name
    assert "Charge Max" in name
    assert "3000W" in name
    assert "22:00-06:00" in name


def test_schedule_switch_weekday_name(schedule_coordinator) -> None:
    """Test that weekday switch name is just the weekday."""
    entry = MagicMock(entry_id="entry1")
    weekday_desc = next(
        desc for desc in SCHEDULE_SWITCH_DESCRIPTIONS if desc.weekday == "Mon"
    )
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", weekday_desc)
    assert switch.name == "Mon"


def test_schedule_switch_icon(schedule_coordinator) -> None:
    """Test that FroniusScheduleSwitch icon changes based on schedule type."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]

    # Test CHARGE_MAX
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)
    assert switch.icon == "mdi:battery-arrow-up"

    # Test CHARGE_MIN
    schedule_coordinator.data[0]["ScheduleType"] = "CHARGE_MIN"
    assert switch.icon == "mdi:battery-plus-outline"

    # Test DISCHARGE_MAX
    schedule_coordinator.data[0]["ScheduleType"] = "DISCHARGE_MAX"
    assert switch.icon == "mdi:battery-arrow-down"

    # Test DISCHARGE_MIN
    schedule_coordinator.data[0]["ScheduleType"] = "DISCHARGE_MIN"
    assert switch.icon == "mdi:battery-minus-outline"

    # Test unknown type
    schedule_coordinator.data[0]["ScheduleType"] = "UNKNOWN"
    assert switch.icon == "mdi:battery-clock"


def test_schedule_switch_schedule_property_error(schedule_coordinator) -> None:
    """Test that _schedule property handles ValueError from resolve_rule_index."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)

    # Make resolve_rule_index raise ValueError
    schedule_coordinator.resolve_rule_index = MagicMock(
        side_effect=ValueError("Not found")
    )

    # Should return empty dict instead of crashing
    assert switch._schedule == {}
    # name should handle empty schedule gracefully
    assert switch.name is not None


def test_schedule_switch_weekday_icon(schedule_coordinator) -> None:
    """Test that weekday switch has calendar icon."""
    entry = MagicMock(entry_id="entry1")
    weekday_desc = next(
        desc for desc in SCHEDULE_SWITCH_DESCRIPTIONS if desc.weekday == "Mon"
    )
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", weekday_desc)
    assert switch.icon == "mdi:calendar-week"


def test_schedule_switch_is_on_false(schedule_coordinator) -> None:
    """Test that FroniusScheduleSwitch is_on returns False when Active is False."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]
    schedule_coordinator.data[0]["Active"] = False
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)
    assert switch.is_on is False


def test_schedule_switch_weekday_is_on_false(schedule_coordinator) -> None:
    """Test that weekday switch is_on returns False when weekday is disabled."""
    entry = MagicMock(entry_id="entry1")
    weekday_desc = next(
        desc for desc in SCHEDULE_SWITCH_DESCRIPTIONS if desc.weekday == "Sat"
    )
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", weekday_desc)
    assert switch.is_on is False


@pytest.mark.asyncio
async def test_schedule_switch_async_turn_on_active(schedule_coordinator) -> None:
    """Test that async_turn_on calls async_set_active for active switch."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)

    schedule_coordinator.async_set_active = AsyncMock()
    await switch.async_turn_on()
    schedule_coordinator.async_set_active.assert_called_once_with("1", active=True)


@pytest.mark.asyncio
async def test_schedule_switch_async_turn_off_active(schedule_coordinator) -> None:
    """Test that async_turn_off calls async_set_active for active switch."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)

    schedule_coordinator.async_set_active = AsyncMock()
    await switch.async_turn_off()
    schedule_coordinator.async_set_active.assert_called_once_with(
        index_or_rule_id="1", active=False
    )


@pytest.mark.asyncio
async def test_schedule_switch_async_turn_off_weekday(schedule_coordinator) -> None:
    """Test that async_turn_off calls async_set_weekday for weekday switch."""
    entry = MagicMock(entry_id="entry1")
    weekday_desc = next(
        desc for desc in SCHEDULE_SWITCH_DESCRIPTIONS if desc.weekday == "Sun"
    )
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", weekday_desc)

    schedule_coordinator.async_set_weekday = AsyncMock()
    await switch.async_turn_off()
    schedule_coordinator.async_set_weekday.assert_called_once_with(
        "1", "Sun", enabled=False
    )


def test_schedule_switch_schedule_property_index_out_of_range(
    schedule_coordinator,
) -> None:
    """Test _schedule property when resolve_rule_index returns index >= len(data)."""
    entry = MagicMock(entry_id="entry1")
    active_desc = SCHEDULE_SWITCH_DESCRIPTIONS[0]
    switch = FroniusScheduleSwitch(schedule_coordinator, entry, "1", active_desc)

    # Make resolve_rule_index return an index that's out of range
    schedule_coordinator.resolve_rule_index = MagicMock(return_value=5)
    # Data only has 1 element, so index 5 is out of range

    # Should return empty dict when idx >= len(data)
    assert switch._schedule == {}
    # Accessing name should not crash
    name = switch.name
    assert name is not None


def test_battery_switch_name_with_label(batteries_coordinator) -> None:
    """Test battery switch name uses label from BATTERY_CONFIG_LABELS."""
    entry = MagicMock(entry_id="entry1")
    # HYB_EVU_CHARGEFROMGRID has a label defined
    switch = FroniusBatterySwitch(
        batteries_coordinator, entry, "HYB_EVU_CHARGEFROMGRID"
    )
    name = switch.name
    # Should use the label from BATTERY_CONFIG_LABELS
    assert "Charge From Grid" in name or "charge" in name.lower()


def test_battery_switch_name_without_label(batteries_coordinator) -> None:
    """Test battery switch name falls back to formatted key when no label exists."""
    entry = MagicMock(entry_id="entry1")
    batteries_coordinator.data = {"UNKNOWN_SWITCH_KEY": True}
    # Key without a defined label
    switch = FroniusBatterySwitch(batteries_coordinator, entry, "UNKNOWN_SWITCH_KEY")
    name = switch.name
    # Should format key as title case with spaces
    assert "Unknown" in name
    assert "Switch" in name
    assert "Key" in name


def test_battery_switch_is_on_true(batteries_coordinator) -> None:
    """Test battery switch is_on property returns True when value is True."""
    entry = MagicMock(entry_id="entry1")
    switch = FroniusBatterySwitch(
        batteries_coordinator, entry, "HYB_EVU_CHARGEFROMGRID"
    )
    # HYB_EVU_CHARGEFROMGRID is set to True in fixture
    assert switch.is_on is True


def test_battery_switch_is_on_false(batteries_coordinator) -> None:
    """Test battery switch is_on property returns False when value is False."""
    entry = MagicMock(entry_id="entry1")
    switch = FroniusBatterySwitch(batteries_coordinator, entry, "HYB_BM_CHARGEFROMAC")
    # HYB_BM_CHARGEFROMAC is set to False in fixture
    assert switch.is_on is False


@pytest.mark.asyncio
async def test_battery_switch_async_turn_on(batteries_coordinator) -> None:
    """Test battery switch async_turn_on calls coordinator method."""
    entry = MagicMock(entry_id="entry1")
    switch = FroniusBatterySwitch(
        batteries_coordinator, entry, "HYB_EVU_CHARGEFROMGRID"
    )

    batteries_coordinator.async_set_switch = AsyncMock()
    await switch.async_turn_on()
    batteries_coordinator.async_set_switch.assert_called_once_with(
        "HYB_EVU_CHARGEFROMGRID", value=True
    )


@pytest.mark.asyncio
async def test_battery_switch_async_turn_off(batteries_coordinator) -> None:
    """Test battery switch async_turn_off calls coordinator method."""
    entry = MagicMock(entry_id="entry1")
    switch = FroniusBatterySwitch(
        batteries_coordinator, entry, "HYB_EVU_CHARGEFROMGRID"
    )

    batteries_coordinator.async_set_switch = AsyncMock()
    await switch.async_turn_off()
    batteries_coordinator.async_set_switch.assert_called_once_with(
        "HYB_EVU_CHARGEFROMGRID", value=False
    )
