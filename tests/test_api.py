"""Tests for the API module."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.fronius_tdc.api import (
    fronius_get_html,
    fronius_get_json,
    fronius_post_json,
    fronius_request,
)


class TestFroniusRequest:
    """Test fronius_request function."""

    @patch("custom_components.fronius_tdc.api.requests.request")
    def test_successful_request_without_auth(self, mock_request) -> None:
        """Test a successful request without authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_request.return_value = mock_response

        result = fronius_request(
            "GET",
            "http://192.168.1.1:80/api/test",
            "user",
            "pass",
        )

        assert result.status_code == 200
        mock_request.assert_called_once()

    @patch("custom_components.fronius_tdc.api.requests.request")
    @patch("custom_components.fronius_tdc.api._build_authorization")
    def test_retry_on_401_with_digest_auth(self, mock_auth, mock_request) -> None:
        """Test that 401 response triggers digest auth flow."""
        # First call returns 401
        response_401 = Mock()
        response_401.status_code = 401
        response_401.headers = {"x-www-authenticate": 'Digest realm="test"'}
        response_401.raise_for_status = Mock()

        # Second call (authenticated) returns 200
        response_200 = Mock()
        response_200.status_code = 200
        response_200.text = "<response data>"
        response_200.raise_for_status = Mock()

        mock_request.side_effect = [response_401, response_200]
        mock_auth.return_value = "Digest username=test"

        result = fronius_request(
            "GET",
            "http://192.168.1.1:80/api/test",
            "customer",
            "secret",
        )

        assert result.status_code == 200
        assert mock_request.call_count == 2
        mock_auth.assert_called_once()

    @patch("custom_components.fronius_tdc.api.requests.request")
    def test_http_error_raised(self, mock_request) -> None:
        """Test that HTTP errors are raised."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server error")
        mock_request.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            fronius_request(
                "GET",
                "http://192.168.1.1:80/api/test",
                "user",
                "pass",
            )

    @patch("custom_components.fronius_tdc.api.requests.request")
    def test_timeout_passed_through(self, mock_request) -> None:
        """Test custom timeout is respected."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        fronius_request(
            "GET",
            "http://192.168.1.1:80/api/test",
            "user",
            "pass",
            timeout=30,
        )

        _, kwargs = mock_request.call_args
        assert kwargs["timeout"] == 30


class TestFroniusGetJson:
    """Test fronius_get_json function."""

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_get_json(self, mock_request) -> None:
        """Test getting JSON from inverter."""
        mock_response = Mock()
        mock_response.json.return_value = {"timeofuse": []}
        mock_request.return_value = mock_response

        result = fronius_get_json(
            "http://192.168.1.1:80/api/config/timeofuse",
            "customer",
            "password",
        )

        assert result == {"timeofuse": []}
        mock_request.assert_called_once_with(
            "GET",
            "http://192.168.1.1:80/api/config/timeofuse",
            "customer",
            "password",
            timeout=15,
        )


class TestFroniusGetHtml:
    """Test fronius_get_html function."""

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_get_html(self, mock_request) -> None:
        """Test getting HTML from inverter."""
        mock_response = Mock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_request.return_value = mock_response

        result = fronius_get_html(
            "http://192.168.1.1:80/api/test",
            "customer",
            "password",
        )

        assert result == "<html><body>Test</body></html>"
        mock_request.assert_called_once()


class TestFroniusPostJson:
    """Test fronius_post_json function."""

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_post_json(self, mock_request) -> None:
        """Test posting JSON to inverter."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        payload = {"timeofuse": []}
        result = fronius_post_json(
            "http://192.168.1.1:80/api/config/timeofuse",
            "customer",
            "password",
            payload,
        )

        assert result == {"status": "ok"}
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"] == payload
