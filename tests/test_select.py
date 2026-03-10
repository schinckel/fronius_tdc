"""Tests for select entities."""

# ruff: noqa: D103

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN
from custom_components.fronius_tdc.select import (
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
