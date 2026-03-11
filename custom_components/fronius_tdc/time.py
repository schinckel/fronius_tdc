"""Time entities: editable schedule start/end times."""

from __future__ import annotations

import logging
from datetime import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SCHEDULE_END_TIME_DESCRIPTION,
    SCHEDULE_START_TIME_DESCRIPTION,
    ScheduleTimeEntityDescription,
)
from .tdc_coordinator import FroniusTDCCoordinator

_LOGGER = logging.getLogger(__name__)
HHMM_PARTS = 2
MAX_HOUR = 23
MAX_MINUTE = 59


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up time entities for TOU schedule start/end values."""
    coordinator: FroniusTDCCoordinator | None = hass.data[DOMAIN].get(entry.entry_id)
    if not coordinator:
        _LOGGER.warning(
            "No TOU coordinator found for entry %s, skipping time setup",
            entry.entry_id,
        )
        return

    await coordinator.async_config_entry_first_refresh()

    entities: list[FroniusScheduleTimeEntity] = []
    for index in range(len(coordinator.data or [])):
        entities.append(
            FroniusScheduleTimeEntity(
                coordinator,
                entry,
                index,
                SCHEDULE_START_TIME_DESCRIPTION,
            )
        )
        entities.append(
            FroniusScheduleTimeEntity(
                coordinator,
                entry,
                index,
                SCHEDULE_END_TIME_DESCRIPTION,
            )
        )

    async_add_entities(entities)


class FroniusScheduleTimeEntity(CoordinatorEntity[FroniusTDCCoordinator], TimeEntity):
    """Time entity for one schedule time field."""

    entity_description: ScheduleTimeEntityDescription

    def __init__(
        self,
        coordinator: FroniusTDCCoordinator,
        entry: ConfigEntry,
        index: int,
        description: ScheduleTimeEntityDescription,
    ) -> None:
        """Initialize schedule time entity."""
        super().__init__(coordinator)
        self._index = index
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_schedule_{index}_{description.key}"
        base_name = slugify(entry.title if isinstance(entry.title, str) else "")
        base_name = base_name or "fronius_tdc"
        self.entity_id = f"time.{base_name}_schedule_{index}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Time of Use",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

    @property
    def _schedule(self) -> dict[str, Any]:
        """Return schedule payload for this index."""
        data = self.coordinator.data or []
        if self._index < len(data):
            return data[self._index]
        return {}

    @property
    def name(self) -> str:
        """Return a human-friendly entity name."""
        suffix = "Start" if self.entity_description.key == "start_time" else "End"
        return f"Schedule {self._index + 1} {suffix}"

    @property
    def native_value(self) -> time | None:
        """Return current schedule time as a time object."""
        timetable = self._schedule.get("TimeTable")
        if not isinstance(timetable, dict):
            return None

        raw_value = timetable.get(self.entity_description.value_path[-1])
        if not isinstance(raw_value, str):
            return None

        parts = raw_value.split(":")
        if len(parts) != HHMM_PARTS:
            return None

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
        except ValueError:
            return None

        if not (0 <= hours <= MAX_HOUR and 0 <= minutes <= MAX_MINUTE):
            return None

        return time(hours, minutes)

    async def async_set_value(self, value: time) -> None:
        """Set schedule time; only HH:MM precision is accepted."""
        if value.second != 0 or value.microsecond != 0:
            msg = "Time must use HH:MM precision"
            raise ValueError(msg)

        hhmm = f"{value.hour:02d}:{value.minute:02d}"
        setter = getattr(self.coordinator, self.entity_description.setter_name)
        await setter(
            index=self._index,
            **{self.entity_description.setter_value_parameter: hhmm},
        )
