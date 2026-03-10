"""Tests for integration lifecycle and services."""

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.fronius_tdc import (
    DATA_BATTERIES,
    DATA_SERVICES_REGISTERED,
    _add_schedule_schema,
    _parse_hhmm,
    _register_services,
    _unregister_services,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.fronius_tdc.const import (
    DOMAIN,
    SERVICE_ADD_SCHEDULE,
    SERVICE_REMOVE_SCHEDULE,
)
from custom_components.fronius_tdc.tdc_coordinator import FroniusTDCCoordinator


@pytest.mark.asyncio
@patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
@patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
async def test_setup_registers_services(mock_tdc_cls, mock_batteries_cls) -> None:
    """Test setup registers integration services for add/remove schedule."""
    tdc = AsyncMock()
    tdc.async_config_entry_first_refresh = AsyncMock()
    mock_tdc_cls.return_value = tdc

    batteries = AsyncMock()
    batteries.async_config_entry_first_refresh = AsyncMock()
    mock_batteries_cls.return_value = batteries

    hass = AsyncMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()

    entry = MagicMock(entry_id="entry1")
    entry.async_on_unload = MagicMock(return_value=AsyncMock())
    entry.add_update_listener = MagicMock()

    assert await async_setup_entry(hass, entry)

    assert DOMAIN in hass.data
    registered = [call.args[1] for call in hass.services.async_register.call_args_list]
    assert SERVICE_ADD_SCHEDULE in registered
    assert SERVICE_REMOVE_SCHEDULE in registered


@pytest.mark.asyncio
async def test_unload_removes_services() -> None:
    """Test unloading the last entry unregisters the integration services."""
    hass = AsyncMock()
    hass.data = {
        DOMAIN: {
            "entry1": MagicMock(),
            "services_registered": True,
            "batteries_coordinator": {"entry1": MagicMock()},
        }
    }
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_remove = MagicMock()

    entry = MagicMock(entry_id="entry1")

    assert await async_unload_entry(hass, entry)
    removed = [call.args[1] for call in hass.services.async_remove.call_args_list]
    assert SERVICE_ADD_SCHEDULE in removed
    assert SERVICE_REMOVE_SCHEDULE in removed


@pytest.mark.asyncio
async def test_add_schedule_service() -> None:
    """Test that add_schedule service calls coordinator method."""
    tdc = AsyncMock(spec=FroniusTDCCoordinator)
    tdc.async_add_schedule = AsyncMock()

    hass = AsyncMock()
    hass.data = {DOMAIN: {"entry1": tdc, DATA_BATTERIES: {}}}
    # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()

    _register_services(hass)

    # Get the registered service handler
    add_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_ADD_SCHEDULE
    )
    service_handler = add_schedule_call.args[2]

    # Call the service
    call_data = MagicMock()
    call_data.data = {
        "active": True,
        "schedule_type": "CHARGE_MAX",
        "power": 5000,
        "start": "22:00",
        "end": "06:00",
        "weekdays": {
            "Mon": True,
            "Tue": True,
            "Wed": True,
            "Thu": True,
            "Fri": True,
            "Sat": False,
            "Sun": False,
        },
    }

    await service_handler(call_data)

    # Verify coordinator method was called
    tdc.async_add_schedule.assert_called_once()
    schedule = tdc.async_add_schedule.call_args[0][0]
    assert schedule["Active"] is True
    assert schedule["ScheduleType"] == "CHARGE_MAX"
    assert schedule["Power"] == 5000
    assert schedule["TimeTable"]["Start"] == "22:00"
    assert schedule["TimeTable"]["End"] == "06:00"


@pytest.mark.asyncio
async def test_add_schedule_service_with_time_object() -> None:
    """Test that add_schedule service handles time objects."""
    tdc = AsyncMock(spec=FroniusTDCCoordinator)
    tdc.async_add_schedule = AsyncMock()

    hass = AsyncMock()
    hass.data = {
        DOMAIN: {"entry1": tdc, DATA_BATTERIES: {}}
    }  # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()
    _register_services(hass)

    # Get the registered service handler
    add_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_ADD_SCHEDULE
    )
    service_handler = add_schedule_call.args[2]

    # Call the service with time objects
    call_data = MagicMock()
    call_data.data = {
        "active": False,
        "schedule_type": "DISCHARGE_MAX",
        "power": 3000,
        "start": time(8, 30),
        "end": time(17, 45),
        "weekdays": {
            "Mon": True,
            "Tue": False,
            "Wed": False,
            "Thu": False,
            "Fri": False,
            "Sat": False,
            "Sun": False,
        },
    }

    await service_handler(call_data)

    # Verify time objects were converted to HH:MM format
    tdc.async_add_schedule.assert_called_once()
    schedule = tdc.async_add_schedule.call_args[0][0]
    assert schedule["TimeTable"]["Start"] == "08:30"
    assert schedule["TimeTable"]["End"] == "17:45"


