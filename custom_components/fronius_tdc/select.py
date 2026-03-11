"""Select entities: enum battery configuration settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
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
    BATTERY_SELECT_OPTIONS,
    DOMAIN,
    SCHEDULE_TYPE_SELECT_DESCRIPTION,
    ScheduleSelectEntityDescription,
)
from .tdc_coordinator import FroniusTDCCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for schedule and battery configuration."""
    entities: list[SelectEntity] = []

    tdc_coordinator: FroniusTDCCoordinator | None = hass.data[DOMAIN].get(
        entry.entry_id
    )
    if tdc_coordinator:
        await tdc_coordinator.async_config_entry_first_refresh()
        entities.extend(
            FroniusScheduleTypeSelect(tdc_coordinator, entry, index)
            for index in range(len(tdc_coordinator.data or []))
        )

    coordinator: FroniusBatteriesCoordinator | None = (
        hass.data[DOMAIN].get("batteries_coordinator", {}).get(entry.entry_id)
    )

    if not coordinator and not entities:
        _LOGGER.warning(
            "No select-capable coordinator found for entry %s", entry.entry_id
        )
        return

    if coordinator:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("Battery coordinator data available: %s", coordinator.data)

        # Find all select/enum keys for battery select entities
        select_keys = [
            key
            for key, platform_type in BATTERY_CONFIG_KEYS.items()
            if platform_type == "select"
        ]

        battery_select_entities = [
            FroniusBatterySelect(coordinator, entry, key)
            for key in select_keys
            if key in (coordinator.data or {}) and key in BATTERY_SELECT_OPTIONS
        ]
        _LOGGER.debug(
            "Creating %d battery select entities: %s",
            len(battery_select_entities),
            [e.name for e in battery_select_entities],
        )
        entities.extend(battery_select_entities)

    async_add_entities(entities)


class FroniusScheduleTypeSelect(CoordinatorEntity[FroniusTDCCoordinator], SelectEntity):
    """Select entity for schedule type."""

    entity_description: ScheduleSelectEntityDescription = (
        SCHEDULE_TYPE_SELECT_DESCRIPTION
    )

    def __init__(
        self,
        coordinator: FroniusTDCCoordinator,
        entry: ConfigEntry,
        index: int,
    ) -> None:
        """Initialize the schedule type select entity."""
        super().__init__(coordinator)
        self._index = index
        self._entry = entry
        self._attr_unique_id = (
            f"{entry.entry_id}_schedule_{index}_{self.entity_description.key}"
        )
        base_name = slugify(entry.title if isinstance(entry.title, str) else "")
        base_name = base_name or "fronius_tdc"
        self.entity_id = (
            f"select.{base_name}_schedule_{index}_{self.entity_description.key}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Time of Use",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }
        self._attr_options = list(self.entity_description.options or [])

    @property
    def _schedule(self) -> dict[str, Any]:
        """Return the current schedule payload for this entity index."""
        data = self.coordinator.data or []
        if self._index < len(data):
            return data[self._index]
        return {}

    @property
    def name(self) -> str:
        """Return a human-friendly name for this schedule type entity."""
        return f"Schedule {self._index + 1} Type"

    @property
    def current_option(self) -> str | None:
        """Return the current schedule type label."""
        value = self._schedule.get(self.entity_description.value_path[0])
        return self.entity_description.value_to_option.get(value)

    async def async_select_option(self, option: str) -> None:
        """Set the schedule type using the selected label."""
        value = self.entity_description.option_to_value.get(option)
        if value is None:
            _LOGGER.error("Unknown schedule type option %s", option)
            return
        await self.coordinator.async_set_schedule_type(
            index=self._index,
            schedule_type=value,
        )


class FroniusBatterySelect(
    CoordinatorEntity[FroniusBatteriesCoordinator], SelectEntity
):
    """Select entity for an enum battery configuration setting."""

    def __init__(
        self,
        coordinator: FroniusBatteriesCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the battery select entity."""
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_battery_select_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Battery",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

        # Set available options based on the key
        if key in BATTERY_SELECT_OPTIONS:
            options_dict = BATTERY_SELECT_OPTIONS[key]
            self._options_dict = options_dict
            # Extract the display labels as options
            self._attr_options = [str(label) for label in options_dict.values()]
            # Build reverse mapping for converting display label back to value
            self._label_to_value = {
                str(label): value for value, label in options_dict.items()
            }

    @property
    def name(self) -> str:
        """Return a human-friendly name for this battery select."""
        # Convert key to readable format: HYB_EM_MODE → "HYB EM Mode"
        label_info = BATTERY_CONFIG_LABELS.get(self._key, {})
        return label_info.get("name", self._key.replace("_", " ").title())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        config = self.coordinator.data or {}
        current_value = config.get(self._key)

        if current_value is None:
            return None

        # Look up the label for this value
        if current_value in self._options_dict:
            return str(self._options_dict[current_value])

        # If value not in mapping, return None or log warning
        _LOGGER.warning(
            "Battery select %s has unknown value: %s", self._key, current_value
        )
        return None

    async def async_select_option(self, option: str) -> None:
        """Set the select option."""
        # Convert the display label back to the actual value
        if option in self._label_to_value:
            value = self._label_to_value[option]
            await self.coordinator.async_set_select(self._key, value)
        else:
            _LOGGER.error("Unknown option %s for %s", option, self._key)
