"""Number entities: numeric battery configuration settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE, UnitOfPower
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
    SCHEDULE_POWER_NUMBER_DESCRIPTION,
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
    """Set up number entities for schedule and battery configuration."""
    entities: list[NumberEntity] = []

    tdc_coordinator: FroniusTDCCoordinator | None = hass.data[DOMAIN].get(
        entry.entry_id
    )
    if tdc_coordinator:
        await tdc_coordinator.async_config_entry_first_refresh()
        entities.extend(
            FroniusSchedulePowerNumber(tdc_coordinator, entry, index)
            for index in range(len(tdc_coordinator.data or []))
        )

    coordinator: FroniusBatteriesCoordinator | None = (
        hass.data[DOMAIN].get("batteries_coordinator", {}).get(entry.entry_id)
    )

    if not coordinator and not entities:
        _LOGGER.warning(
            "No number-capable coordinator found for entry %s", entry.entry_id
        )
        return

    if coordinator:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("Battery coordinator data available: %s", coordinator.data)

        # Find all numeric keys for battery number entities
        numeric_keys = [
            key
            for key, platform_type in BATTERY_CONFIG_KEYS.items()
            if platform_type == "number"
        ]

        battery_number_entities = [
            FroniusBatteryNumber(coordinator, entry, key)
            for key in numeric_keys
            if key in (coordinator.data or {})
        ]
        _LOGGER.debug(
            "Creating %d battery number entities: %s",
            len(battery_number_entities),
            [e.name for e in battery_number_entities],
        )
        entities.extend(battery_number_entities)

    async_add_entities(entities)


class FroniusSchedulePowerNumber(
    CoordinatorEntity[FroniusTDCCoordinator], NumberEntity
):
    """Number entity for schedule power."""

    entity_description = SCHEDULE_POWER_NUMBER_DESCRIPTION

    def __init__(
        self,
        coordinator: FroniusTDCCoordinator,
        entry: ConfigEntry,
        index: int,
    ) -> None:
        """Initialize the schedule power number entity."""
        super().__init__(coordinator)
        self._index = index
        self._entry = entry
        self._attr_unique_id = (
            f"{entry.entry_id}_schedule_{index}_{self.entity_description.key}"
        )
        base_name = slugify(entry.title if isinstance(entry.title, str) else "")
        base_name = base_name or "fronius_tdc"
        self.entity_id = (
            f"number.{base_name}_schedule_{index}_{self.entity_description.key}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Fronius Gen24 Time of Use",
            "manufacturer": "Fronius",
            "model": "GEN24 Plus / Symo GEN24",
        }

    @property
    def _schedule(self) -> dict[str, Any]:
        """Return the current schedule payload for this entity index."""
        data = self.coordinator.data or []
        if self._index < len(data):
            return data[self._index]
        return {}

    @property
    def name(self) -> str:
        """Return a human-friendly name for this schedule power entity."""
        return f"Schedule {self._index + 1} Power"

    @property
    def native_value(self) -> float | None:
        """Return the current schedule power."""
        power = self._schedule.get(self.entity_description.value_path[0])
        if power is None:
            return None
        return float(power)

    async def async_set_native_value(self, value: float) -> None:
        """Set schedule power."""
        await self.coordinator.async_set_power(index=self._index, power=int(value))


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