@pytest.mark.asyncio
async def test_remove_schedule_service_with_rule_id() -> None:
    """Test that remove_schedule service calls coordinator with rule_id."""
    tdc = AsyncMock(spec=FroniusTDCCoordinator)
    tdc.async_remove_schedule = AsyncMock()

    hass = AsyncMock()
    hass.data = {
        DOMAIN: {"entry1": tdc, DATA_BATTERIES: {}}
    }  # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()
    _register_services(hass)

    # Get the registered service handler
    remove_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_REMOVE_SCHEDULE
    )
    service_handler = remove_schedule_call.args[2]

    # Call the service with rule_id
    call_data = MagicMock()
    call_data.data = {"rule_id": "rule_123"}

    await service_handler(call_data)

    # Verify coordinator method was called with rule_id
    tdc.async_remove_schedule.assert_called_once_with("rule_123")


@pytest.mark.asyncio
async def test_remove_schedule_service_with_index() -> None:
    """Test that remove_schedule service calls coordinator with index."""
    tdc = AsyncMock(spec=FroniusTDCCoordinator)
    tdc.async_remove_schedule = AsyncMock()

    hass = AsyncMock()
    hass.data = {
        DOMAIN: {"entry1": tdc, DATA_BATTERIES: {}}
    }  # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()
    _register_services(hass)

    # Get the registered service handler
    remove_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_REMOVE_SCHEDULE
    )
    service_handler = remove_schedule_call.args[2]

    # Call the service with index
    call_data = MagicMock()
    call_data.data = {"index": 2}

    await service_handler(call_data)

    # Verify coordinator method was called with index (converted to int)
    tdc.async_remove_schedule.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_remove_schedule_service_missing_params() -> None:
    """Test remove_schedule fails when both rule_id and index are missing."""
    tdc = AsyncMock(spec=FroniusTDCCoordinator)
    tdc.async_remove_schedule = AsyncMock()

    hass = AsyncMock()
    hass.data = {DOMAIN: {"entry1": tdc, DATA_BATTERIES: {}}}
    # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()

    _register_services(hass)

    # Get the registered service handler
    remove_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_REMOVE_SCHEDULE
    )
    service_handler = remove_schedule_call.args[2]

    # Call the service without rule_id or index
    call_data = MagicMock()
    call_data.data = {}

    with pytest.raises(vol.Invalid, match="Either rule_id or index is required"):
        await service_handler(call_data)


@pytest.mark.asyncio
async def test_service_with_explicit_config_entry_id() -> None:
    """Test that services work with explicit config_entry_id."""
    tdc1 = AsyncMock(spec=FroniusTDCCoordinator)
    tdc1.async_add_schedule = AsyncMock()

    tdc2 = AsyncMock(spec=FroniusTDCCoordinator)
    tdc2.async_add_schedule = AsyncMock()

    hass = AsyncMock()
    hass.data = {DOMAIN: {"entry1": tdc1, "entry2": tdc2, DATA_BATTERIES: {}}}
    # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()

    _register_services(hass)

    # Get the registered service handler
    add_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_ADD_SCHEDULE
    )
    service_handler = add_schedule_call.args[2]

    # Call the service targeting entry2 specifically
    call_data = MagicMock()
    call_data.data = {
        "config_entry_id": "entry2",
        "active": True,
        "schedule_type": "CHARGE_MAX",
        "power": 5000,
        "start": "22:00",
        "end": "06:00",
        "weekdays": {
            "Mon": True,
            "Tue": False,
            "Wed": False,
            "Thu": False,
            "Fri": False,
            "Sat": False,
            "Sun": False,
        },
    }

    await service_handler(call_data)

    # Verify only tdc2 was called
    tdc1.async_add_schedule.assert_not_called()
    tdc2.async_add_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_service_multiple_entries_without_config_entry_id() -> None:
    """Test services fail without config_entry_id when multiple entries exist."""
    tdc1 = AsyncMock(spec=FroniusTDCCoordinator)
    tdc2 = AsyncMock(spec=FroniusTDCCoordinator)

    hass = AsyncMock()
    hass.data = {DOMAIN: {"entry1": tdc1, "entry2": tdc2, DATA_BATTERIES: {}}}
    # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()

    _register_services(hass)

    # Get the registered service handler
    add_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_ADD_SCHEDULE
    )
    service_handler = add_schedule_call.args[2]

    # Call the service without config_entry_id
    call_data = MagicMock()
    call_data.data = {
        "active": True,
        "schedule_type": "CHARGE_MAX",
        "power": 5000,
        "start": "22:00",
        "end": "06:00",
        "weekdays": {
            "Mon": True,
            "Tue": False,
            "Wed": False,
            "Thu": False,
            "Fri": False,
            "Sat": False,
            "Sun": False,
        },
    }

    with pytest.raises(
        vol.Invalid,
        match="config_entry_id is required when multiple entries are configured",
    ):
        await service_handler(call_data)


