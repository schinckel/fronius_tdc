"""Select entities: enum battery configuration settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    SCHEDULE_SELECT_DESCRIPTIONS,
    SCHEDULE_TYPE_LABELS,
    ScheduleSelectDescription,
)
from .tdc_coordinator import FroniusTDCCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for TOU and battery configuration."""
    entities: list[SelectEntity] = []

    tdc_coordinator: FroniusTDCCoordinator | None = hass.data[DOMAIN].get(
        entry.entry_id
    )
    if tdc_coordinator:
        await tdc_coordinator.async_config_entry_first_refresh()
        for rule_id in tdc_coordinator.get_rule_ids():
            entities.extend(
                [
                    FroniusScheduleSelect(
                        tdc_coordinator,
                        entry,
                        rule_id,
                        description,
                    )
                    for description in SCHEDULE_SELECT_DESCRIPTIONS
                ]
            )

    coordinator: FroniusBatteriesCoordinator | None = (
        hass.data[DOMAIN].get("batteries_coordinator", {}).get(entry.entry_id)
    )

    if not coordinator:
        _LOGGER.warning(
            "No batteries coordinator found for entry %s, skipping select setup",
            entry.entry_id,
        )
        async_add_entities(entities)
        return

    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Battery coordinator data available: %s", coordinator.data)

    # Find all select/enum keys for select entities
    select_keys = [
        key
        for key, platform_type in BATTERY_CONFIG_KEYS.items()
        if platform_type == "select"
    ]

    select_entities: list[SelectEntity] = [
        FroniusBatterySelect(coordinator, entry, key)
        for key in select_keys
        if key in (coordinator.data or {}) and key in BATTERY_SELECT_OPTIONS
    ]
    _LOGGER.debug(
        "Creating %d battery select entities: %s",
        len(select_entities),
        [e.name for e in select_entities],
    )
    entities.extend(select_entities)
    async_add_entities(entities)


class FroniusScheduleSelect(CoordinatorEntity[FroniusTDCCoordinator], SelectEntity):
    """Select entity for per-rule schedule type."""

    entity_description: ScheduleSelectDescription

    def __init__(
        self,
        coordinator: FroniusTDCCoordinator,
        entry: ConfigEntry,
        rule_id: str,
        description: ScheduleSelectDescription,
    ) -> None:
        """Initialize the schedule select entity."""
        super().__init__(coordinator)
        self._rule_id = rule_id
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_schedule_{rule_id}_{description.key}"
        self._attr_options = [SCHEDULE_TYPE_LABELS[key] for key in description.options]
        self._label_to_value = {
            label: key
            for key, label in SCHEDULE_TYPE_LABELS.items()
            if key in description.options
        }
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
    def current_option(self) -> str | None:
        """Return currently selected option label."""
        try:
            idx = self.coordinator.resolve_rule_index(self._rule_id)
        except ValueError:
            return None
        value = (self.coordinator.data or [])[idx].get("ScheduleType")
        if value is None:
            return None
        return SCHEDULE_TYPE_LABELS.get(value, value)

    async def async_select_option(self, option: str) -> None:
        """Set selected schedule type."""
        if option not in self._label_to_value:
            msg = f"Invalid schedule type option: {option}"
            raise ValueError(msg)
        await self.coordinator.async_set_schedule_type(
            self._rule_id,
            self._label_to_value[option],
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
        else:
            # Initialize with empty options if key not found
            self._options_dict = {}
            self._attr_options = []
            self._label_to_value = {}

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

        # If no mapping exists, return the raw value as string
        return str(current_value)

    async def async_select_option(self, option: str) -> None:
        """Set the select option."""
        # Convert the display label back to the actual value
        if option in self._label_to_value:
            value = self._label_to_value[option]
            await self.coordinator.async_set_select(self._key, value)
        else:
            # If no mapping exists, use the option value directly
            await self.coordinator.async_set_select(self._key, option)
