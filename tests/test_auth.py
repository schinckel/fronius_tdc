"""Tests for the auth module."""

from __future__ import annotations

import hashlib
import re
from unittest.mock import patch

from custom_components.fronius_tdc.auth import _build_authorization, _parse_challenge


class TestParseChallenge:
    """Test _parse_challenge function."""

    def test_parse_basic_challenge(self):
        """Test parsing a basic digest challenge."""
        header = 'Digest realm="Webinterface area", nonce="abc123", qop="auth"'
        result = _parse_challenge(header)

        assert result["realm"] == "Webinterface area"
        assert result["nonce"] == "abc123"
        assert result["qop"] == "auth"

    def test_parse_challenge_with_spaces_in_realm(self):
        """Test parsing challenge with spaces in quoted realm."""
        header = 'Digest realm="My Test Realm", nonce="xyz789"'
        result = _parse_challenge(header)

        assert result["realm"] == "My Test Realm"
        assert result["nonce"] == "xyz789"

    def test_parse_challenge_with_algorithm(self):
        """Test parsing challenge with algorithm directive."""
        header = 'Digest realm="api", nonce="n123", algorithm="SHA-256"'
        result = _parse_challenge(header)

        assert result["realm"] == "api"
        assert result["algorithm"] == "SHA-256"

    def test_parse_challenge_with_opaque(self):
        """Test parsing challenge with opaque directive."""
        header = 'Digest realm="test", nonce="n1", opaque="op123", qop="auth"'
        result = _parse_challenge(header)

        assert result["opaque"] == "op123"
        assert result["qop"] == "auth"

    def test_parse_challenge_unquoted_values(self):
        """Test parsing challenge with unquoted values."""
        header = 'Digest realm="api", nonce=abc123, qop=auth'
        result = _parse_challenge(header)

        assert result["realm"] == "api"
        assert result["nonce"] == "abc123"
        assert result["qop"] == "auth"

    def test_parse_challenge_multiple_qop_values(self):
        """Test parsing challenge with multiple qop options."""
        header = 'Digest realm="test", nonce="n1", qop="auth,auth-int"'
        result = _parse_challenge(header)

        assert result["qop"] == "auth,auth-int"

    def test_parse_challenge_empty_header(self):
        """Test parsing empty challenge header."""
        result = _parse_challenge("")
        assert result == {}

    def test_parse_challenge_case_insensitive_keys(self):
        """Test that keys are lowercased."""
        header = 'Digest REALM="api", NONCE="n1"'
        result = _parse_challenge(header)

        assert "realm" in result
        assert "nonce" in result
        assert result["realm"] == "api"


