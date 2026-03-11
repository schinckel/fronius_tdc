"""Tests for time entities."""

from __future__ import annotations

from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fronius_tdc.const import (
    DOMAIN,
    SCHEDULE_END_TIME_DESCRIPTION,
    SCHEDULE_START_TIME_DESCRIPTION,
)
from custom_components.fronius_tdc.time import (
    FroniusScheduleTimeEntity,
    async_setup_entry,
)


class TestFroniusScheduleTimeEntity:
    """Test FroniusScheduleTimeEntity entity."""

    @pytest.fixture
    def coordinator_mock(self):
        """Create a mock TOU coordinator."""
        coordinator = MagicMock()
        coordinator.data = [
            {
                "TimeTable": {"Start": "18:00", "End": "21:00"},
                "Weekdays": {
                    "Mon": True,
                    "Tue": True,
                    "Wed": True,
                    "Thu": True,
                    "Fri": True,
                    "Sat": True,
                    "Sun": True,
                },
            }
        ]
        return coordinator

    @pytest.fixture
    def config_entry_mock(self):
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_123"
        entry.title = "Test Inverter"
        return entry

    def test_start_entity_initialization(self, coordinator_mock, config_entry_mock):
        """Test start time entity initialization and state."""
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        assert entity._attr_unique_id == "test_entry_123_schedule_0_start_time"
        assert entity.entity_id == "time.test_inverter_schedule_0_start_time"
        assert entity.name == "Schedule 1 Start"
        assert entity.native_value == dt_time(18, 0)

    def test_end_entity_initialization(self, coordinator_mock, config_entry_mock):
        """Test end time entity initialization and state."""
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_END_TIME_DESCRIPTION,
        )

        assert entity._attr_unique_id == "test_entry_123_schedule_0_end_time"
        assert entity.entity_id == "time.test_inverter_schedule_0_end_time"
        assert entity.name == "Schedule 1 End"
        assert entity.native_value == dt_time(21, 0)

    @pytest.mark.asyncio
    async def test_start_set_value(self, coordinator_mock, config_entry_mock) -> None:
        """Test setting start time dispatches HH:MM string."""
        coordinator_mock.async_set_start_time = AsyncMock()
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        await entity.async_set_value(dt_time(9, 30))

        coordinator_mock.async_set_start_time.assert_called_once_with(
            index=0,
            start="09:30",
        )

    @pytest.mark.asyncio
    async def test_end_set_value(self, coordinator_mock, config_entry_mock) -> None:
        """Test setting end time dispatches HH:MM string."""
        coordinator_mock.async_set_end_time = AsyncMock()
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_END_TIME_DESCRIPTION,
        )

        await entity.async_set_value(dt_time(23, 59))

        coordinator_mock.async_set_end_time.assert_called_once_with(
            index=0,
            end="23:59",
        )

    @pytest.mark.asyncio
    async def test_set_value_rejects_seconds(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test seconds precision is rejected at entity boundary."""
        coordinator_mock.async_set_start_time = AsyncMock()
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        with pytest.raises(ValueError, match="HH:MM"):
            await entity.async_set_value(dt_time(10, 30, 45))

        coordinator_mock.async_set_start_time.assert_not_called()

    def test_native_value_out_of_range_index_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None when schedule index is out of range."""
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            5,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        assert entity.native_value is None

    def test_native_value_missing_timetable_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None when TimeTable is not a dict."""
        coordinator_mock.data = [{"TimeTable": None}]
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        assert entity.native_value is None

    def test_native_value_non_string_time_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None for non-string time values."""
        coordinator_mock.data = [{"TimeTable": {"Start": 930, "End": "21:00"}}]
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        assert entity.native_value is None

    def test_native_value_bad_format_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None for malformed HH:MM strings."""
        coordinator_mock.data = [{"TimeTable": {"Start": "09-30", "End": "21:00"}}]
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        assert entity.native_value is None

    def test_native_value_non_numeric_parts_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None for non-numeric HH:MM parts."""
        coordinator_mock.data = [{"TimeTable": {"Start": "xx:yy", "End": "21:00"}}]
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        assert entity.native_value is None

    def test_native_value_out_of_range_clock_returns_none(
        self, coordinator_mock, config_entry_mock
    ) -> None:
        """Test native_value returns None for invalid clock values."""
        coordinator_mock.data = [{"TimeTable": {"Start": "24:30", "End": "21:00"}}]
        entity = FroniusScheduleTimeEntity(
            coordinator_mock,
            config_entry_mock,
            0,
            SCHEDULE_START_TIME_DESCRIPTION,
        )

        assert entity.native_value is None


class TestAsyncSetupEntry:
    """Test time async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_entities(self) -> None:
        """Test setup creates start/end entities for each schedule."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.data = [
            {"TimeTable": {"Start": "06:00", "End": "08:00"}},
            {"TimeTable": {"Start": "20:00", "End": "22:00"}},
        ]

        hass.data = {DOMAIN: {config_entry.entry_id: coordinator}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        coordinator.async_config_entry_first_refresh.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 4
        assert all(isinstance(e, FroniusScheduleTimeEntity) for e in entities)

    @pytest.mark.asyncio
    async def test_async_setup_entry_without_coordinator(self) -> None:
        """Test setup returns early when no TOU coordinator exists."""
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"

        hass.data = {DOMAIN: {}}
        async_add_entities = MagicMock()

        await async_setup_entry(hass, config_entry, async_add_entities)

        async_add_entities.assert_not_called()
