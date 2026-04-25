"""Adds config flow for Fronius TDC."""

from __future__ import annotations

import re
from ipaddress import IPv4Address

import requests
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

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

HOSTNAME_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


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
            normalized_host = _normalize_host(user_input[CONF_HOST])
            user_input = {
                **user_input,
                CONF_HOST: normalized_host,
            }
            error_key = await self.hass.async_add_executor_job(
                _test_connection_blocking,
                normalized_host,
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            if error_key:
                errors["base"] = error_key
            else:
                await self.async_set_unique_id(f"fronius_tdc_{normalized_host}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Fronius Gen24 ({normalized_host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
            errors=errors,
        )


def _test_connection_blocking(host: str, port: int, username: str, password: str) -> str | None:
    """Test connection to the inverter with the given parameters."""
    url = f"http://{host}:{port}{ENDPOINT_TOU}"
    LOGGER.debug("Testing connection to %s", url)
    try:
        fronius_get_json(url, username, password, timeout=10)
    except requests.HTTPError as exc:
        LOGGER.warning("Fronius TDC connection test HTTP error: %s", exc)
        return "invalid_auth" if exc.response.status_code in (401, 403) else "cannot_connect"
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


def _normalize_host(host: str) -> str:
    """Normalize and validate a host value from the config flow."""
    value = cv.string(host).strip()
    if not value:
        msg = "Host is required"
        raise vol.Invalid(msg)

    if any(char in value for char in ("://", "/", "?", "#", "@", ":")):
        msg = "Enter a hostname or IP address, not a URL"
        raise vol.Invalid(msg)

    try:
        return str(IPv4Address(value))
    except ValueError as exc:
        normalized = value.lower()
        if len(normalized) > 253 or "." not in normalized:  # noqa: PLR2004
            msg = "Enter a valid hostname or IPv4 address"
            raise vol.Invalid(msg) from exc

        labels = normalized.split(".")
        if not all(HOSTNAME_LABEL_RE.fullmatch(label) for label in labels):
            msg = "Enter a valid hostname or IPv4 address"
            raise vol.Invalid(msg) from exc

        return normalized


def _build_schema(defaults: dict) -> vol.Schema:
    """Build the config flow form schema, using defaults where available."""
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): _normalize_host,
        vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=65535),
        ),
        vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "customer")): cv.string,
        vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): cv.string,
    })