@pytest.mark.asyncio
async def test_service_with_invalid_config_entry_id() -> None:
    """Test that services raise error with unknown config_entry_id."""
    tdc = AsyncMock(spec=FroniusTDCCoordinator)

    hass = AsyncMock()
    hass.data = {DOMAIN: {"entry1": tdc, DATA_BATTERIES: {}}}
    # Configure services mocks to avoid RuntimeWarnings
    hass.services.async_register = MagicMock()

    _register_services(hass)

    # Get the registered service handler
    add_schedule_call = next(
        call
        for call in hass.services.async_register.call_args_list
        if call.args[1] == SERVICE_ADD_SCHEDULE
    )
    service_handler = add_schedule_call.args[2]

    # Call the service with invalid config_entry_id
    call_data = MagicMock()
    call_data.data = {
        "config_entry_id": "invalid_entry",
        "active": True,
        "schedule_type": "CHARGE_MAX",
        "power": 5000,
        "start": "22:00",
        "end": "06:00",
        "weekdays": {
            "Mon": True,
            "Tue": False,
            "Wed": False,
            "Thu": False,
            "Fri": False,
            "Sat": False,
            "Sun": False,
        },
    }

    with pytest.raises(
        vol.Invalid,
        match="Unknown config_entry_id: invalid_entry",
    ):
        await service_handler(call_data)


@pytest.mark.asyncio
async def test_parse_hhmm_with_invalid_type() -> None:
    """Test _parse_hhmm raises error with invalid type."""
    # Test with invalid type (not str or time)
    with pytest.raises(vol.Invalid, match="Invalid time value"):
        _parse_hhmm(12345)  # Integer is not valid

    with pytest.raises(vol.Invalid, match="Invalid time value"):
        _parse_hhmm(None)  # None is not valid


@pytest.mark.asyncio
async def test_add_schedule_schema_invalid_weekdays() -> None:
    """Test _add_schedule_schema raises error when weekdays is not a dict."""
    data = {
        "active": True,
        "schedule_type": "CHARGE_MAX",
        "power": 5000,
        "start": "22:00",
        "end": "06:00",
        "weekdays": "invalid_not_a_dict",  # Should be dict
    }

    with pytest.raises(vol.Invalid, match="weekdays must be an object"):
        _add_schedule_schema(data)


@pytest.mark.asyncio
async def test_register_services_idempotent() -> None:
    """Test _register_services is idempotent - doesn't register twice."""
    hass = AsyncMock()
    hass.data = {DOMAIN: {}}
    hass.services.async_register = MagicMock()

    # First registration
    _register_services(hass)
    first_call_count = hass.services.async_register.call_count
    assert first_call_count == 2  # add_schedule and remove_schedule

    # Second registration should not register again
    _register_services(hass)
    assert hass.services.async_register.call_count == first_call_count


@pytest.mark.asyncio
async def test_unregister_services_when_services_exist() -> None:
    """Test _unregister_services removes services when they exist."""
    hass = AsyncMock()
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_remove = MagicMock()

    _unregister_services(hass)

    # Should check for both services
    assert hass.services.has_service.call_count == 2
    # Should remove both services
    assert hass.services.async_remove.call_count == 2

    removed = [call.args[1] for call in hass.services.async_remove.call_args_list]
    assert SERVICE_ADD_SCHEDULE in removed
    assert SERVICE_REMOVE_SCHEDULE in removed


