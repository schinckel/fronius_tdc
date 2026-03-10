"""Tests for select entities."""

# ruff: noqa: D103

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN
from custom_components.fronius_tdc.select import (
    FroniusBatterySelect,
    FroniusScheduleSelect,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_schedule_select_setter() -> None:
    coordinator = MagicMock()
    coordinator.data = [{"rule_id": "1", "ScheduleType": "CHARGE_MAX"}]
    coordinator.resolve_rule_index = MagicMock(return_value=0)
    coordinator.async_set_schedule_type = AsyncMock()
    entry = MagicMock(entry_id="entry1")

    entity = FroniusScheduleSelect(
        coordinator,
        entry,
        "1",
        MagicMock(
            key="schedule_type",
            name="Type",
            options=("CHARGE_MAX", "CHARGE_MIN", "DISCHARGE_MAX", "DISCHARGE_MIN"),
        ),
    )
    await entity.async_select_option("Charge Min")
    coordinator.async_set_schedule_type.assert_called_once_with("1", "CHARGE_MIN")


@pytest.mark.asyncio
async def test_schedule_select_current_option_value_error() -> None:
    """Test current_option returns None when resolve_rule_index raises ValueError."""
    coordinator = MagicMock()
    coordinator.data = [{"rule_id": "1", "ScheduleType": "CHARGE_MAX"}]
    # Make resolve_rule_index raise ValueError
    coordinator.resolve_rule_index = MagicMock(side_effect=ValueError("Invalid rule"))
    entry = MagicMock(entry_id="entry1")

    entity = FroniusScheduleSelect(
        coordinator,
        entry,
        "1",
        MagicMock(
            key="schedule_type",
            name="Type",
            options=("CHARGE_MAX", "CHARGE_MIN", "DISCHARGE_MAX", "DISCHARGE_MIN"),
        ),
    )
    # Should return None when ValueError occurs
    assert entity.current_option is None


@pytest.mark.asyncio
async def test_schedule_select_async_select_option_invalid() -> None:
    """Test schedule select async_select_option raises ValueError for invalid option."""
    coordinator = MagicMock()
    coordinator.data = [{"rule_id": "1", "ScheduleType": "CHARGE_MAX"}]
    coordinator.resolve_rule_index = MagicMock(return_value=0)
    coordinator.async_set_schedule_type = AsyncMock()
    entry = MagicMock(entry_id="entry1")

    entity = FroniusScheduleSelect(
        coordinator,
        entry,
        "1",
        MagicMock(
            key="schedule_type",
            name="Type",
            options=("CHARGE_MAX", "CHARGE_MIN", "DISCHARGE_MAX", "DISCHARGE_MIN"),
        ),
    )

    # Try to select an invalid option that's not in _label_to_value mapping
    with pytest.raises(ValueError, match="Invalid schedule type option"):
        await entity.async_select_option("INVALID_OPTION")


@pytest.mark.asyncio
async def test_async_setup_entry_includes_schedule_selects() -> None:
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    tdc = MagicMock()
    tdc.get_rule_ids = MagicMock(return_value=["1"])
    tdc.async_config_entry_first_refresh = AsyncMock()

    batteries = MagicMock()
    batteries.data = {}
    batteries.async_config_entry_first_refresh = AsyncMock()

    hass.data = {
        DOMAIN: {"entry1": tdc, "batteries_coordinator": {"entry1": batteries}}
    }
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    assert any(isinstance(entity, FroniusScheduleSelect) for entity in entities)


@pytest.mark.asyncio
async def test_async_setup_entry_without_batteries_coordinator() -> None:
    """Test setup when batteries coordinator is missing."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    tdc = MagicMock()
    tdc.get_rule_ids = MagicMock(return_value=["1"])
    tdc.async_config_entry_first_refresh = AsyncMock()

    # No batteries coordinator
    hass.data = {DOMAIN: {"entry1": tdc}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    # Should still call add_entities with schedule selects only
    entities = add_entities.call_args[0][0]
    assert all(isinstance(entity, FroniusScheduleSelect) for entity in entities)


@pytest.mark.asyncio
async def test_async_setup_entry_with_battery_selects() -> None:
    """Test setup when batteries coordinator has select keys."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    tdc = MagicMock()
    tdc.get_rule_ids = MagicMock(return_value=["1"])
    tdc.async_config_entry_first_refresh = AsyncMock()

    batteries = MagicMock()
    # Add select keys that should create battery select entities
    batteries.data = {
        "HYB_EM_MODE": "charge",
        "BAT_M0_SOC_MODE": "active",
    }
    batteries.async_config_entry_first_refresh = AsyncMock()

    hass.data = {
        DOMAIN: {"entry1": tdc, "batteries_coordinator": {"entry1": batteries}}
    }
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    # Should have both schedule and battery selects
    schedule_selects = [e for e in entities if isinstance(e, FroniusScheduleSelect)]
    battery_selects = [e for e in entities if isinstance(e, FroniusBatterySelect)]

    assert len(schedule_selects) > 0
    assert len(battery_selects) > 0


@pytest.mark.asyncio
async def test_async_setup_entry_battery_only() -> None:
    """Test setup with only batteries coordinator (no TDC coordinator)."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    batteries = MagicMock()
    batteries.data = {
        "HYB_EM_MODE": "charge",
        "BAT_M0_SOC_MODE": "active",
    }
    batteries.async_config_entry_first_refresh = AsyncMock()

    # No tdc coordinator, only batteries
    hass.data = {DOMAIN: {"batteries_coordinator": {"entry1": batteries}}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    # Should have only battery selects
    battery_selects = [e for e in entities if isinstance(e, FroniusBatterySelect)]
    assert len(battery_selects) > 0


def test_schedule_select_name() -> None:
    """Test schedule select name property returns description label."""
    coordinator = MagicMock()
    coordinator.data = [{"rule_id": "1", "ScheduleType": "CHARGE_MAX"}]
    coordinator.resolve_rule_index = MagicMock(return_value=0)
    entry = MagicMock(entry_id="entry1")

    description = SimpleNamespace(
        key="schedule_type",
        name="Schedule Type Label",
        options=("CHARGE_MAX", "CHARGE_MIN", "DISCHARGE_MAX", "DISCHARGE_MIN"),
    )
    entity = FroniusScheduleSelect(coordinator, entry, "1", description)

    assert entity.name == "Schedule Type Label"
