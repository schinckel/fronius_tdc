"""DataUpdateCoordinator: polls Fronius Gen24 Time of Use schedules."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
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
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
SCHEDULE_REQUIRED_KEYS = ("Active", "ScheduleType", "Power", "TimeTable", "Weekdays")
TIME_TABLE_REQUIRED_KEYS = ("Start", "End")
WEEKDAY_KEYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
TIME_24H_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _strip_meta(obj: Any) -> Any:
    """Recursively remove all keys beginning with '_' (metadata fields)."""
    if isinstance(obj, dict):
        return {k: _strip_meta(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_meta(item) for item in obj]
    return obj


def _validate_schedule_type(schedule_type: Any) -> None:
    """Validate schedule type value from inverter payload."""
    if not isinstance(schedule_type, str):
        msg = "ScheduleType must be a string"
        raise TypeError(msg)
    if schedule_type not in {
        "CHARGE_MAX",
        "CHARGE_MIN",
        "DISCHARGE_MAX",
        "DISCHARGE_MIN",
    }:
        msg = f"Unsupported ScheduleType: {schedule_type}"
        raise ValueError(msg)


def _validate_time_value(value: Any, field_name: str) -> None:
    """Validate strict 24h HH:MM time values."""
    if not isinstance(value, str) or not TIME_24H_PATTERN.fullmatch(value):
        msg = f"{field_name} must be in HH:MM 24h format"
        raise TypeError(msg) if not isinstance(value, str) else ValueError(msg)


def _validate_weekdays(weekdays: Any) -> None:
    """Validate weekday map contains all expected day keys as booleans."""
    if not isinstance(weekdays, dict):
        msg = "Weekdays must be an object"
        raise TypeError(msg)

    missing_days = [day for day in WEEKDAY_KEYS if day not in weekdays]
    if missing_days:
        msg = f"Weekdays missing keys: {', '.join(missing_days)}"
        raise ValueError(msg)

    for day in WEEKDAY_KEYS:
        if not isinstance(weekdays[day], bool):
            msg = f"Weekdays.{day} must be a boolean"
            raise TypeError(msg)


def _normalize_rule(rule: Any) -> dict[str, Any]:
    """Normalize and validate one TOU schedule rule into canonical schema."""
    if not isinstance(rule, dict):
        msg = "Schedule rule must be an object"
        raise TypeError(msg)

    missing_keys = [key for key in SCHEDULE_REQUIRED_KEYS if key not in rule]
    if missing_keys:
        msg = f"Schedule rule missing required keys: {', '.join(missing_keys)}"
        raise ValueError(msg)

    active = rule["Active"]
    if not isinstance(active, bool):
        msg = "Active must be a boolean"
        raise TypeError(msg)

    _validate_schedule_type(rule["ScheduleType"])
    schedule_type = rule["ScheduleType"]

    power = rule["Power"]
    if isinstance(power, bool) or not isinstance(power, int):
        msg = "Power must be an integer"
        raise TypeError(msg)

    timetable = rule["TimeTable"]
    if not isinstance(timetable, dict):
        msg = "TimeTable must be an object"
        raise TypeError(msg)

    missing_time_keys = [
        key for key in TIME_TABLE_REQUIRED_KEYS if key not in timetable
    ]
    if missing_time_keys:
        msg = f"TimeTable missing required keys: {', '.join(missing_time_keys)}"
        raise ValueError(msg)

    _validate_time_value(timetable["Start"], "TimeTable.Start")
    _validate_time_value(timetable["End"], "TimeTable.End")

    weekdays = rule["Weekdays"]
    _validate_weekdays(weekdays)

    return {
        "Active": active,
        "ScheduleType": schedule_type,
        "Power": power,
        "TimeTable": {
            "Start": timetable["Start"],
            "End": timetable["End"],
        },
        "Weekdays": {day: weekdays[day] for day in WEEKDAY_KEYS},
    }


def _normalize_schedules(schedules: Any) -> list[dict[str, Any]]:
    """Normalize and validate list of TOU schedule rules."""
    if not isinstance(schedules, list):
        msg = "timeofuse payload must be a list"
        raise TypeError(msg)
    return [_normalize_rule(rule) for rule in schedules]


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
        return f"http://{self._host}:{self._port}{ENDPOINT_TOU}"

    # ------------------------------------------------------------------
    # Blocking helpers (executor)
    # ------------------------------------------------------------------

    def _blocking_get(self) -> list[dict]:
        raw = fronius_get_json(
            self._url, self._username, self._password, REQUEST_TIMEOUT
        )
        schedules = raw.get("timeofuse", [])
        return _normalize_schedules([_strip_meta(s) for s in schedules])

    def _blocking_post(self, schedules: list[dict]) -> None:
        """Write the full schedule list back to the inverter."""
        payload_schedules = _normalize_schedules(
            [_strip_meta(rule) for rule in schedules]
        )
        fronius_post_json(
            self._url,
            self._username,
            self._password,
            {"timeofuse": payload_schedules},
            REQUEST_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> list[dict]:
        try:
            return await self.hass.async_add_executor_job(self._blocking_get)
        except (ValueError, TypeError) as err:
            msg = f"Invalid schedule payload from inverter: {err}"
            raise UpdateFailed(msg) from err
        except requests.HTTPError as err:
            msg = f"HTTP error from inverter: {err}"
            raise UpdateFailed(msg) from err
        except requests.RequestException as err:
            msg = f"Cannot reach Fronius inverter: {err}"
            raise UpdateFailed(msg) from err

    async def _async_read_modify_write(
        self, index: int, mutate: Callable[[dict[str, Any]], None], *, operation: str
    ) -> None:
        """Fetch latest schedules, mutate one entry, write full list, refresh."""
        try:
            schedules = await self.hass.async_add_executor_job(self._blocking_get)
        except (ValueError, TypeError) as err:
            msg = f"Invalid schedule payload from inverter: {err}"
            raise UpdateFailed(msg) from err
        except requests.HTTPError as err:
            msg = f"HTTP error from inverter: {err}"
            raise UpdateFailed(msg) from err
        except requests.RequestException as err:
            msg = f"Cannot reach Fronius inverter: {err}"
            raise UpdateFailed(msg) from err

        updated_schedules = deepcopy(schedules)
        if index >= len(updated_schedules):
            _LOGGER.error("Schedule index %d out of range", index)
            return

        try:
            mutate(updated_schedules[index])
            updated_schedules = _normalize_schedules(updated_schedules)
        except (ValueError, TypeError) as err:
            msg = f"Invalid schedule update for index {index}: {err}"
            raise UpdateFailed(msg) from err

        try:
            await self.hass.async_add_executor_job(
                self._blocking_post, updated_schedules
            )
        except (ValueError, TypeError) as err:
            msg = f"Invalid schedule update for index {index}: {err}"
            raise UpdateFailed(msg) from err
        except requests.RequestException as err:
            msg = f"Failed to {operation} for schedule {index}: {err}"
            raise UpdateFailed(msg) from err

        await self.async_refresh()

    async def _async_update_rule_field(
        self, index: int, *, field_path: tuple[str, ...], value: Any, operation: str
    ) -> None:
        """Update one rule field via centralized read-modify-write flow."""
        if not field_path:
            msg = "field_path must not be empty"
            raise ValueError(msg)

        def _mutate(schedule: dict[str, Any]) -> None:
            target: dict[str, Any] = schedule
            for key in field_path[:-1]:
                nested = target.get(key)
                if not isinstance(nested, dict):
                    msg = f"{'.'.join(field_path[:-1])} must be an object"
                    raise TypeError(msg)
                target = nested
            target[field_path[-1]] = value

        await self._async_read_modify_write(
            index=index, mutate=_mutate, operation=operation
        )

    async def async_set_active(self, index: int, *, active: bool) -> None:
        """
        Toggle the Active flag on one schedule entry and push the full list back.

        The inverter's API only supports writing the full list of schedules,
        so we read-modify-write the entire list here.
        """
        await self._async_update_rule_field(
            index,
            field_path=("Active",),
            value=active,
            operation="set active",
        )

    def test_connection_blocking(self) -> list[dict]:
        """Test connection by performing a single GET request."""
        return self._blocking_get()
