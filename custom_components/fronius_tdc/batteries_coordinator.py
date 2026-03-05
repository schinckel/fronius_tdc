"""DataUpdateCoordinator: manages Fronius Gen24 battery configuration."""

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
    ENDPOINT_BATTERIES,
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


class FroniusBatteriesCoordinator(DataUpdateCoordinator[dict]):
    """
    Coordinator that manages battery configuration via a single config object.

    self.data → single configuration dict with keys like:
        {
            "HYB_EVU_CHARGEFROMGRID": bool,
            "HYB_BM_CHARGEFROMAC": bool,
            "HYB_EM_POWER": int,
            "HYB_BM_PACMIN": int,
            "HYB_BACKUP_CRITICALSOC": int,
            "HYB_BACKUP_RESERVED": int,
            "BAT_M0_SOC_MAX": int,
            "BAT_M0_SOC_MIN": int,
            "HYB_EM_MODE": int or str,
            "BAT_M0_SOC_MODE": str,
        }
    """

    def __init__(
        self, hass: HomeAssistant, logger: logging.Logger, config_entry: Any
    ) -> None:
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
        return f"http://{self._host}:{self._port}{ENDPOINT_BATTERIES}"

    # ------------------------------------------------------------------
    # Blocking helpers (executor)
    # ------------------------------------------------------------------

    def _blocking_get(self) -> dict:
        """Get the current battery configuration."""
        try:
            raw = fronius_get_json(
                self._url, self._username, self._password, REQUEST_TIMEOUT
            )
            # The endpoint returns the config object directly, not wrapped
            config = _strip_meta(raw)
            _LOGGER.debug("Battery config fetched: %s", config)
        except requests.HTTPError as err:
            # If read is not supported (404, etc), log and return empty dict
            _LOGGER.warning(
                "Cannot read battery config from %s: %s. Using cached/empty data.",
                self._url,
                err,
            )
            return {}
        return config

    def _blocking_post(self, key: str, *, value: str | bool | float) -> None:
        """
        Write a single battery configuration field to the inverter.

        Only sends the specific field being changed, not the entire configuration.
        """
        payload = {key: value}
        fronius_post_json(
            self._url,
            self._username,
            self._password,
            payload,
            REQUEST_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        try:
            return await self.hass.async_add_executor_job(self._blocking_get)
        except requests.RequestException as err:
            msg = f"Cannot reach Fronius inverter: {err}"
            raise UpdateFailed(msg) from err

    # ------------------------------------------------------------------
    # Action methods (read-modify-write patterns)
    # ------------------------------------------------------------------

    async def async_set_switch(self, key: str, *, value: bool) -> None:
        """Set a boolean config value and update the inverter."""
        try:
            await self.hass.async_add_executor_job(self._blocking_post, key, value)
        except requests.RequestException as err:
            msg = f"Failed to set {key} to {value}: {err}"
            raise UpdateFailed(msg) from err
        await self.async_refresh()

    async def async_set_number(self, key: str, value: float) -> None:
        """Set a numeric config value and update the inverter."""
        try:
            await self.hass.async_add_executor_job(self._blocking_post, key, value)
        except requests.RequestException as err:
            msg = f"Failed to set {key} to {value}: {err}"
            raise UpdateFailed(msg) from err
        await self.async_refresh()

    async def async_set_select(self, key: str, value: str | int) -> None:
        """Set a select/enum config value and update the inverter."""
        try:
            await self.hass.async_add_executor_job(self._blocking_post, key, value)
        except requests.RequestException as err:
            msg = f"Failed to set {key} to {value}: {err}"
            raise UpdateFailed(msg) from err
        await self.async_refresh()

    def test_connection_blocking(self) -> dict:
        """Test connection by performing a single GET request."""
        return self._blocking_get()
