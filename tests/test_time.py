"""Tests for time entities."""

# ruff: noqa: D103

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import DOMAIN
from custom_components.fronius_tdc.time import FroniusScheduleTime, async_setup_entry


@pytest.mark.asyncio
async def test_schedule_time_setters() -> None:
    coordinator = MagicMock()
    coordinator.data = [
        {"rule_id": "1", "TimeTable": {"Start": "00:00", "End": "23:59"}}
    ]
    coordinator.resolve_rule_index = MagicMock(return_value=0)
    coordinator.async_set_start_time = AsyncMock()
    coordinator.async_set_end_time = AsyncMock()

    entry = MagicMock(entry_id="entry1")
    start_entity = FroniusScheduleTime(
        coordinator,
        entry,
        "1",
        MagicMock(key="start", name="Start Time", timetable_field="Start"),
    )
    end_entity = FroniusScheduleTime(
        coordinator,
        entry,
        "1",
        MagicMock(key="end", name="End Time", timetable_field="End"),
    )

    await start_entity.async_set_value(time(hour=0, minute=0))
    await end_entity.async_set_value(time(hour=23, minute=59))

    coordinator.async_set_start_time.assert_called_once_with("1", "00:00")
    coordinator.async_set_end_time.assert_called_once_with("1", "23:59")


@pytest.mark.asyncio
async def test_async_setup_entry_creates_time_entities() -> None:
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    coordinator = MagicMock()
    coordinator.get_rule_ids = MagicMock(return_value=["1"])
    coordinator.async_config_entry_first_refresh = AsyncMock()

    hass.data = {DOMAIN: {"entry1": coordinator}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    entities = add_entities.call_args[0][0]
    assert len(entities) == 2


@pytest.mark.asyncio
async def test_async_setup_entry_without_coordinator() -> None:
    """Test setup when coordinator is missing."""
    hass = MagicMock()
    entry = MagicMock(entry_id="entry1")

    # No coordinator
    hass.data = {DOMAIN: {}}
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    # Should call add_entities with empty list
    entities = add_entities.call_args[0][0]
    assert len(entities) == 0
