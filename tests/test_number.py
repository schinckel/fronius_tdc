"""Tests for number entities."""

# ruff: noqa: D103

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN
from custom_components.fronius_tdc.number import (
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
