"""
Custom integration to integrate Fronius Gen24 TDC with Home Assistant.

For more details about this integration, please refer to
https://github.com/schinckel/fronius_tdc
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import Platform

from .batteries_coordinator import FroniusBatteriesCoordinator
from .const import (
    DOMAIN,
    LOGGER,
    SCHEDULE_TYPES,
    SERVICE_ADD_SCHEDULE,
    SERVICE_REMOVE_SCHEDULE,
)
from .tdc_coordinator import FroniusTDCCoordinator, validate_schedule

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TIME,
]

DATA_BATTERIES = "batteries_coordinator"
DATA_SERVICES_REGISTERED = "services_registered"


def _coordinator_items(domain_data: dict[str, Any]) -> dict[str, FroniusTDCCoordinator]:
    """Return only config-entry coordinators."""
    return {
        key: value
        for key, value in domain_data.items()
        if key not in {DATA_BATTERIES, DATA_SERVICES_REGISTERED}
        and isinstance(value, FroniusTDCCoordinator)
    }


def _resolve_coordinator(
    domain_data: dict[str, Any],
    config_entry_id: str | None,
) -> FroniusTDCCoordinator:
    """Resolve target coordinator by explicit entry_id or single configured entry."""
    coordinators = _coordinator_items(domain_data)
    if config_entry_id:
        if config_entry_id not in coordinators:
            msg = f"Unknown config_entry_id: {config_entry_id}"
            raise vol.Invalid(msg)
        return coordinators[config_entry_id]

    if len(coordinators) != 1:
        msg = "config_entry_id is required when multiple entries are configured"
        raise vol.Invalid(msg)

    return next(iter(coordinators.values()))


def _parse_hhmm(value: str | datetime.time) -> str:
    """Normalize service time input to HH:MM."""
    if isinstance(value, datetime.time):
        return f"{value.hour:02d}:{value.minute:02d}"
    if isinstance(value, str):
        return value
    msg = "Invalid time value"
    raise vol.Invalid(msg)


def _add_schedule_schema(data: dict[str, Any]) -> dict[str, Any]:
    weekdays = data.get("weekdays")
    if not isinstance(weekdays, dict):
        msg = "weekdays must be an object"
        raise vol.Invalid(msg)

    schedule = {
        "Active": data["active"],
        "ScheduleType": data["schedule_type"],
        "Power": data["power"],
        "TimeTable": {
            "Start": _parse_hhmm(data["start"]),
            "End": _parse_hhmm(data["end"]),
        },
        "Weekdays": weekdays,
    }
    validate_schedule(schedule)
    return data


ADD_SCHEDULE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional("config_entry_id"): cv.string,
            vol.Required("active"): cv.boolean,
            vol.Required("schedule_type"): vol.In(SCHEDULE_TYPES),
            vol.Required("power"): vol.Coerce(int),
            vol.Required("start"): vol.Any(cv.time, cv.string),
            vol.Required("end"): vol.Any(cv.time, cv.string),
            vol.Required("weekdays"): dict,
        }
    ),
    _add_schedule_schema,
)

REMOVE_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Optional("rule_id"): cv.string,
        vol.Optional("index"): vol.Coerce(int),
    }
)


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services exactly once."""
    if hass.data[DOMAIN].get(DATA_SERVICES_REGISTERED):
        return

    async def async_add_schedule(call: ServiceCall) -> None:
        domain_data = hass.data[DOMAIN]
        coordinator = _resolve_coordinator(
            domain_data, call.data.get("config_entry_id")
        )
        schedule = {
            "Active": call.data["active"],
            "ScheduleType": call.data["schedule_type"],
            "Power": int(call.data["power"]),
            "TimeTable": {
                "Start": _parse_hhmm(call.data["start"]),
                "End": _parse_hhmm(call.data["end"]),
            },
            "Weekdays": call.data["weekdays"],
        }
        await coordinator.async_add_schedule(validate_schedule(schedule))

    async def async_remove_schedule(call: ServiceCall) -> None:
        domain_data = hass.data[DOMAIN]
        coordinator = _resolve_coordinator(
            domain_data, call.data.get("config_entry_id")
        )

        rule_id = call.data.get("rule_id")
        index = call.data.get("index")
        if rule_id is None and index is None:
            msg = "Either rule_id or index is required"
            raise vol.Invalid(msg)

        # At this point, at least one is not None due to the check above
        target: int | str = rule_id if rule_id is not None else int(index)  # type: ignore[arg-type]
        await coordinator.async_remove_schedule(target)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_SCHEDULE,
        async_add_schedule,
        schema=ADD_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_SCHEDULE,
        async_remove_schedule,
        schema=REMOVE_SCHEDULE_SCHEMA,
    )
    hass.data[DOMAIN][DATA_SERVICES_REGISTERED] = True


def _unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services if present."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_SCHEDULE):
        hass.services.async_remove(DOMAIN, SERVICE_ADD_SCHEDULE)
    if hass.services.has_service(DOMAIN, SERVICE_REMOVE_SCHEDULE):
        hass.services.async_remove(DOMAIN, SERVICE_REMOVE_SCHEDULE)


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
    hass.data[DOMAIN].setdefault(DATA_BATTERIES, {})[entry.entry_id] = (
        batteries_coordinator
    )
    await batteries_coordinator.async_config_entry_first_refresh()

    _register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not result:
        return False

    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)

    batteries = domain_data.get(DATA_BATTERIES, {})
    if isinstance(batteries, dict):
        batteries.pop(entry.entry_id, None)

    if not _coordinator_items(domain_data):
        _unregister_services(hass)
        domain_data.pop(DATA_SERVICES_REGISTERED, None)

    return True


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
