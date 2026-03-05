"""Switch entities: one per Time of Use schedule entry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCHEDULE_TYPE_LABELS
from .tdc_coordinator import FroniusTDCCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for one config entry."""
    coordinator: FroniusTDCCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for first data fetch so we know how many schedules exist
    await coordinator.async_config_entry_first_refresh()

    entities = [
        FroniusScheduleSwitch(coordinator, entry, index)
        for index in range(len(coordinator.data or []))
    ]
    await async_add_entities(entities)


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
