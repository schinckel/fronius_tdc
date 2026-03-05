"""
Custom integration to integrate Fronius Gen24 TDC with Home Assistant.

For more details about this integration, please refer to
https://github.com/schinckel/fronius_tdc
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .batteries_coordinator import FroniusBatteriesCoordinator
from .const import DOMAIN, LOGGER
from .tdc_coordinator import FroniusTDCCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})

    # Set up TOU coordinator
    tdc_coordinator = FroniusTDCCoordinator(
        hass=hass,
        logger=LOGGER,
        config_entry=entry,
    )
    hass.data[DOMAIN][entry.entry_id] = tdc_coordinator

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await tdc_coordinator.async_config_entry_first_refresh()

    # Set up Batteries coordinator
    batteries_coordinator = FroniusBatteriesCoordinator(
        hass=hass,
        logger=LOGGER,
        config_entry=entry,
    )
    hass.data[DOMAIN].setdefault("batteries_coordinator", {})[entry.entry_id] = (
        batteries_coordinator
    )
    await batteries_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
