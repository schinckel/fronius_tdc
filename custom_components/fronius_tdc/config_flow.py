"""Adds config flow for Fronius TDC."""

from __future__ import annotations

import requests
import voluptuous as vol
from homeassistant import config_entries

from .api import fronius_get_json
from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DEFAULT_PORT,
    DOMAIN,
    ENDPOINT_TOU,
    LOGGER,
)


class BlueprintFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Fronius TDC."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error_key = await self.hass.async_add_executor_job(
                _test_connection_blocking,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            if error_key:
                errors["base"] = error_key
            else:
                await self.async_set_unique_id(f"fronius_tdc_{user_input[CONF_HOST]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Fronius Gen24 ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
            errors=errors,
        )


def _test_connection_blocking(
    host: str, port: int, username: str, password: str
) -> str | None:
    """Test connection to the inverter with the given parameters."""
    url = f"http://{host}:{port}{ENDPOINT_TOU}"
    LOGGER.debug("Testing connection to %s", url)
    try:
        fronius_get_json(url, username, password, timeout=10)
    except requests.HTTPError as exc:
        LOGGER.warning("Fronius TDC connection test HTTP error: %s", exc)
        return (
            "invalid_auth"
            if exc.response.status_code in (401, 403)
            else "cannot_connect"
        )
    except requests.ConnectionError as exc:
        LOGGER.warning("Fronius TDC connection test ConnectionError: %s", exc)
        return "cannot_connect"
    except requests.Timeout as exc:
        LOGGER.warning("Fronius TDC connection test timed out: %s", exc)
        return "cannot_connect"
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Fronius TDC connection test unexpected error: %s", exc)
        return "cannot_connect"
    return None


def _build_schema(defaults: dict) -> vol.Schema:
    """Build the config flow form schema, using defaults where available."""
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Required(
            CONF_USERNAME, default=defaults.get(CONF_USERNAME, "customer")
        ): str,
        vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
    })
