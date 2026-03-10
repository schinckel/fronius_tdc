"""Time entities for TOU schedule start/end editing."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, cast

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCHEDULE_TIME_DESCRIPTIONS, ScheduleTimeDescription
from .tdc_coordinator import FroniusTDCCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up schedule time entities."""
    coordinator: FroniusTDCCoordinator | None = hass.data[DOMAIN].get(entry.entry_id)
    if not coordinator:
        async_add_entities([])
        return

    await coordinator.async_config_entry_first_refresh()
    entities: list[FroniusScheduleTime] = []
    for rule_id in coordinator.get_rule_ids():
        entities.extend(
            [
                FroniusScheduleTime(coordinator, entry, rule_id, description)
                for description in SCHEDULE_TIME_DESCRIPTIONS
            ]
        )

    async_add_entities(entities)


class FroniusScheduleTime(CoordinatorEntity[FroniusTDCCoordinator], TimeEntity):
    """Time entity for one schedule start/end field."""

    entity_description: ScheduleTimeDescription

    def __init__(
        self,
        coordinator: FroniusTDCCoordinator,
        entry: ConfigEntry,
        rule_id: str,
        description: ScheduleTimeDescription,
    ) -> None:
        """Initialize the schedule time entity."""
        super().__init__(coordinator)
        self._rule_id = rule_id
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_schedule_{rule_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Time of Use",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

    @property
    def name(self) -> str:
        """Return display name."""
        return cast("str", self.entity_description.name)

    @property
    def native_value(self) -> time | None:
        """Return current time value."""
        try:
            idx = self.coordinator.resolve_rule_index(self._rule_id)
        except ValueError:
            return None

        value = (
            (self.coordinator.data or [])[idx]
            .get("TimeTable", {})
            .get(self.entity_description.timetable_field)
        )
        if not isinstance(value, str) or ":" not in value:
            return None
        hour, minute = value.split(":", 1)
        return time(hour=int(hour), minute=int(minute))

    async def async_set_value(self, value: time) -> None:
        """Set time value."""
        hhmm = f"{value.hour:02d}:{value.minute:02d}"
        if self.entity_description.timetable_field == "Start":
            await self.coordinator.async_set_start_time(self._rule_id, hhmm)
        else:
            await self.coordinator.async_set_end_time(self._rule_id, hhmm)
