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
ENDPOINT_BATTERIES = "/api/config/batteries"

SCHEDULE_TYPE_LABELS = {
    "CHARGE_MAX": "Charge Max",
    "CHARGE_MIN": "Charge Min",
    "DISCHARGE_MAX": "Discharge Max",
    "DISCHARGE_MIN": "Discharge Min",
}

# Battery configuration keys mapping: key → platform type
BATTERY_CONFIG_KEYS = {
    # Boolean switches
    "HYB_EVU_CHARGEFROMGRID": "switch",
    "HYB_BM_CHARGEFROMAC": "switch",
    # Numeric inputs
    "HYB_EM_POWER": "number",
    "HYB_BM_PACMIN": "number",
    "HYB_BACKUP_CRITICALSOC": "number",
    "HYB_BACKUP_RESERVED": "number",
    "BAT_M0_SOC_MAX": "number",
    "BAT_M0_SOC_MIN": "number",
    # Select/enum configs
    "HYB_EM_MODE": "select",
    "BAT_M0_SOC_MODE": "select",
}

# Battery select options mapping: key → {value: label}
BATTERY_SELECT_OPTIONS = {
    "HYB_EM_MODE": {
        0: "Automatic",
        1: "Manual",
    },
    "BAT_M0_SOC_MODE": {
        "manual": "Manual",
        "auto": "Auto",
    },
}

# Battery configuration labels and descriptions
# Maps key → {"name": human_readable_name, "description": help_text}
BATTERY_CONFIG_LABELS = {
    # Boolean switches
    "HYB_EVU_CHARGEFROMGRID": {
        "name": "Charge From Grid",
        "description": "Allow charging the battery from the grid",
    },
    "HYB_BM_CHARGEFROMAC": {
        "name": "Charge From AC",
        "description": "Allow charging the battery from AC input",
    },
    # Numeric inputs
    "HYB_EM_POWER": {
        "name": "Energy Management Power",
        "description": "Power setting for energy management (W)",
    },
    "HYB_BM_PACMIN": {
        "name": "Battery Manager Min Power",
        "description": "Minimum AC power threshold (W)",
    },
    "HYB_BACKUP_CRITICALSOC": {
        "name": "Backup Critical SOC",
        "description": "Critical state of charge for backup mode (%)",
    },
    "HYB_BACKUP_RESERVED": {
        "name": "Backup Reserved SOC",
        "description": "Reserved state of charge for backup mode (%)",
    },
    "BAT_M0_SOC_MAX": {
        "name": "Battery Max SOC",
        "description": "Maximum state of charge for battery (%)",
    },
    "BAT_M0_SOC_MIN": {
        "name": "Battery Min SOC",
        "description": "Minimum state of charge for battery (%)",
    },
    # Select/enum configs
    "HYB_EM_MODE": {
        "name": "Energy Management Mode",
        "description": "Operation mode: Automatic or Manual",
    },
    "BAT_M0_SOC_MODE": {
        "name": "Battery SOC Mode",
        "description": "State of charge mode: Auto or Manual",
    },
}
