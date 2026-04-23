"""Switch entities: Time of Use schedules and battery configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .batteries_coordinator import FroniusBatteriesCoordinator
from .const import (
    BATTERY_CONFIG_KEYS,
    BATTERY_CONFIG_LABELS,
    DOMAIN,
    SCHEDULE_TYPE_LABELS,
)
from .tdc_coordinator import FroniusTDCCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for one config entry."""
    entities: list[SwitchEntity] = []

    # Set up TOU schedule switches
    domain_data = hass.data[DOMAIN]
    tdc_coordinator = domain_data.get(entry.entry_id)

    if tdc_coordinator:
        await tdc_coordinator.async_config_entry_first_refresh()
        entities.extend([
            FroniusScheduleSwitch(tdc_coordinator, entry, index)
            for index in range(len(tdc_coordinator.data or []))
        ])

    # Set up Battery configuration switches (booleans only)
    batteries_coordinator = domain_data.get("batteries_coordinator", {}).get(
        entry.entry_id
    )
    if batteries_coordinator:
        await batteries_coordinator.async_config_entry_first_refresh()
        _LOGGER.debug(
            "Battery coordinator data available: %s", batteries_coordinator.data
        )

        # Find all boolean keys for switches
        boolean_keys = [
            key
            for key, platform_type in BATTERY_CONFIG_KEYS.items()
            if platform_type == "switch"
        ]
        battery_switches = [
            FroniusBatterySwitch(batteries_coordinator, entry, key)
            for key in boolean_keys
            if key in (batteries_coordinator.data or {})
        ]
        _LOGGER.debug(
            "Creating %d battery switch entities: %s",
            len(battery_switches),
            [e.name for e in battery_switches],
        )
        entities.extend(battery_switches)
    else:
        _LOGGER.warning("No batteries coordinator found for entry %s", entry.entry_id)

    async_add_entities(entities)


class FroniusScheduleSwitch(CoordinatorEntity[FroniusTDCCoordinator], SwitchEntity):
    """Switch that activates/deactivates one Time of Use schedule."""

    def __init__(
        self,
        coordinator: FroniusTDCCoordinator,
        entry: ConfigEntry,
        index: int,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._index = index
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_schedule_{index}"
        entry_title = entry.title if isinstance(entry.title, str) else ""
        base_name = slugify(entry_title) or "fronius_tdc"
        self.entity_id = f"switch.{base_name}_schedule_{index}_active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Time of Use",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

    @property
    def _schedule(self) -> dict:
        data = self.coordinator.data or []
        if self._index < len(data):
            return data[self._index]
        return {}

    @property
    def name(self) -> str:
        """
        Generate a human-friendly name.

        Like "Charge Max 3000W 22:00-06:00"
        Based on the schedule parameters.
        """
        s = self._schedule
        stype = SCHEDULE_TYPE_LABELS.get(
            s.get("ScheduleType", ""),
            s.get("ScheduleType", ""),
        )
        power = s.get("Power", 0)
        tt = s.get("TimeTable", {})
        start = tt.get("Start", "?")
        end = tt.get("End", "?")
        return f"{stype} {power}W {start}-{end}"

    @property
    def icon(self) -> str:
        """
        Return an icon representing the schedule type.

        The icon changes based on the `ScheduleType` value from the
        underlying schedule data so that different modes (charge/discharge,
        max/min) have appropriate battery-style icons.
        """
        s = self._schedule
        stype = s.get("ScheduleType", "")
        if stype == "CHARGE_MAX":
            return "mdi:battery-arrow-up"
        if stype == "CHARGE_MIN":
            return "mdi:battery-plus-outline"
        if stype == "DISCHARGE_MAX":
            return "mdi:battery-arrow-down"
        if stype == "DISCHARGE_MIN":
            return "mdi:battery-minus-outline"
        return "mdi:battery-clock"

    @property
    def is_on(self) -> bool:
        """Return True if the schedule is active, False otherwise."""
        return bool(self._schedule.get("Active", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for the schedule, like days of week."""
        s = self._schedule
        tt = s.get("TimeTable", {})
        weekdays = s.get("Weekdays", {})
        active_days = [day for day, on in weekdays.items() if on is True]
        return {
            "schedule_type": s.get("ScheduleType"),
            "power_w": s.get("Power"),
            "start": tt.get("Start"),
            "end": tt.get("End"),
            "days": sorted(active_days),
        }

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the schedule by setting its Active flag to True."""
        await self.coordinator.async_set_active(self._index, active=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the schedule by setting its Active flag to False."""
        # pass both parameters as keywords; the boolean must not be positional
        await self.coordinator.async_set_active(index=self._index, active=False)


class FroniusBatterySwitch(
    CoordinatorEntity[FroniusBatteriesCoordinator], SwitchEntity
):
    """Switch for a boolean battery configuration setting."""

    def __init__(
        self,
        coordinator: FroniusBatteriesCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the battery switch entity."""
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_battery_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Battery",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

    @property
    def name(self) -> str:
        """Return a human-friendly name for this battery switch."""
        label_info = BATTERY_CONFIG_LABELS.get(self._key, {})
        return label_info.get("name", self._key.replace("_", " ").title())

    @property
    def is_on(self) -> bool:
        """Return True if the battery config key is True, False otherwise."""
        return bool((self.coordinator.data or {}).get(self._key, False))

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the battery switch."""
        await self.coordinator.async_set_switch(self._key, value=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the battery switch."""
        await self.coordinator.async_set_switch(self._key, value=False)
