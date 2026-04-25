"""DataUpdateCoordinator: polls Fronius Gen24 Time of Use schedules."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import requests
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import fronius_get_json, fronius_post_json
from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENDPOINT_TOU,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15


def _strip_meta(obj: Any) -> Any:
    """Recursively remove all keys beginning with '_' (metadata fields)."""
    if isinstance(obj, dict):
        return {k: _strip_meta(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_meta(item) for item in obj]
    return obj


class FroniusTDCCoordinator(DataUpdateCoordinator[list[dict]]):
    """
    Coordinator that owns the list of Time of Use schedule entries.

    self.data → list of dicts, one per schedule, meta fields stripped:
        {
            "Active": bool,
            "ScheduleType": str,   # (CHARGE/DISCHARGE)_(MIN/MAX)
            "Power": int,          # watts
            "TimeTable": {"Start": "HH:MM", "End": "HH:MM"},
            "Weekdays": {"Mon": bool, "Tue": bool, ...},
        }
    """

    def __init__(self, hass: HomeAssistant, logger: logging.Logger, config_entry: Any) -> None:
        """Initialize the coordinator and parse connection parameters."""
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        cfg = config_entry.data
        self._host = cfg[CONF_HOST]
        self._port = cfg[CONF_PORT]
        self._username = cfg[CONF_USERNAME]
        self._password = cfg[CONF_PASSWORD]

    @property
    def _url(self) -> str:
        return f"http://{self._host}:{self._port}{ENDPOINT_TOU}"

    # ------------------------------------------------------------------
    # Blocking helpers (executor)
    # ------------------------------------------------------------------

    def _blocking_get(self) -> list[dict]:
        raw = fronius_get_json(self._url, self._username, self._password, REQUEST_TIMEOUT)
        schedules = raw.get("timeofuse", [])
        return [_strip_meta(s) for s in schedules]

    def _blocking_post(self, schedules: list[dict]) -> None:
        """Write the full schedule list back to the inverter."""
        fronius_post_json(
            self._url,
            self._username,
            self._password,
            {"timeofuse": schedules},
            REQUEST_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> list[dict]:
        try:
            return await self.hass.async_add_executor_job(self._blocking_get)
        except requests.HTTPError as err:
            msg = f"HTTP error from inverter: {err}"
            raise UpdateFailed(msg) from err
        except requests.RequestException as err:
            msg = f"Cannot reach Fronius inverter: {err}"
            raise UpdateFailed(msg) from err

    async def async_set_active(self, index: int, *, active: bool) -> None:
        """
        Toggle the Active flag on one schedule entry and push the full list back.

        The inverter's API only supports writing the full list of schedules,
        so we read-modify-write the entire list here.
        """
        schedules = [dict(s) for s in (self.data or [])]
        if index >= len(schedules):
            _LOGGER.error("Schedule index %d out of range", index)
            return
        schedules[index] = dict(schedules[index])
        schedules[index]["Active"] = active
        try:
            await self.hass.async_add_executor_job(self._blocking_post, schedules)
        except requests.RequestException as err:
            msg = f"Failed to update schedule {index}: {err}"
            raise UpdateFailed(msg) from err
        await self.async_refresh()

    def test_connection_blocking(self) -> list[dict]:
        """Test connection by performing a single GET request."""
        return self._blocking_get()