@pytest.mark.asyncio
async def test_unregister_services_when_services_dont_exist() -> None:
    """Test _unregister_services handles case when services don't exist."""
    hass = AsyncMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_remove = MagicMock()

    _unregister_services(hass)

    # Should check for both services
    assert hass.services.has_service.call_count == 2
    # Should not remove any services
    assert hass.services.async_remove.call_count == 0


@pytest.mark.asyncio
async def test_unload_entry_cleans_up_batteries_coordinator() -> None:
    """Test async_unload_entry cleans up batteries coordinator data."""
    hass = AsyncMock()
    batteries_dict = {"entry1": MagicMock(), "entry2": MagicMock()}
    hass.data = {
        DOMAIN: {
            "entry1": MagicMock(),
            "entry2": MagicMock(),  # Another entry still exists
            DATA_SERVICES_REGISTERED: True,
            DATA_BATTERIES: batteries_dict,
        }
    }
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    # Configure services mocks to avoid RuntimeWarnings
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_remove = MagicMock()

    entry = MagicMock(entry_id="entry1")

    result = await async_unload_entry(hass, entry)

    assert result is True
    # Should remove entry1 from batteries
    assert "entry1" not in batteries_dict
    # Should still have entry2
    assert "entry2" in batteries_dict


@pytest.mark.asyncio
async def test_unload_last_entry_unregisters_services() -> None:
    """Test async_unload_entry unregisters services when last entry is removed."""
    hass = AsyncMock()
    domain_data = {
        "entry1": MagicMock(),
        DATA_SERVICES_REGISTERED: True,
        DATA_BATTERIES: {"entry1": MagicMock()},
    }
    hass.data = {DOMAIN: domain_data}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    # Configure services mocks to avoid RuntimeWarnings
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_remove = MagicMock()

    entry = MagicMock(entry_id="entry1")

    result = await async_unload_entry(hass, entry)

    assert result is True
    # Should have unregistered services
    assert hass.services.async_remove.call_count == 2
    # Should have removed the services_registered flag
    assert DATA_SERVICES_REGISTERED not in domain_data


@pytest.mark.asyncio
async def test_add_schedule_schema_valid_data() -> None:
    """Test _add_schedule_schema accepts valid payload and returns original data."""
    data = {
        "active": True,
        "schedule_type": "CHARGE_MAX",
        "power": 5000,
        "start": time(22, 0),
        "end": "06:00",
        "weekdays": {
            "Mon": True,
            "Tue": True,
            "Wed": True,
            "Thu": True,
            "Fri": True,
            "Sat": False,
            "Sun": False,
        },
    }

    assert _add_schedule_schema(data) == data


@pytest.mark.asyncio
async def test_unload_entry_returns_false_when_platform_unload_fails() -> None:
    """Test async_unload_entry returns False when platform unload fails."""
    hass = AsyncMock()
    hass.data = {
        DOMAIN: {"entry1": MagicMock(), DATA_BATTERIES: {"entry1": MagicMock()}}
    }
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_remove = MagicMock()
    entry = MagicMock(entry_id="entry1")

    result = await async_unload_entry(hass, entry)

    assert result is False
    hass.services.async_remove.assert_not_called()


@pytest.mark.asyncio
async def test_unload_entry_keeps_services_when_other_coordinator_exists() -> None:
    """Test unload keeps services when another coordinator remains."""
    hass = AsyncMock()
    domain_data = {
        "entry1": MagicMock(),
        "entry2": MagicMock(),
        DATA_SERVICES_REGISTERED: True,
        DATA_BATTERIES: ["not", "a", "dict"],
    }
    hass.data = {DOMAIN: domain_data}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_remove = MagicMock()
    entry = MagicMock(entry_id="entry1")

    with patch(
        "custom_components.fronius_tdc._coordinator_items",
        return_value={"entry2": object()},
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    assert "entry2" in domain_data
    assert DATA_SERVICES_REGISTERED in domain_data
    hass.services.async_remove.assert_not_called()


@pytest.mark.asyncio
async def test_reload_entry_calls_config_reload() -> None:
    """Test async_reload_entry delegates to Home Assistant config reload."""
    hass = AsyncMock()
    hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock(entry_id="entry1")

    await async_reload_entry(hass, entry)

    hass.config_entries.async_reload.assert_called_once_with("entry1")
