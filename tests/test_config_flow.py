"""Tests for config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from custom_components.fronius_tdc.config_flow import (
    BlueprintFlowHandler,
    _test_connection_blocking,
)
from custom_components.fronius_tdc.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)


class TestTestConnectionBlocking:
    """Test _test_connection_blocking function."""

    @patch("custom_components.fronius_tdc.config_flow.fronius_get_json")
    def test_successful_connection(self, mock_get) -> None:
        """Test successful connection."""
        mock_get.return_value = {"timeofuse": []}

        result = _test_connection_blocking("192.168.1.1", 80, "customer", "password")

        assert result is None
        mock_get.assert_called_once()

    @patch("custom_components.fronius_tdc.config_flow.fronius_get_json")
    def test_connection_invalid_auth(self, mock_get) -> None:
        """Test invalid credentials."""
        error = requests.HTTPError("401 Unauthorized")
        error.response = Mock()
        error.response.status_code = 401
        mock_get.side_effect = error

        result = _test_connection_blocking("192.168.1.1", 80, "customer", "wrongpass")

        assert result == "invalid_auth"

    @patch("custom_components.fronius_tdc.config_flow.fronius_get_json")
    def test_connection_forbidden(self, mock_get) -> None:
        """Test 403 Forbidden."""
        error = requests.HTTPError("403 Forbidden")
        error.response = Mock()
        error.response.status_code = 403
        mock_get.side_effect = error

        result = _test_connection_blocking("192.168.1.1", 80, "customer", "password")

        assert result == "invalid_auth"

    @patch("custom_components.fronius_tdc.config_flow.fronius_get_json")
    def test_connection_cannot_reach(self, mock_get) -> None:
        """Test connection error."""
        mock_get.side_effect = requests.ConnectionError("Cannot reach host")

        result = _test_connection_blocking("192.168.1.1", 80, "customer", "password")

        assert result == "cannot_connect"

    @patch("custom_components.fronius_tdc.config_flow.fronius_get_json")
    def test_connection_timeout(self, mock_get) -> None:
        """Test request timeout."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        result = _test_connection_blocking("192.168.1.1", 80, "customer", "password")

        assert result == "cannot_connect"

    @patch("custom_components.fronius_tdc.config_flow.fronius_get_json")
    def test_connection_http_error_500(self, mock_get) -> None:
        """Test 500 server error."""
        error = requests.HTTPError("500 Internal Server Error")
        error.response = Mock()
        error.response.status_code = 500
        mock_get.side_effect = error

        result = _test_connection_blocking("192.168.1.1", 80, "customer", "password")

        assert result == "cannot_connect"

    @patch("custom_components.fronius_tdc.config_flow.fronius_get_json")
    def test_connection_unexpected_error(self, mock_get) -> None:
        """Test unexpected error."""
        mock_get.side_effect = ValueError("Unexpected error")

        result = _test_connection_blocking("192.168.1.1", 80, "customer", "password")

        assert result == "cannot_connect"


class TestBlueprintFlowHandler:
    """Test BlueprintFlowHandler config flow."""

    @pytest.fixture
    def flow_handler(self):
        """Create a config flow handler."""
        return BlueprintFlowHandler()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.config_flow._test_connection_blocking")
    async def test_async_step_user_success(self, mock_test, flow_handler) -> None:
        """Test successful config flow."""
        mock_test.return_value = None
        flow_handler.async_set_unique_id = AsyncMock()
        flow_handler._abort_if_unique_id_configured = Mock()
        flow_handler.async_create_entry = Mock()

        user_input = {
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 80,
            CONF_USERNAME: "customer",
            CONF_PASSWORD: "password",
        }

        flow_handler.hass = AsyncMock()
        flow_handler.hass.async_add_executor_job = AsyncMock(return_value=None)

        await flow_handler.async_step_user(user_input)

        flow_handler.async_set_unique_id.assert_called_once_with(
            "fronius_tdc_192.168.1.1"
        )
        flow_handler.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.config_flow._test_connection_blocking")
    async def test_async_step_user_invalid_auth(self, mock_test, flow_handler) -> None:
        """Test config flow with invalid auth."""
        mock_test.return_value = "invalid_auth"
        flow_handler.async_show_form = Mock()

        user_input = {
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 80,
            CONF_USERNAME: "customer",
            CONF_PASSWORD: "wrongpass",
        }

        flow_handler.hass = AsyncMock()
        flow_handler.hass.async_add_executor_job = AsyncMock(
            return_value="invalid_auth"
        )

        await flow_handler.async_step_user(user_input)

        flow_handler.async_show_form.assert_called_once()
        form_kwargs = flow_handler.async_show_form.call_args[1]
        assert form_kwargs["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    @patch("custom_components.fronius_tdc.config_flow._test_connection_blocking")
    async def test_async_step_user_cannot_connect(
        self, mock_test, flow_handler
    ) -> None:
        """Test config flow when cannot connect."""
        mock_test.return_value = "cannot_connect"
        flow_handler.async_show_form = Mock()

        user_input = {
            CONF_HOST: "192.168.99.99",
            CONF_PORT: 80,
            CONF_USERNAME: "customer",
            CONF_PASSWORD: "password",
        }

        flow_handler.hass = AsyncMock()
        flow_handler.hass.async_add_executor_job = AsyncMock(
            return_value="cannot_connect"
        )

        await flow_handler.async_step_user(user_input)

        flow_handler.async_show_form.assert_called_once()
        form_kwargs = flow_handler.async_show_form.call_args[1]
        assert form_kwargs["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_async_step_user_no_input(self, flow_handler) -> None:
        """Test config flow without user input."""
        flow_handler.async_show_form = Mock()
        flow_handler.hass = AsyncMock()

        await flow_handler.async_step_user(None)

        flow_handler.async_show_form.assert_called_once()
        assert flow_handler.async_show_form.call_args[1]["step_id"] == "user"
