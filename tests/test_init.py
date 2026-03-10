"""Tests for integration lifecycle and services."""

# ruff: noqa: D103

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.fronius_tdc import async_setup_entry, async_unload_entry
from custom_components.fronius_tdc.const import (
    DOMAIN,
    SERVICE_ADD_SCHEDULE,
    SERVICE_REMOVE_SCHEDULE,
)


@pytest.mark.asyncio
@patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
@patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
async def test_setup_registers_services(mock_tdc_cls, mock_batteries_cls) -> None:
    tdc = AsyncMock()
    tdc.async_config_entry_first_refresh = AsyncMock()
    mock_tdc_cls.return_value = tdc

    batteries = AsyncMock()
    batteries.async_config_entry_first_refresh = AsyncMock()
    mock_batteries_cls.return_value = batteries

    hass = AsyncMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()

    entry = MagicMock(entry_id="entry1")
    entry.async_on_unload = MagicMock(return_value=AsyncMock())
    entry.add_update_listener = MagicMock()

    assert await async_setup_entry(hass, entry)

    assert DOMAIN in hass.data
    registered = [call.args[1] for call in hass.services.async_register.call_args_list]
    assert SERVICE_ADD_SCHEDULE in registered
    assert SERVICE_REMOVE_SCHEDULE in registered


@pytest.mark.asyncio
async def test_unload_removes_services() -> None:
    hass = AsyncMock()
    hass.data = {
        DOMAIN: {
            "entry1": MagicMock(),
            "services_registered": True,
            "batteries_coordinator": {"entry1": MagicMock()},
        }
    }
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_remove = MagicMock()

    entry = MagicMock(entry_id="entry1")

    assert await async_unload_entry(hass, entry)
    removed = [call.args[1] for call in hass.services.async_remove.call_args_list]
    assert SERVICE_ADD_SCHEDULE in removed
    assert SERVICE_REMOVE_SCHEDULE in removed
