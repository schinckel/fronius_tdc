"""Tests for number entities."""

# ruff: noqa: D103

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN
from custom_components.fronius_tdc.number import (
    FroniusBatteryNumber,
    FroniusScheduleNumber,
    async_setup_entry,
)


@pytest.mark.asyncio
async def test_schedule_number_setter() -> None:
    coordinator = MagicMock()
    coordinator.data = [{"rule_id": "1", "Power": 3000}]
    coordinator.resolve_rule_index = MagicMock(return_value=0)
    coordinator.async_set_power = AsyncMock()
    entry = MagicMock(entry_id="entry1")

    entity = FroniusScheduleNumber(
        coordinator,
        entry,
        "1",
        MagicMock(key="power", name="Power", min_value=0, max_value=20000, step=100),
    )
    await entity.async_set_native_value(3500)
    coordinator.async_set_power.assert_called_once_with("1", 3500)


@pytest.mark.asyncio
async def test_async_setup_entry_includes_schedule_numbers() -> None:
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
    assert any(isinstance(entity, FroniusScheduleNumber) for entity in entities)


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

    # Should still call add_entities with schedule numbers only
    entities = add_entities.call_args[0][0]
    assert all(isinstance(entity, FroniusScheduleNumber) for entity in entities)


@pytest.mark.asyncio
async def test_async_setup_entry_with_battery_numbers() -> None:
    """Test setup when batteries coordinator has numeric keys."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    tdc = MagicMock()
    tdc.get_rule_ids = MagicMock(return_value=["1"])
    tdc.async_config_entry_first_refresh = AsyncMock()

    batteries = MagicMock()
    # Add numeric keys that should create battery number entities
    batteries.data = {
        "HYB_EM_POWER": 5000,
        "HYB_BM_PACMIN": 4000,
    }
    batteries.async_config_entry_first_refresh = AsyncMock()

    hass.data = {
        DOMAIN: {"entry1": tdc, "batteries_coordinator": {"entry1": batteries}}
    }
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    # Should have both schedule and battery numbers
    schedule_numbers = [e for e in entities if isinstance(e, FroniusScheduleNumber)]
    battery_numbers = [e for e in entities if isinstance(e, FroniusBatteryNumber)]

    assert len(schedule_numbers) > 0
    assert len(battery_numbers) > 0


@pytest.mark.asyncio
async def test_async_setup_entry_battery_only() -> None:
    """Test setup with only batteries coordinator (no TDC coordinator)."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    batteries = MagicMock()
    batteries.data = {
        "HYB_EM_POWER": 5000,
        "HYB_BM_PACMIN": 4000,
    }
    batteries.async_config_entry_first_refresh = AsyncMock()

    # No tdc coordinator, only batteries
    hass.data = {DOMAIN: {"batteries_coordinator": {"entry1": batteries}}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    # Should have only battery numbers
    battery_numbers = [e for e in entities if isinstance(e, FroniusBatteryNumber)]
    assert len(battery_numbers) > 0


def test_schedule_number_name() -> None:
    """Test schedule number name property returns description label."""
    coordinator = MagicMock()
    coordinator.data = [{"rule_id": "1", "Power": 3000}]
    coordinator.resolve_rule_index = MagicMock(return_value=0)
    entry = MagicMock(entry_id="entry1")

    description = SimpleNamespace(
        key="power",
        name="Power Label",
        min_value=0,
        max_value=20000,
        step=100,
    )
    entity = FroniusScheduleNumber(coordinator, entry, "1", description)

    assert entity.name == "Power Label"
