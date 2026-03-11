"""Constants for integration_blueprint."""

from dataclasses import dataclass, field
from logging import Logger, getLogger
from typing import Any

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.helpers.entity import EntityDescription

LOGGER: Logger = getLogger(__package__)

DOMAIN = "fronius_tdc"
SERVICE_ADD_SCHEDULE = "add_schedule"
SERVICE_REMOVE_SCHEDULE = "remove_schedule"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

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
SCHEDULE_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

type ScheduleValuePath = tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class ScheduleEntityDescription(EntityDescription):
    """Descriptor metadata for one editable schedule field."""

    value_path: ScheduleValuePath
    setter_name: str
    setter_value_parameter: str


@dataclass(frozen=True, kw_only=True)
class ScheduleSwitchEntityDescription(
    ScheduleEntityDescription, SwitchEntityDescription
):
    """Descriptor for a schedule-backed switch entity."""

    setter_args: tuple[Any, ...] = ()
    entity_id_suffix: str = ""
    unique_id_suffix: str = ""


@dataclass(frozen=True, kw_only=True)
class ScheduleNumberEntityDescription(
    ScheduleEntityDescription, NumberEntityDescription
):
    """Descriptor for a schedule-backed number entity."""


@dataclass(frozen=True, kw_only=True)
class ScheduleSelectEntityDescription(
    ScheduleEntityDescription, SelectEntityDescription
):
    """Descriptor for a schedule-backed select entity."""

    option_to_value: dict[str, str] = field(default_factory=dict)
    value_to_option: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class ScheduleTimeEntityDescription(ScheduleEntityDescription):
    """Descriptor for a schedule-backed time-like entity."""


SCHEDULE_ACTIVE_SWITCH_DESCRIPTION = ScheduleSwitchEntityDescription(
    key="active",
    name="Active",
    value_path=("Active",),
    setter_name="async_set_active",
    setter_value_parameter="active",
    entity_id_suffix="active",
)

SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS = tuple(
    ScheduleSwitchEntityDescription(
        key=f"weekday_{day.lower()}",
        name=day,
        value_path=("Weekdays", day),
        setter_name="async_set_weekday",
        setter_value_parameter="enabled",
        setter_args=(day,),
        entity_id_suffix=day.lower(),
        unique_id_suffix=f"weekday_{day.lower()}",
    )
    for day in SCHEDULE_WEEKDAYS
)

SCHEDULE_POWER_NUMBER_DESCRIPTION = ScheduleNumberEntityDescription(
    key="power",
    name="Power",
    value_path=("Power",),
    setter_name="async_set_power",
    setter_value_parameter="power",
    native_min_value=0,
    native_max_value=200000,
    native_step=100,
)

SCHEDULE_TYPE_SELECT_DESCRIPTION = ScheduleSelectEntityDescription(
    key="schedule_type",
    name="Schedule Type",
    value_path=("ScheduleType",),
    setter_name="async_set_schedule_type",
    setter_value_parameter="schedule_type",
    options=list(SCHEDULE_TYPE_LABELS.values()),
    option_to_value={label: value for value, label in SCHEDULE_TYPE_LABELS.items()},
    value_to_option=dict(SCHEDULE_TYPE_LABELS),
)

SCHEDULE_START_TIME_DESCRIPTION = ScheduleTimeEntityDescription(
    key="start_time",
    name="Start Time",
    value_path=("TimeTable", "Start"),
    setter_name="async_set_start_time",
    setter_value_parameter="start",
)

SCHEDULE_END_TIME_DESCRIPTION = ScheduleTimeEntityDescription(
    key="end_time",
    name="End Time",
    value_path=("TimeTable", "End"),
    setter_name="async_set_end_time",
    setter_value_parameter="end",
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
