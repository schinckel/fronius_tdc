"""DataUpdateCoordinator: polls Fronius Gen24 Time of Use schedules."""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from datetime import timedelta
from hashlib import sha1
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
    SCHEDULE_POWER_MAX,
    SCHEDULE_POWER_MIN,
    SCHEDULE_TYPES,
    WEEKDAYS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _strip_meta(obj: Any) -> Any:
    """Recursively remove all keys beginning with '_' (metadata fields)."""
    if isinstance(obj, dict):
        return {k: _strip_meta(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_meta(item) for item in obj]
    return obj


def _is_valid_hhmm(value: str) -> bool:
    """Return True for strict 24h HH:MM values."""
    return bool(TIME_PATTERN.fullmatch(value))


def _ensure_schedule_type(value: str) -> None:
    """Validate schedule type value."""
    if value not in SCHEDULE_TYPES:
        msg = f"Invalid schedule type: {value}"
        raise ValueError(msg)


def _ensure_time(value: str, *, field: str) -> None:
    """Validate strict time value."""
    if not _is_valid_hhmm(value):
        msg = f"Invalid {field} time '{value}', expected HH:MM"
        raise ValueError(msg)


def _ensure_power(value: int) -> None:
    """Validate power bounds."""
    if not SCHEDULE_POWER_MIN <= value <= SCHEDULE_POWER_MAX:
        msg = f"Power {value} out of range [{SCHEDULE_POWER_MIN}, {SCHEDULE_POWER_MAX}]"
        raise ValueError(msg)


def _ensure_weekdays(weekdays: dict[str, Any]) -> None:
    """Validate full weekday mapping with bool values."""
    for day in WEEKDAYS:
        if day not in weekdays:
            msg = f"Missing weekday: {day}"
            raise ValueError(msg)
        if not isinstance(weekdays[day], bool):
            msg = f"Weekday '{day}' must be boolean"
            raise TypeError(msg)


def validate_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one schedule payload."""
    required = {"Active", "ScheduleType", "Power", "TimeTable", "Weekdays"}
    missing = required - set(schedule)
    if missing:
        msg = f"Missing schedule keys: {sorted(missing)}"
        raise ValueError(msg)

    timetable = schedule["TimeTable"]
    if not isinstance(timetable, dict):
        msg = "TimeTable must be an object"
        raise TypeError(msg)
    if "Start" not in timetable or "End" not in timetable:
        msg = "TimeTable requires Start and End"
        raise ValueError(msg)

    weekdays = schedule["Weekdays"]
    if not isinstance(weekdays, dict):
        msg = "Weekdays must be an object"
        raise TypeError(msg)

    normalized = {
        "Active": bool(schedule["Active"]),
        "ScheduleType": str(schedule["ScheduleType"]),
        "Power": int(schedule["Power"]),
        "TimeTable": {
            "Start": str(timetable["Start"]),
            "End": str(timetable["End"]),
        },
        "Weekdays": {day: bool(weekdays.get(day, False)) for day in WEEKDAYS},
    }

    _ensure_schedule_type(normalized["ScheduleType"])
    _ensure_power(normalized["Power"])
    _ensure_time(normalized["TimeTable"]["Start"], field="start")
    _ensure_time(normalized["TimeTable"]["End"], field="end")
    _ensure_weekdays(normalized["Weekdays"])
    return normalized


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
        self._rule_id_to_index: dict[str, int] = {}
        self._previous_generated_ids: dict[str, str] = {}
        self._rule_ids_changed = False

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
        if not isinstance(schedules, list):
            msg = "Invalid inverter payload: timeofuse must be a list"
            raise TypeError(msg)

        normalized: list[dict[str, Any]] = []
        next_mapping: dict[str, int] = {}
        collisions: dict[str, int] = {}

        for index, raw_schedule in enumerate(schedules):
            clean_schedule = validate_schedule(_strip_meta(raw_schedule))
            rule_id = self._derive_rule_id(raw_schedule, clean_schedule, collisions)
            clean_schedule["rule_id"] = rule_id
            normalized.append(clean_schedule)
            next_mapping[rule_id] = index

        old_rule_ids = tuple(self._rule_id_to_index)
        new_rule_ids = tuple(next_mapping)
        if old_rule_ids and old_rule_ids != new_rule_ids:
            self._rule_ids_changed = True

        self._rule_id_to_index = next_mapping
        return normalized

    def _derive_rule_id(
        self,
        raw_schedule: dict[str, Any],
        normalized_schedule: dict[str, Any],
        collisions: dict[str, int],
    ) -> str:
        """Build stable ID from inverter metadata or a deterministic fallback hash."""
        explicit_id = raw_schedule.get("_Id")
        if explicit_id not in (None, ""):
            return str(explicit_id)

        signature = json.dumps(
            normalized_schedule, sort_keys=True, separators=(",", ":")
        )
        digest = sha1(signature.encode("utf-8")).hexdigest()[:10]  # NOQA: S324
        base = self._previous_generated_ids.get(signature, f"hash_{digest}")
        collisions[base] = collisions.get(base, 0) + 1
        resolved = base if collisions[base] == 1 else f"{base}_{collisions[base]}"
        self._previous_generated_ids[signature] = resolved
        return resolved

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

    def get_rule_ids(self) -> list[str]:
        """Return current ordered rule IDs."""
        return list(self._rule_id_to_index)

    def consume_rule_set_changed(self) -> bool:
        """Return and clear the rule-set changed marker."""
        changed = self._rule_ids_changed
        self._rule_ids_changed = False
        return changed

    def resolve_rule_index(self, index_or_rule_id: int | str) -> int:
        """Resolve index or rule_id into current index."""
        if isinstance(index_or_rule_id, int):
            index = index_or_rule_id
        else:
            if index_or_rule_id not in self._rule_id_to_index:
                msg = f"Unknown rule_id: {index_or_rule_id}"
                raise ValueError(msg)
            index = self._rule_id_to_index[index_or_rule_id]

        schedules = self.data or []
        if index < 0 or index >= len(schedules):
            msg = f"Schedule index out of range: {index}"
            raise ValueError(msg)
        return index

    def _deepcopy_schedules(self) -> list[dict[str, Any]]:
        """Return deep copy of current schedules."""
        return deepcopy(self.data or [])

    async def _async_write_schedules(self, schedules: list[dict[str, Any]]) -> None:
        """Validate and write full schedule list, then refresh."""
        validated = [validate_schedule(schedule) for schedule in schedules]
        try:
            await self.hass.async_add_executor_job(self._blocking_post, validated)
        except requests.RequestException as err:
            msg = f"Failed to update schedules: {err}"
            raise UpdateFailed(msg) from err
        await self.async_refresh()

    async def _async_update_rule(
        self,
        index_or_rule_id: int | str,
        mutator: Any,
    ) -> None:
        """Read-modify-write helper that updates exactly one rule."""
        schedules = self._deepcopy_schedules()
        index = self.resolve_rule_index(index_or_rule_id)
        mutator(schedules[index])
        await self._async_write_schedules(schedules)

    async def async_set_active(
        self, index_or_rule_id: int | str, *, active: bool
    ) -> None:
        """
        Toggle the Active flag on one schedule entry and push the full list back.

        The inverter's API only supports writing the full list of schedules,
        so we read-modify-write the entire list here.
        """
        await self._async_update_rule(
            index_or_rule_id,
            lambda rule: rule.__setitem__("Active", bool(active)),
        )

    async def async_set_power(self, index_or_rule_id: int | str, power: int) -> None:
        """Update a rule power value."""
        _ensure_power(power)
        await self._async_update_rule(
            index_or_rule_id,
            lambda rule: rule.__setitem__("Power", int(power)),
        )

    async def async_set_schedule_type(
        self,
        index_or_rule_id: int | str,
        schedule_type: str,
    ) -> None:
        """Update a rule schedule type."""
        _ensure_schedule_type(schedule_type)
        await self._async_update_rule(
            index_or_rule_id,
            lambda rule: rule.__setitem__("ScheduleType", schedule_type),
        )

    async def async_set_start_time(
        self, index_or_rule_id: int | str, start: str
    ) -> None:
        """Update a rule start time."""
        _ensure_time(start, field="start")
        await self._async_update_rule(
            index_or_rule_id,
            lambda rule: rule.setdefault("TimeTable", {}).__setitem__("Start", start),
        )

    async def async_set_end_time(self, index_or_rule_id: int | str, end: str) -> None:
        """Update a rule end time."""
        _ensure_time(end, field="end")
        await self._async_update_rule(
            index_or_rule_id,
            lambda rule: rule.setdefault("TimeTable", {}).__setitem__("End", end),
        )

    async def async_set_weekday(
        self,
        index_or_rule_id: int | str,
        day: str,
        *,
        enabled: bool,
    ) -> None:
        """Update one weekday flag for a rule."""
        if day not in WEEKDAYS:
            msg = f"Invalid weekday: {day}"
            raise ValueError(msg)
        await self._async_update_rule(
            index_or_rule_id,
            lambda rule: rule.setdefault("Weekdays", {}).__setitem__(
                day, bool(enabled)
            ),
        )

    async def async_add_schedule(self, schedule: dict[str, Any]) -> None:
        """Append a new schedule and write back the full list."""
        schedules = self._deepcopy_schedules()
        schedules.append(validate_schedule(schedule))
        await self._async_write_schedules(schedules)

    async def async_remove_schedule(self, index_or_rule_id: int | str) -> None:
        """Remove one schedule by index or rule ID and write back."""
        schedules = self._deepcopy_schedules()
        index = self.resolve_rule_index(index_or_rule_id)
        schedules.pop(index)
        await self._async_write_schedules(schedules)

    def test_connection_blocking(self) -> list[dict]:
        """Test connection by performing a single GET request."""
        return self._blocking_get()