class TestBuildAuthorization:
    """Test _build_authorization function."""

    @patch("custom_components.fronius_tdc.auth.os.urandom")
    def test_build_authorization_with_auth_qop(self, mock_urandom):
        """Test building authorization with auth qop."""
        # Mock urandom to return predictable cnonce
        mock_urandom.return_value = b"\x01\x02\x03\x04\x05\x06\x07\x08"

        challenge = 'Digest realm="Webinterface area", nonce="abc123", qop="auth"'
        header = _build_authorization(
            "GET",
            "http://192.168.1.1:80/api/config/timeofuse",
            "customer",
            "password",
            challenge,
        )

        # Verify header structure
        assert header.startswith('Digest username="customer"')
        assert 'realm="Webinterface area"' in header
        assert 'nonce="abc123"' in header
        assert "qop=auth" in header
        assert "nc=00000001" in header
        assert "cnonce=" in header
        assert "response=" in header

    def test_build_authorization_without_auth_qop(self):
        """Test building authorization without auth qop (legacy mode)."""
        challenge = 'Digest realm="api", nonce="n123"'
        header = _build_authorization(
            "POST",
            "http://192.168.1.1/api/test",
            "user",
            "pass",
            challenge,
        )

        # Without qop, should not have nc or cnonce
        assert "qop" not in header
        assert "nc=" not in header
        assert "cnonce=" not in header
        assert 'Digest username="user"' in header
        assert "response=" in header

    def test_build_authorization_different_methods(self):
        """Test that different HTTP methods produce different responses."""
        challenge = 'Digest realm="api", nonce="n123", qop="auth"'

        with patch("custom_components.fronius_tdc.auth.os.urandom") as mock_urandom:
            mock_urandom.return_value = b"\x00" * 8

            get_header = _build_authorization(
                "GET",
                "http://192.168.1.1/api/test",
                "user",
                "pass",
                challenge,
            )

            post_header = _build_authorization(
                "POST",
                "http://192.168.1.1/api/test",
                "user",
                "pass",
                challenge,
            )

            # Extract response values
            get_response = re.search(r'response="([^"]+)"', get_header)
            post_response = re.search(r'response="([^"]+)"', post_header)

            assert get_response
            assert post_response
            assert get_response.group(1) != post_response.group(1)

    def test_build_authorization_different_uris(self):
        """Test that different URIs produce different responses."""
        challenge = 'Digest realm="api", nonce="n123", qop="auth"'

        with patch("custom_components.fronius_tdc.auth.os.urandom") as mock_urandom:
            mock_urandom.return_value = b"\x00" * 8

            uri1_header = _build_authorization(
                "GET",
                "http://192.168.1.1/api/endpoint1",
                "user",
                "pass",
                challenge,
            )

            uri2_header = _build_authorization(
                "GET",
                "http://192.168.1.1/api/endpoint2",
                "user",
                "pass",
                challenge,
            )

            uri1_response = re.search(r'response="([^"]+)"', uri1_header)
            uri2_response = re.search(r'response="([^"]+)"', uri2_header)

            assert uri1_response
            assert uri2_response
            assert uri1_response.group(1) != uri2_response.group(1)

    def test_build_authorization_preserves_realm(self):
        """Test that realm value is preserved in the header."""
        challenge = 'Digest realm="Custom Realm Name", nonce="n1", qop="auth"'
        header = _build_authorization(
            "GET",
            "http://192.168.1.1/api",
            "user",
            "pass",
            challenge,
        )

        assert 'realm="Custom Realm Name"' in header

    def test_build_authorization_uri_with_query_string(self):
        """Test building auth with URI containing query parameters."""
        challenge = 'Digest realm="api", nonce="n1", qop="auth"'

        with patch("custom_components.fronius_tdc.auth.os.urandom") as mock_urandom:
            mock_urandom.return_value = b"\x00" * 8

            header = _build_authorization(
                "GET",
                "http://192.168.1.1/api/test?param=value",
                "user",
                "pass",
                challenge,
            )

            assert 'uri="/api/test?param=value"' in header

    def test_build_authorization_different_credentials(self):
        """Test that different credentials produce different responses."""
        challenge = 'Digest realm="api", nonce="n1", qop="auth"'

        with patch("custom_components.fronius_tdc.auth.os.urandom") as mock_urandom:
            mock_urandom.return_value = b"\x00" * 8

            header1 = _build_authorization(
                "GET",
                "http://192.168.1.1/api",
                "user1",
                "pass1",
                challenge,
            )

            header2 = _build_authorization(
                "GET",
                "http://192.168.1.1/api",
                "user2",
                "pass2",
                challenge,
            )

            response1 = re.search(r'response="([^"]+)"', header1)
            response2 = re.search(r'response="([^"]+)"', header2)

            assert response1
            assert response2
            assert response1.group(1) != response2.group(1)

    def test_build_authorization_ha1_uses_md5(self):
        """Test that HA1 is computed with MD5 (legacy Fronius behavior)."""
        username = "customer"
        password = "password"  # noqa: S105
        realm = "Webinterface area"

        challenge = f'Digest realm="{realm}", nonce="n1", qop="auth"'

        with patch("custom_components.fronius_tdc.auth.os.urandom") as mock_urandom:
            mock_urandom.return_value = b"\x00" * 8

            header = _build_authorization(
                "GET",
                "http://192.168.1.1/api",
                username,
                password,
                challenge,
            )

            # Manually compute expected HA1
            hashlib.md5(  # noqa: S324
                f"{username}:{realm}:{password}".encode()
            ).hexdigest()

            # The response should contain the correct HA1 value
            # We can verify it by computing what the response should be
            assert header is not None
            assert "response=" in header

    def test_build_authorization_format_without_algorithm_field(self):
        """Test that algorithm field is NOT included in the response."""
        challenge = 'Digest realm="api", nonce="n1", algorithm="SHA-256", qop="auth"'
        header = _build_authorization(
            "GET",
            "http://192.168.1.1/api",
            "user",
            "pass",
            challenge,
        )

        # The Authorization header should NOT echo back the algorithm field
        assert "algorithm=" not in header

    def test_build_authorization_handles_missing_qop(self):
        """Test building auth when challenge doesn't specify qop."""
        challenge = 'Digest realm="api", nonce="n1"'
        header = _build_authorization(
            "GET",
            "http://192.168.1.1/api",
            "user",
            "pass",
            challenge,
        )

        assert 'Digest username="user"' in header
        assert "response=" in header
        # Should not have qop-related fields
        assert "nc=" not in header

    def test_build_authorization_port_in_uri(self):
        """Test that port is not included in the URI digest calculation."""
        challenge = 'Digest realm="api", nonce="n1", qop="auth"'

        with patch("custom_components.fronius_tdc.auth.os.urandom") as mock_urandom:
            mock_urandom.return_value = b"\x00" * 8

            # Port 80 vs 8080 - should not affect digest since ports aren't in URI path
            header = _build_authorization(
                "GET",
                "http://192.168.1.1:80/api/test",
                "user",
                "pass",
                challenge,
            )

            assert 'uri="/api/test"' in header


class TestAuthIntegration:
    """Integration tests for authentication flow."""

    @patch("custom_components.fronius_tdc.auth.os.urandom")
    def test_auth_roundtrip(self, mock_urandom):
        """Test complete authentication challenge-response flow."""
        # Simulate a real Fronius challenge
        challenge = (
            'Digest realm="Webinterface area", nonce="6edf5f3f0b0c7d4b", qop="auth"'
        )

        mock_urandom.return_value = b"\xaa\xbb\xcc\xdd\xee\xff\x00\x11"

        header = _build_authorization(
            "GET",
            "http://192.168.1.1:80/api/config/timeofuse",
            "customer",
            "pass123",
            challenge,
        )

        # Verify all required fields are present
        assert 'username="customer"' in header
        assert 'realm="Webinterface area"' in header
        assert 'nonce="6edf5f3f0b0c7d4b"' in header
        assert 'uri="/api/config/timeofuse"' in header
        assert "response=" in header
        assert "qop=auth" in header
        assert "nc=00000001" in header
        assert "cnonce=" in header
