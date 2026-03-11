"""Tests for the integration lifecycle (__init__.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.fronius_tdc import (
    _async_handle_add_schedule,
    _async_handle_remove_schedule,
    _async_unregister_services_if_unused,
    _build_schedule_from_service,
    _resolve_service_target,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.fronius_tdc.const import (
    DOMAIN,
    SERVICE_ADD_SCHEDULE,
    SERVICE_REMOVE_SCHEDULE,
)


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_creates_coordinator(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that setup creates a coordinator and stores it."""
        # Setup mocks
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.async_register = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_123"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        # Call setup
        result = await async_setup_entry(hass, config_entry)

        # Verify result
        assert result is True

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_stores_coordinator_in_hass_data(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that coordinator is stored in hass.data[DOMAIN]."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.async_register = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify coordinator is stored
        assert DOMAIN in hass.data
        assert hass.data[DOMAIN]["entry_1"] is mock_tdc

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_calls_first_refresh(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that first_refresh is called during setup."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.async_register = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify first_refresh was called
        mock_tdc.async_config_entry_first_refresh.assert_called_once()
        mock_batteries.async_config_entry_first_refresh.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_forwards_entry_setups(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that entry setup forwards to platforms."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.async_register = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify platforms are setup
        hass.config_entries.async_forward_entry_setups.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_registers_update_listener(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test that update listener is registered."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.async_register = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry)

        # Verify update listener is added
        config_entry.add_update_listener.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_multiple_entries(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test setup with multiple config entries."""
        mock_tdc1 = AsyncMock()
        mock_tdc1.async_config_entry_first_refresh = AsyncMock()
        mock_tdc2 = AsyncMock()
        mock_tdc2.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.side_effect = [mock_tdc1, mock_tdc2]

        mock_batteries1 = AsyncMock()
        mock_batteries1.async_config_entry_first_refresh = AsyncMock()
        mock_batteries2 = AsyncMock()
        mock_batteries2.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.side_effect = [
            mock_batteries1,
            mock_batteries2,
        ]

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.services.async_register = MagicMock()

        config_entry1 = MagicMock()
        config_entry1.entry_id = "entry_1"
        config_entry1.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry1.add_update_listener = MagicMock()

        config_entry2 = MagicMock()
        config_entry2.entry_id = "entry_2"
        config_entry2.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry2.add_update_listener = MagicMock()

        # Setup both entries
        await async_setup_entry(hass, config_entry1)
        await async_setup_entry(hass, config_entry2)

        # Verify both are stored
        assert hass.data[DOMAIN]["entry_1"] is mock_tdc1
        assert hass.data[DOMAIN]["entry_2"] is mock_tdc2
        assert hass.services.async_register.call_count == 2

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_async_setup_entry_registers_schedule_services_once(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test domain services are only registered on first setup."""
        mock_tdc_coordinator_class.return_value = AsyncMock(
            async_config_entry_first_refresh=AsyncMock()
        )
        mock_batteries_coordinator_class.return_value = AsyncMock(
            async_config_entry_first_refresh=AsyncMock()
        )

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.services.async_register = MagicMock()

        config_entry1 = MagicMock(entry_id="entry_1")
        config_entry1.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry1.add_update_listener = MagicMock()
        config_entry2 = MagicMock(entry_id="entry_2")
        config_entry2.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry2.add_update_listener = MagicMock()

        await async_setup_entry(hass, config_entry1)
        await async_setup_entry(hass, config_entry2)

        assert hass.services.async_register.call_count == 2
        assert (
            hass.services.async_register.call_args_list[0].args[1]
            == SERVICE_ADD_SCHEDULE
        )
        assert (
            hass.services.async_register.call_args_list[1].args[1]
            == SERVICE_REMOVE_SCHEDULE
        )


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    @pytest.mark.asyncio
    async def test_async_unload_entry_unloads_platforms(self):
        """Test that unload removes entry platforms."""
        hass = AsyncMock()
        hass.data = {
            DOMAIN: {
                "entry_1": MagicMock(),
                "batteries_coordinator": {"entry_1": MagicMock()},
                "services_registered": True,
            }
        }
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services.async_remove = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        hass.config_entries.async_unload_platforms.assert_called_once_with(
            config_entry, ["switch", "number", "select"]
        )
        hass.services.async_remove.assert_any_call(DOMAIN, SERVICE_ADD_SCHEDULE)
        hass.services.async_remove.assert_any_call(DOMAIN, SERVICE_REMOVE_SCHEDULE)

    @pytest.mark.asyncio
    async def test_async_unload_entry_keeps_services_with_other_entries(self):
        """Test unload keeps services while another TDC entry remains."""
        hass = AsyncMock()
        hass.data = {
            DOMAIN: {
                "entry_1": MagicMock(),
                "entry_2": MagicMock(),
                "batteries_coordinator": {
                    "entry_1": MagicMock(),
                    "entry_2": MagicMock(),
                },
                "services_registered": True,
            }
        }
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services.async_remove = MagicMock()

        config_entry = MagicMock(entry_id="entry_1")

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        hass.services.async_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_unload_entry_handles_failure(self):
        """Test unload when platform unload fails."""
        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        result = await async_unload_entry(hass, config_entry)

        assert result is False


class TestAsyncReloadEntry:
    """Test async_reload_entry function."""

    @pytest.mark.asyncio
    async def test_async_reload_entry_reloads_config(self):
        """Test that reload triggers entry reload."""
        hass = AsyncMock()
        hass.config_entries.async_reload = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        await async_reload_entry(hass, config_entry)

        hass.config_entries.async_reload.assert_called_once_with("entry_1")

    @pytest.mark.asyncio
    async def test_async_reload_entry_return_value(self):
        """Test that reload doesn't return anything."""
        hass = AsyncMock()
        hass.config_entries.async_reload = AsyncMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"

        result = await async_reload_entry(hass, config_entry)

        assert result is None


class TestIntegrationLifecycle:
    """Integration tests for the full lifecycle."""

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_full_setup_unload_cycle(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test complete setup and unload cycle."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services.async_register = MagicMock()
        hass.services.async_remove = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        # Setup
        setup_result = await async_setup_entry(hass, config_entry)
        assert setup_result is True
        assert DOMAIN in hass.data

        # Unload
        unload_result = await async_unload_entry(hass, config_entry)
        assert unload_result is True

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.FroniusBatteriesCoordinator")
    @patch("custom_components.fronius_tdc.FroniusTDCCoordinator")
    async def test_setup_reload_cycle(
        self, mock_tdc_coordinator_class, mock_batteries_coordinator_class
    ):
        """Test setup followed by reload."""
        mock_tdc = AsyncMock()
        mock_tdc.async_config_entry_first_refresh = AsyncMock()
        mock_tdc_coordinator_class.return_value = mock_tdc

        mock_batteries = AsyncMock()
        mock_batteries.async_config_entry_first_refresh = AsyncMock()
        mock_batteries_coordinator_class.return_value = mock_batteries

        hass = AsyncMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.config_entries.async_reload = AsyncMock()
        hass.services.async_register = MagicMock()

        config_entry = MagicMock()
        config_entry.entry_id = "entry_1"
        config_entry.async_on_unload = MagicMock(return_value=AsyncMock())
        config_entry.add_update_listener = MagicMock()

        # Setup
        await async_setup_entry(hass, config_entry)

        # Reload
        await async_reload_entry(hass, config_entry)

        # Verify reload was called
        hass.config_entries.async_reload.assert_called_once()


class TestServiceHandlers:
    """Test add/remove schedule service handlers."""

    def test_resolve_service_target_without_entries(self):
        """Test service resolution fails when no TDC entries exist."""
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        call = MagicMock(data={})

        with pytest.raises(ServiceValidationError, match="No configured Fronius"):
            _resolve_service_target(hass, call)

    def test_resolve_service_target_requires_entry_id_for_multiple_entries(self):
        """Test service resolution requires config_entry_id with multiple entries."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "entry_1": MagicMock(),
                "entry_2": MagicMock(),
            }
        }
        call = MagicMock(data={})

        with pytest.raises(ServiceValidationError, match="config_entry_id is required"):
            _resolve_service_target(hass, call)

    def test_resolve_service_target_missing_entry_record(self):
        """Test service resolution fails if config entry lookup returns None."""
        coordinator = MagicMock()
        hass = MagicMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=None)
        call = MagicMock(data={"config_entry_id": "entry_1"})

        with pytest.raises(ServiceValidationError, match="Config entry not found"):
            _resolve_service_target(hass, call)

    def test_build_schedule_from_service(self):
        """Test service payload is converted into canonical weekday map."""
        call = MagicMock(
            data={
                "active": True,
                "schedule_type": "CHARGE_MAX",
                "power": 1000,
                "start": "08:00",
                "end": "09:00",
                "weekdays": ["Mon", "Wed"],
            }
        )

        result = _build_schedule_from_service(call)

        assert result["Weekdays"]["Mon"] is True
        assert result["Weekdays"]["Wed"] is True
        assert result["Weekdays"]["Tue"] is False

    @pytest.mark.asyncio
    async def test_add_schedule_service_reloads_entry(self):
        """Test add_schedule service writes and reloads the targeted entry."""
        coordinator = AsyncMock()
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        hass.config_entries.async_reload = AsyncMock()
        call = MagicMock(
            data={
                "schedule_type": "CHARGE_MAX",
                "start": "08:00",
                "end": "09:00",
                "weekdays": ["Mon"],
                "active": False,
                "power": 1000,
            }
        )

        await _async_handle_add_schedule(hass, call)

        coordinator.async_add_schedule.assert_called_once()
        hass.config_entries.async_reload.assert_called_once_with("entry_1")

    @pytest.mark.asyncio
    async def test_remove_schedule_service_reloads_entry(self):
        """Test remove_schedule service writes and reloads the targeted entry."""
        coordinator = AsyncMock()
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        hass.config_entries.async_reload = AsyncMock()
        call = MagicMock(data={"index": 1})

        await _async_handle_remove_schedule(hass, call)

        coordinator.async_remove_schedule.assert_called_once_with(1)
        hass.config_entries.async_reload.assert_called_once_with("entry_1")

    @pytest.mark.asyncio
    async def test_remove_schedule_service_invalid_target(self):
        """Test service rejects unknown config_entry_id."""
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": AsyncMock()}}
        hass.config_entries.async_get_entry = MagicMock(return_value=None)
        call = MagicMock(data={"config_entry_id": "missing", "index": 0})

        with pytest.raises(ServiceValidationError, match="Unknown config_entry_id"):
            await _async_handle_remove_schedule(hass, call)

    @pytest.mark.asyncio
    async def test_add_schedule_service_invalid_payload(self):
        """Test invalid schedule payloads surface as validation errors."""
        coordinator = AsyncMock()
        coordinator.async_add_schedule.side_effect = Exception(
            "Invalid schedule update during add schedule: bad time"
        )
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        call = MagicMock(
            data={
                "schedule_type": "CHARGE_MAX",
                "start": "99:00",
                "end": "09:00",
                "weekdays": ["Mon"],
                "active": False,
                "power": 1000,
            }
        )

        with pytest.raises(ServiceValidationError, match="Invalid schedule update"):
            await _async_handle_add_schedule(hass, call)

    @pytest.mark.asyncio
    async def test_add_schedule_service_wraps_unknown_error(self):
        """Test unknown add errors are wrapped as HomeAssistantError."""
        coordinator = AsyncMock()
        coordinator.async_add_schedule.side_effect = RuntimeError("boom")
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        call = MagicMock(
            data={
                "schedule_type": "CHARGE_MAX",
                "start": "08:00",
                "end": "09:00",
                "weekdays": ["Mon"],
                "active": False,
                "power": 1000,
            }
        )

        with pytest.raises(HomeAssistantError, match="boom"):
            await _async_handle_add_schedule(hass, call)

    @pytest.mark.asyncio
    async def test_remove_schedule_service_invalid_payload(self):
        """Test invalid remove requests surface as validation errors."""
        coordinator = AsyncMock()
        coordinator.async_remove_schedule.side_effect = Exception(
            "Schedule index 99 out of range"
        )
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        call = MagicMock(data={"index": 99})

        with pytest.raises(ServiceValidationError, match="out of range"):
            await _async_handle_remove_schedule(hass, call)

    @pytest.mark.asyncio
    async def test_add_schedule_service_reraises_homeassistant_error(self):
        """Test HomeAssistantError is passed through unchanged."""
        coordinator = AsyncMock()
        coordinator.async_add_schedule.side_effect = ServiceValidationError("bad")
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        call = MagicMock(
            data={
                "schedule_type": "CHARGE_MAX",
                "start": "08:00",
                "end": "09:00",
                "weekdays": ["Mon"],
                "active": False,
                "power": 1000,
            }
        )

        with pytest.raises(ServiceValidationError, match="bad"):
            await _async_handle_add_schedule(hass, call)

    @pytest.mark.asyncio
    async def test_remove_schedule_service_wraps_unknown_error(self):
        """Test unknown remove errors are wrapped as HomeAssistantError."""
        coordinator = AsyncMock()
        coordinator.async_remove_schedule.side_effect = RuntimeError("boom")
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        call = MagicMock(data={"index": 1})

        with pytest.raises(HomeAssistantError, match="boom"):
            await _async_handle_remove_schedule(hass, call)

    @pytest.mark.asyncio
    async def test_remove_schedule_service_reraises_homeassistant_error(self):
        """Test HomeAssistantError is passed through for remove service."""
        coordinator = AsyncMock()
        coordinator.async_remove_schedule.side_effect = ServiceValidationError("bad")
        entry = MagicMock(entry_id="entry_1")
        hass = AsyncMock()
        hass.data = {DOMAIN: {"entry_1": coordinator}}
        hass.config_entries.async_get_entry = MagicMock(return_value=entry)
        call = MagicMock(data={"index": 1})

        with pytest.raises(ServiceValidationError, match="bad"):
            await _async_handle_remove_schedule(hass, call)

    def test_async_unregister_services_if_unused_without_flag(self):
        """Test unregister helper is a no-op when services were never registered."""
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        hass.services.async_remove = MagicMock()

        _async_unregister_services_if_unused(hass)

        hass.services.async_remove.assert_not_called()
