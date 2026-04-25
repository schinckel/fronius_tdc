"""Tests for the API module."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.fronius_tdc import api
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
    @patch("custom_components.fronius_tdc.api._build_authorization")
    def test_retry_on_401_with_sha256_fallback(self, mock_auth, mock_request) -> None:
        """Test that SHA-256 HA1 is attempted first and MD5 is used on failure."""
        response_401 = Mock()
        response_401.status_code = 401
        response_401.headers = {"x-www-authenticate": 'Digest realm="test", nonce="abc123"'}
        response_401.raise_for_status = Mock()

        response_401_second = Mock()
        response_401_second.status_code = 401
        response_401_second.headers = {"x-www-authenticate": 'Digest realm="test", nonce="xyz789"'}
        response_401_second.raise_for_status = Mock()

        response_200 = Mock()
        response_200.status_code = 200
        response_200.text = "<response data>"
        response_200.raise_for_status = Mock()

        mock_request.side_effect = [response_401, response_401_second, response_200]
        mock_auth.side_effect = ["Digest sha256", "Digest md5"]

        result = fronius_request(
            "GET",
            "http://192.168.1.1:80/api/test",
            "customer",
            "secret",
        )

        assert result.status_code == 200
        assert mock_request.call_count == 3
        assert mock_auth.call_count == 2
        assert mock_auth.call_args_list[0].kwargs["ha1_algo"] == "sha256"
        assert mock_auth.call_args_list[1].kwargs["ha1_algo"] == "md5"
        assert 'nonce="abc123"' in mock_auth.call_args_list[0].args[4]
        assert 'nonce="xyz789"' in mock_auth.call_args_list[1].args[4]

    @patch("custom_components.fronius_tdc.api.requests.request")
    @patch("custom_components.fronius_tdc.api._build_authorization")
    def test_cached_algorithm_avoids_repeated_probe(self, mock_auth, mock_request) -> None:
        """Test that a cached HA1 algorithm is tried first and falls back on failure."""
        cache_key = ("192.168.1.1:80", "customer")
        api._AUTH_ALGO_CACHE[cache_key] = "sha256"

        response_401_initial = Mock()
        response_401_initial.status_code = 401
        response_401_initial.headers = {"x-www-authenticate": 'Digest realm="test", nonce="abc123"'}
        response_401_initial.raise_for_status = Mock()

        response_401_cached = Mock()
        response_401_cached.status_code = 401
        response_401_cached.headers = {"x-www-authenticate": 'Digest realm="test", nonce="xyz789"'}
        response_401_cached.raise_for_status = Mock()

        response_200 = Mock()
        response_200.status_code = 200
        response_200.text = "<response data>"
        response_200.raise_for_status = Mock()

        mock_request.side_effect = [
            response_401_initial,
            response_401_cached,
            response_200,
        ]
        mock_auth.side_effect = ["Digest sha256", "Digest md5"]

        result = fronius_request(
            "GET",
            "http://192.168.1.1:80/api/test",
            "customer",
            "secret",
        )

        assert result.status_code == 200
        assert mock_request.call_count == 3
        assert mock_auth.call_count == 2
        assert mock_auth.call_args_list[0].kwargs["ha1_algo"] == "sha256"
        assert mock_auth.call_args_list[1].kwargs["ha1_algo"] == "md5"
        assert 'nonce="abc123"' in mock_auth.call_args_list[0].args[4]
        assert 'nonce="xyz789"' in mock_auth.call_args_list[1].args[4]
        api._AUTH_ALGO_CACHE.clear()

    @patch("custom_components.fronius_tdc.api.requests.request")
    @patch("custom_components.fronius_tdc.api._build_authorization")
    def test_auth_failure_after_all_retries(self, mock_auth, mock_request) -> None:
        """Test that auth failure after all algorithm retries raises HTTPError."""
        response_401_initial = Mock()
        response_401_initial.status_code = 401
        response_401_initial.headers = {"x-www-authenticate": 'Digest realm="test", nonce="abc123"'}
        response_401_initial.raise_for_status = Mock(side_effect=requests.HTTPError("Unauthorized"))

        response_401_sha256 = Mock()
        response_401_sha256.status_code = 401
        response_401_sha256.headers = {"x-www-authenticate": 'Digest realm="test", nonce="xyz789"'}
        response_401_sha256.raise_for_status = Mock(side_effect=requests.HTTPError("Unauthorized"))

        response_401_md5 = Mock()
        response_401_md5.status_code = 401
        response_401_md5.headers = {"x-www-authenticate": 'Digest realm="test", nonce="def456"'}
        response_401_md5.raise_for_status = Mock(side_effect=requests.HTTPError("Unauthorized"))

        mock_request.side_effect = [
            response_401_initial,
            response_401_sha256,
            response_401_md5,
        ]
        mock_auth.side_effect = ["Digest sha256", "Digest md5"]

        with pytest.raises(requests.HTTPError):
            fronius_request(
                "GET",
                "http://192.168.1.1:80/api/test",
                "customer",
                "secret",
            )

        assert mock_request.call_count == 3
        assert mock_auth.call_count == 2

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


class TestAPIEdgeCases:
    """Test edge cases and error conditions for API functions."""

    @patch("custom_components.fronius_tdc.api.requests.request")
    @patch("custom_components.fronius_tdc.api._build_authorization")
    def test_401_with_www_authenticate_header(self, mock_auth, mock_request) -> None:
        """Test 401 with standard www-authenticate header (not x-www-authenticate)."""
        response_401 = Mock()
        response_401.status_code = 401
        response_401.headers = {"www-authenticate": 'Digest realm="api"'}
        response_401.raise_for_status = Mock()

        response_200 = Mock()
        response_200.status_code = 200
        response_200.text = "Success"
        response_200.raise_for_status = Mock()

        mock_request.side_effect = [response_401, response_200]
        mock_auth.return_value = "Digest auth"

        result = fronius_request(
            "POST",
            "http://192.168.1.1/api/endpoint",
            "user",
            "pass",
        )

        assert result.status_code == 200
        mock_auth.assert_called_once()

    @patch("custom_components.fronius_tdc.api.requests.request")
    def test_401_without_challenge_header(self, mock_request) -> None:
        """Test 401 response without challenge header."""
        response_401 = Mock()
        response_401.status_code = 401
        response_401.headers = {}
        response_401.raise_for_status = Mock(side_effect=requests.HTTPError("401 Unauthorized"))
        mock_request.return_value = response_401

        with pytest.raises(requests.HTTPError):
            fronius_request(
                "GET",
                "http://192.168.1.1/api/test",
                "user",
                "pass",
            )

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_get_json_with_complex_data(self, mock_request) -> None:
        """Test getting complex JSON structure."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "timeofuse": [
                {
                    "id": 1,
                    "active": True,
                    "nested": {
                        "deep": {
                            "value": "test",
                            "array": [1, 2, 3],
                        }
                    },
                }
            ]
        }
        mock_request.return_value = mock_response

        result = fronius_get_json(
            "http://192.168.1.1/api/test",
            "user",
            "pass",
        )

        assert result["timeofuse"][0]["nested"]["deep"]["value"] == "test"
        assert result["timeofuse"][0]["nested"]["deep"]["array"] == [1, 2, 3]

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_get_html_with_special_characters(self, mock_request) -> None:
        """Test getting HTML with special characters."""
        mock_response = Mock()
        mock_response.text = "<html><body>äöü 日本語 emoji 🔧</body></html>"
        mock_request.return_value = mock_response

        result = fronius_get_html(
            "http://192.168.1.1/api/html",
            "user",
            "pass",
        )

        assert "äöü" in result
        assert "日本語" in result
        assert "🔧" in result

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_post_json_with_empty_payload(self, mock_request) -> None:
        """Test posting empty payload."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        result = fronius_post_json(
            "http://192.168.1.1/api/endpoint",
            "user",
            "pass",
            {},
        )

        assert result == {"status": "ok"}

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_post_json_with_large_payload(self, mock_request) -> None:
        """Test posting large JSON payload."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        # Create large payload
        large_payload = {"items": [{"id": i, "data": "x" * 1000} for i in range(100)]}

        result = fronius_post_json(
            "http://192.168.1.1/api/endpoint",
            "user",
            "pass",
            large_payload,
        )

        assert result == {"status": "ok"}
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"] == large_payload

    @patch("custom_components.fronius_tdc.api.requests.request")
    def test_request_with_custom_headers(self, mock_request) -> None:
        """Test request with custom headers passed via kwargs."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        fronius_request(
            "GET",
            "http://192.168.1.1/api/test",
            "user",
            "pass",
            headers={"X-Custom": "value"},
        )

        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs or call_kwargs.get("headers", {}).get("X-Custom") == "value"

    @patch("custom_components.fronius_tdc.api.requests.request")
    def test_request_different_http_methods(self, mock_request) -> None:
        """Test different HTTP methods."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        for method in methods:
            fronius_request(
                method,
                "http://192.168.1.1/api/test",
                "user",
                "pass",
            )

            call_args = mock_request.call_args[0]
            assert call_args[0] == method

    @patch("custom_components.fronius_tdc.api.requests.request")
    def test_request_handles_various_status_codes(self, mock_request) -> None:
        """Test request handling of various HTTP status codes."""
        status_codes = [200, 201, 204, 301, 302, 304, 400, 403, 404, 500, 502, 503]

        for status in status_codes:
            mock_response = Mock()
            mock_response.status_code = status
            mock_response.headers = {}
            if status >= 400:
                mock_response.raise_for_status.side_effect = requests.HTTPError(f"{status} Error")
            else:
                mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            if status >= 400 and status != 401:
                with pytest.raises(requests.HTTPError):
                    fronius_request(
                        "GET",
                        "http://192.168.1.1/api/test",
                        "user",
                        "pass",
                    )
            # 401 should retry, < 400 should succeed
            elif status != 401:
                result = fronius_request(
                    "GET",
                    "http://192.168.1.1/api/test",
                    "user",
                    "pass",
                )
                assert result.status_code == status

    @patch("custom_components.fronius_tdc.api.fronius_request")
    def test_get_json_handles_null_values(self, mock_request) -> None:
        """Test parsing JSON with null values."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "field1": None,
            "field2": "value",
            "field3": None,
        }
        mock_request.return_value = mock_response

        result = fronius_get_json(
            "http://192.168.1.1/api/test",
            "user",
            "pass",
        )

        assert result["field1"] is None
        assert result["field2"] == "value"
        assert result["field3"] is None
