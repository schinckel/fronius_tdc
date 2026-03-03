"""
Custom HTTP Digest auth for Fronius Gen24's non-standard X-WWW-Authenticate header.

Fronius Gen24 quirks discovered by reverse-engineering main_*.js:
  1. Digest challenge arrives in X-WWW-Authenticate, not WWW-Authenticate.
  2. HA1 is computed with MD5 regardless of the advertised algorithm
     (legacy accounts created before Fronius switched to SHA-256 store an
     MD5 hash on the server; hashingVersion==1 => MD5, ==2 => SHA-256, but
     we have no way to query that without being authenticated first).
  3. HA2 and the final response are always computed with SHA-256.
  4. The Authorization response must NOT echo the `algorithm` field back
     (the server rejects requests that include it).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)


def _parse_challenge(header: str) -> dict[str, str]:
    """
    Parse a Digest challenge header into a dict of directives.

    Handles quoted values that contain spaces, e.g. realm="Webinterface area".
    """
    challenge: dict[str, str] = {}
    for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([\w./+-]+))', header):
        key = match.group(1).lower()
        value = match.group(2) if match.group(2) is not None else match.group(3)
        challenge[key] = value
    _LOGGER.debug("Parsed digest challenge: %s", challenge)
    return challenge


def _build_authorization(
    method: str,
    url: str,
    username: str,
    password: str,
    challenge_header: str,
) -> str:
    """
    Compute an Authorization header value matching Fronius Gen24's expectations.

    Fronius uses a mixed-algorithm scheme:
      - HA1 = MD5(username:realm:password)   ← legacy MD5 regardless of advertised algo
      - HA2 = SHA-256(METHOD:uri)
      - response = SHA-256(HA1:nonce:nc:cnonce:qop:HA2)

    The `algorithm` directive is intentionally omitted from the Authorization
    header because the server rejects requests that include it.
    """
    challenge = _parse_challenge(challenge_header)

    realm = challenge.get("realm", "")
    nonce = challenge.get("nonce", "")
    qop_opts = challenge.get("qop", "")

    _LOGGER.debug(
        "Digest params — realm=%r nonce=%r qop=%r",
        realm,
        nonce,
        qop_opts,
    )

    parsed = urlparse(url)
    uri = parsed.path + (f"?{parsed.query}" if parsed.query else "")

    def md5(data: str) -> str:
        return hashlib.md5(data.encode()).hexdigest()  # nosec: B303 - MD5 is used here intentionally to match the server's expectations  # noqa: S324

    def sha256(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    # HA1 always uses MD5 (Fronius legacy account storage)
    ha1 = md5(f"{username}:{realm}:{password}")
    # HA2 always uses SHA-256
    ha2 = sha256(f"{method.upper()}:{uri}")

    _LOGGER.debug("HA1(md5)=%s  HA2(sha256)=%s  uri=%r", ha1, ha2, uri)

    if "auth" in qop_opts.split(","):
        cnonce = os.urandom(8).hex()
        nc = "00000001"
        # Final response uses SHA-256
        digest_response = sha256(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}")
        header = (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{digest_response}", '
            f'qop=auth, nc={nc}, cnonce="{cnonce}"'
        )
    else:
        digest_response = sha256(f"{ha1}:{nonce}:{ha2}")
        header = (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{digest_response}"'
        )

    _LOGGER.debug("Built Authorization header: %s", header)
    return header
