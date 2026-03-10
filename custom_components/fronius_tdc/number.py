"""Number entities: numeric battery configuration settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .batteries_coordinator import FroniusBatteriesCoordinator
from .const import (
    BATTERY_CONFIG_KEYS,
    BATTERY_CONFIG_LABELS,
    DOMAIN,
    SCHEDULE_NUMBER_DESCRIPTIONS,
    ScheduleNumberDescription,
)
from .tdc_coordinator import FroniusTDCCoordinator

_LOGGER = logging.getLogger(__name__)

# Min/max constraints for numeric keys (may need adjustment based on device)
NUMBER_MIN_MAX = {
    "HYB_EM_POWER": (-200000, 200000),  # Negative means export, positive means import
    "HYB_BM_PACMIN": (-200000, 0),  # Must be negative
    "HYB_BACKUP_CRITICALSOC": (0, 100),  # Percentage
    "HYB_BACKUP_RESERVED": (0, 100),  # Percentage
    "BAT_M0_SOC_MAX": (0, 100),  # Percentage
    "BAT_M0_SOC_MIN": (0, 100),  # Percentage
}

# Percentage unit keys
PERCENTAGE_KEYS = {
    "HYB_BACKUP_CRITICALSOC",
    "HYB_BACKUP_RESERVED",
    "BAT_M0_SOC_MAX",
    "BAT_M0_SOC_MIN",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for TOU and battery configuration."""
    entities: list[NumberEntity] = []

    tdc_coordinator: FroniusTDCCoordinator | None = hass.data[DOMAIN].get(
        entry.entry_id
    )
    if tdc_coordinator:
        await tdc_coordinator.async_config_entry_first_refresh()
        for rule_id in tdc_coordinator.get_rule_ids():
            entities.extend(
                [
                    FroniusScheduleNumber(
                        tdc_coordinator,
                        entry,
                        rule_id,
                        description,
                    )
                    for description in SCHEDULE_NUMBER_DESCRIPTIONS
                ]
            )

    coordinator: FroniusBatteriesCoordinator | None = (
        hass.data[DOMAIN].get("batteries_coordinator", {}).get(entry.entry_id)
    )

    if not coordinator:
        _LOGGER.warning(
            "No batteries coordinator found for entry %s, skipping number setup",
            entry.entry_id,
        )
        async_add_entities(entities)
        return

    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Battery coordinator data available: %s", coordinator.data)

    # Find all numeric keys for number entities
    numeric_keys = [
        key
        for key, platform_type in BATTERY_CONFIG_KEYS.items()
        if platform_type == "number"
    ]

    number_entities: list[NumberEntity] = [
        FroniusBatteryNumber(coordinator, entry, key)
        for key in numeric_keys
        if key in (coordinator.data or {})
    ]
    _LOGGER.debug(
        "Creating %d battery number entities: %s",
        len(number_entities),
        [e.name for e in number_entities],
    )
    entities.extend(number_entities)
    async_add_entities(entities)


class FroniusScheduleNumber(CoordinatorEntity[FroniusTDCCoordinator], NumberEntity):
    """Number entity for per-rule TOU power."""

    entity_description: ScheduleNumberDescription

    def __init__(
        self,
        coordinator: FroniusTDCCoordinator,
        entry: ConfigEntry,
        rule_id: str,
        description: ScheduleNumberDescription,
    ) -> None:
        """Initialize the schedule number entity."""
        super().__init__(coordinator)
        self._rule_id = rule_id
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_schedule_{rule_id}_{description.key}"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = description.step
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Time of Use",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

    @property
    def name(self) -> str:
        """Return label for this entity."""
        return cast("str", self.entity_description.name)

    @property
    def native_value(self) -> float | None:
        """Return current rule power."""
        try:
            idx = self.coordinator.resolve_rule_index(self._rule_id)
        except ValueError:
            return None
        value = (self.coordinator.data or [])[idx].get("Power")
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set rule power value."""
        await self.coordinator.async_set_power(self._rule_id, int(value))


class FroniusBatteryNumber(
    CoordinatorEntity[FroniusBatteriesCoordinator], NumberEntity
):
    """Number entity for a numeric battery configuration setting."""

    def __init__(
        self,
        coordinator: FroniusBatteriesCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the battery number entity."""
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_battery_number_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Battery",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

        # Set min/max if available
        if key in NUMBER_MIN_MAX:
            min_val, max_val = NUMBER_MIN_MAX[key]
            self._attr_native_min_value = min_val
            self._attr_native_max_value = max_val

        # Set unit if this is a percentage key
        if key in PERCENTAGE_KEYS:
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif "POWER" in key or "PAC" in key:
            self._attr_native_unit_of_measurement = UnitOfPower.WATT

    @property
    def name(self) -> str:
        """Return a human-friendly name for this battery number."""
        label_info = BATTERY_CONFIG_LABELS.get(self._key, {})
        return label_info.get("name", self._key.replace("_", " ").title())

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        config = self.coordinator.data or {}
        value = config.get(self._key)
        if value is not None:
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the numeric value."""
        # Convert to int if appropriate
        int_value = int(value) if value == int(value) else value
        await self.coordinator.async_set_number(self._key, int_value)
