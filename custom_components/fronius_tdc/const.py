"""Constants for integration_blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger, getLogger

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.time import TimeEntityDescription

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

SCHEDULE_TYPES = tuple(SCHEDULE_TYPE_LABELS)
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SCHEDULE_POWER_MIN = 0
SCHEDULE_POWER_MAX = 20000
SCHEDULE_POWER_STEP = 100

SERVICE_ADD_SCHEDULE = "add_schedule"
SERVICE_REMOVE_SCHEDULE = "remove_schedule"


@dataclass(frozen=True)
class ScheduleSwitchDescription(SwitchEntityDescription):
    """Descriptor for per-rule switch entities."""

    weekday: str | None = None


@dataclass(frozen=True)
class ScheduleNumberDescription(NumberEntityDescription):
    """Descriptor for per-rule number entities."""

    min_value: int = 0
    max_value: int = 0
    step: int = 0


@dataclass(frozen=True)
class ScheduleSelectDescription(SelectEntityDescription):
    """Descriptor for per-rule select entities."""

    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleTimeDescription(TimeEntityDescription):
    """Descriptor for per-rule time entities."""

    timetable_field: str = ""


SCHEDULE_SWITCH_DESCRIPTIONS = (
    ScheduleSwitchDescription(key="active", name="Active"),
    *(
        ScheduleSwitchDescription(key=f"weekday_{day.lower()}", name=day, weekday=day)
        for day in WEEKDAYS
    ),
)

SCHEDULE_NUMBER_DESCRIPTIONS = (
    ScheduleNumberDescription(
        key="power",
        name="Power",
        min_value=SCHEDULE_POWER_MIN,
        max_value=SCHEDULE_POWER_MAX,
        step=SCHEDULE_POWER_STEP,
    ),
)

SCHEDULE_SELECT_DESCRIPTIONS = (
    ScheduleSelectDescription(
        key="schedule_type",
        name="Type",
        options=SCHEDULE_TYPES,
    ),
)

SCHEDULE_TIME_DESCRIPTIONS = (
    ScheduleTimeDescription(key="start", name="Start Time", timetable_field="Start"),
    ScheduleTimeDescription(key="end", name="End Time", timetable_field="End"),
)

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
