"""
Custom HTTP Digest auth helpers for Fronius Gen24.

Fronius Gen24 quirks:
1. Digest challenge arrives in X-WWW-Authenticate, not WWW-Authenticate.
2. HA1 is computed with either MD5 or SHA-256 depending on account age.
3. HA2 and the final response digest are always SHA-256.
4. The Authorization response must NOT echo the `algorithm` field.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)


def _parse_challenge(header: str) -> dict[str, str]:
    """Parse a Digest challenge header into a dict of directives."""
    challenge: dict[str, str] = {}

    for match in re.finditer(r'(\w+)=(?:(?:"([^"]*)")|([\w./+-]+))', header):
        key = match.group(1).lower()
        value = match.group(2) or match.group(3)
        if value:
            challenge[key] = value

    _LOGGER.debug("Parsed digest challenge: %s", challenge)
    return challenge


def _build_authorization(  # NOQA: PLR0913
    method: str,
    url: str,
    username: str,
    password: str,
    challenge_header: str,
    ha1_algo: str = "md5",
) -> str:
    """
    Compute an Authorization header value for Digest auth.

    Args:
        method: HTTP method.
        url: Full request URL.
        username: Fronius username.
        password: Fronius password.
        challenge_header: Digest challenge header value.
        ha1_algo: Algorithm to compute HA1 with, either "md5" or "sha256".

    """
    challenge = _parse_challenge(challenge_header)

    realm = challenge.get("realm", "")
    nonce = challenge.get("nonce", "")
    qop_opts = challenge.get("qop", "")

    _LOGGER.debug(
        "Digest params — realm=%r nonce=%r qop=%r ha1_algo=%s",
        realm,
        nonce,
        qop_opts,
        ha1_algo,
    )

    parsed_url = urlparse(url)
    uri = parsed_url.path or "/"
    if parsed_url.query:
        uri = f"{uri}?{parsed_url.query}"

    def md5(value: str) -> str:
        return hashlib.md5(value.encode()).hexdigest()  # NOQA: S324

    def sha256(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    ha1 = (md5 if ha1_algo == "md5" else sha256)(f"{username}:{realm}:{password}")
    ha2 = sha256(f"{method.upper()}:{uri}")

    _LOGGER.debug("HA1(%s)=%s  HA2(sha256)=%s  uri=%r", ha1_algo, ha1, ha2, uri)

    qop_values = [opt.strip() for opt in qop_opts.split(",") if opt.strip()]
    if "auth" in qop_values:
        cnonce = os.urandom(8).hex()
        nc = "00000001"
        response = sha256(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}")
        header = (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{response}", '
            f'qop=auth, nc={nc}, cnonce="{cnonce}"'
        )
    else:
        response = sha256(f"{ha1}:{nonce}:{ha2}")
        header = f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'

    _LOGGER.debug("Built Authorization header (%s): %s", ha1_algo, header)
    return header
