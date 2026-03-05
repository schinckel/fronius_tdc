"""Number entities: numeric battery configuration settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .batteries_coordinator import FroniusBatteriesCoordinator
from .const import BATTERY_CONFIG_KEYS, BATTERY_CONFIG_LABELS, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Min/max constraints for numeric keys (may need adjustment based on device)
NUMBER_MIN_MAX = {
    "HYB_EM_POWER": (0, 10000),  # Example: 0-10000W, adjust as needed
    "HYB_BM_PACMIN": (0, 10000),  # Example: 0-10000W, adjust as needed
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
    """Set up number entities for battery configuration."""
    coordinator: FroniusBatteriesCoordinator = (
        hass.data[DOMAIN].get("batteries_coordinator", {}).get(entry.entry_id)
    )

    if not coordinator:
        _LOGGER.warning(
            "No batteries coordinator found for entry %s, skipping number setup",
            entry.entry_id,
        )
        return

    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Battery coordinator data available: %s", coordinator.data)

    # Find all numeric keys for number entities
    numeric_keys = [
        key
        for key, platform_type in BATTERY_CONFIG_KEYS.items()
        if platform_type == "number"
    ]

    number_entities = [
        FroniusBatteryNumber(coordinator, entry, key)
        for key in numeric_keys
        if key in (coordinator.data or {})
    ]
    _LOGGER.debug(
        "Creating %d battery number entities: %s",
        len(number_entities),
        [e.name for e in number_entities],
    )
    async_add_entities(number_entities)


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
