"""Constants for integration_blueprint."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "fronius_tdc"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"  # noqa: S105

DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 30

# Single endpoint handles both GET (read) and POST (write)
ENDPOINT_TOU = "/api/config/timeofuse"

SCHEDULE_TYPE_LABELS = {
    "CHARGE_MAX": "Charge Max",
    "CHARGE_MIN": "Charge Min",
    "DISCHARGE_MAX": "Discharge Max",
    "DISCHARGE_MIN": "Discharge Min",
}
