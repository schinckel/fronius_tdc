"""
Custom integration to integrate Fronius Gen24 TDC with Home Assistant.

For more details about this integration, please refer to
https://github.com/schinckel/fronius_tdc
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .batteries_coordinator import FroniusBatteriesCoordinator
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    LOGGER,
    SCHEDULE_TYPE_LABELS,
    SERVICE_ADD_SCHEDULE,
    SERVICE_REMOVE_SCHEDULE,
)
from .tdc_coordinator import WEEKDAY_KEYS, FroniusTDCCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]
SERVICE_STATE_KEY = "services_registered"
BATTERIES_COORDINATOR_KEY = "batteries_coordinator"

ADD_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("schedule_type"): vol.In(list(SCHEDULE_TYPE_LABELS)),
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
        vol.Required("weekdays"): vol.All(
            cv.ensure_list,
            [vol.In(list(WEEKDAY_KEYS))],
        ),
        vol.Optional("active", default=False): cv.boolean,
        vol.Optional("power", default=0): vol.Coerce(int),
    }
)

REMOVE_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("index"): vol.Coerce(int),
    }
)


def _get_tdc_coordinators(hass: HomeAssistant) -> dict[str, FroniusTDCCoordinator]:
    """Return configured TOU coordinators keyed by config entry ID."""
    domain_data = hass.data.get(DOMAIN, {})
    return {
        entry_id: coordinator
        for entry_id, coordinator in domain_data.items()
        if entry_id not in {BATTERIES_COORDINATOR_KEY, SERVICE_STATE_KEY}
    }


def _resolve_service_target(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[ConfigEntry, FroniusTDCCoordinator]:
    """Resolve the config entry and coordinator for a service call."""
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    coordinators = _get_tdc_coordinators(hass)

    if entry_id is None:
        if not coordinators:
            msg = "No configured Fronius Time of Use entries are available"
            raise ServiceValidationError(msg)
        if len(coordinators) > 1:
            msg = "config_entry_id is required when multiple Fronius entries exist"
            raise ServiceValidationError(msg)
        entry_id = next(iter(coordinators))

    coordinator = coordinators.get(entry_id)
    if coordinator is None:
        msg = f"Unknown config_entry_id: {entry_id}"
        raise ServiceValidationError(msg)

    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        msg = f"Config entry not found: {entry_id}"
        raise ServiceValidationError(msg)

    return entry, coordinator


def _build_schedule_from_service(call: ServiceCall) -> dict[str, Any]:
    """Build one canonical schedule dict from a validated service call."""
    selected_weekdays = set(call.data["weekdays"])
    return {
        "Active": call.data["active"],
        "ScheduleType": call.data["schedule_type"],
        "Power": call.data["power"],
        "TimeTable": {
            "Start": call.data["start"],
            "End": call.data["end"],
        },
        "Weekdays": {day: day in selected_weekdays for day in WEEKDAY_KEYS},
    }


async def _async_handle_add_schedule(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the add_schedule service."""
    entry, coordinator = _resolve_service_target(hass, call)
    try:
        await coordinator.async_add_schedule(_build_schedule_from_service(call))
    except Exception as err:
        message = str(err)
        if message.startswith("Invalid schedule"):
            raise ServiceValidationError(message) from err
        if isinstance(err, HomeAssistantError):
            raise
        raise HomeAssistantError(message) from err

    await hass.config_entries.async_reload(entry.entry_id)


async def _async_handle_remove_schedule(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the remove_schedule service."""
    entry, coordinator = _resolve_service_target(hass, call)
    try:
        await coordinator.async_remove_schedule(call.data["index"])
    except Exception as err:
        message = str(err)
        if message.startswith("Invalid schedule") or "out of range" in message:
            raise ServiceValidationError(message) from err
        if isinstance(err, HomeAssistantError):
            raise
        raise HomeAssistantError(message) from err

    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once per Home Assistant instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(SERVICE_STATE_KEY):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_SCHEDULE,
        lambda call: _async_handle_add_schedule(hass, call),
        schema=ADD_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_SCHEDULE,
        lambda call: _async_handle_remove_schedule(hass, call),
        schema=REMOVE_SCHEDULE_SCHEMA,
    )
    domain_data[SERVICE_STATE_KEY] = True


def _async_unregister_services_if_unused(hass: HomeAssistant) -> None:
    """Remove domain services when the last config entry is unloaded."""
    domain_data = hass.data.get(DOMAIN, {})
    if _get_tdc_coordinators(hass):
        return
    if not domain_data.get(SERVICE_STATE_KEY):
        return

    hass.services.async_remove(DOMAIN, SERVICE_ADD_SCHEDULE)
    hass.services.async_remove(DOMAIN, SERVICE_REMOVE_SCHEDULE)
    domain_data.pop(SERVICE_STATE_KEY, None)


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
    _async_register_services(hass)

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await tdc_coordinator.async_config_entry_first_refresh()

    # Set up Batteries coordinator
    batteries_coordinator = FroniusBatteriesCoordinator(
        hass=hass,
        logger=LOGGER,
        config_entry=entry,
    )
    hass.data[DOMAIN].setdefault(BATTERIES_COORDINATOR_KEY, {})[entry.entry_id] = (
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
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)
    domain_data.get(BATTERIES_COORDINATOR_KEY, {}).pop(entry.entry_id, None)
    _async_unregister_services_if_unused(hass)

    if not _get_tdc_coordinators(hass) and not domain_data.get(
        BATTERIES_COORDINATOR_KEY
    ):
        hass.data.pop(DOMAIN, None)

    return True


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
