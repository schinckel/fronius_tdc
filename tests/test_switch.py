"""Tests for switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN, SCHEDULE_SWITCH_DESCRIPTIONS
from custom_components.fronius_tdc.switch import (
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

    entities = add_entities.call_args[0][0]
    assert len([e for e in entities if isinstance(e, FroniusScheduleSwitch)]) == len(
        SCHEDULE_SWITCH_DESCRIPTIONS
    )
