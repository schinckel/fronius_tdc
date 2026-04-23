“”“Custom HTTP Digest auth for Fronius Gen24’s non-standard X-WWW-Authenticate header.

Fronius Gen24 quirks:

1. Digest challenge arrives in X-WWW-Authenticate, not WWW-Authenticate.
1. HA1 is computed with either MD5 or SHA-256 depending on when the account
   password was last set (hashingVersion 1 = MD5, 2 = SHA-256). There is no
   way to query the hashingVersion without already being authenticated, so we
   try MD5 first (the common legacy case), then SHA-256 on a second 401.
1. HA2 and the final response digest are always SHA-256.
1. The Authorization response must NOT echo the `algorithm` field back.
   “””

from **future** import annotations

import hashlib
import logging
import os
import re
from urllib.parse import urlparse

import requests

_LOGGER = logging.getLogger(**name**)

def _parse_challenge(header: str) -> dict[str, str]:
“”“Parse a Digest challenge header into a dict of directives.

```
Handles quoted values that contain spaces, e.g. realm="Webinterface area".
"""
challenge: dict[str, str] = {}
for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([\w./+-]+))', header):
    key = match.group(1).lower()
    value = match.group(2) if match.group(2) is not None else match.group(3)
    challenge[key] = value
_LOGGER.debug("Parsed digest challenge: %s", challenge)
return challenge
```

def _build_authorization(
method: str,
url: str,
username: str,
password: str,
challenge_header: str,
ha1_algo: str = “md5”,
) -> str:
“”“Compute one Authorization header value.

```
ha1_algo controls whether HA1 = MD5(...) or SHA256(...).
HA2 and the final response are always SHA-256.
"""
challenge = _parse_challenge(challenge_header)

realm    = challenge.get("realm", "")
nonce    = challenge.get("nonce", "")
qop_opts = challenge.get("qop", "")

_LOGGER.debug(
    "Digest params — realm=%r nonce=%r qop=%r ha1_algo=%s",
    realm, nonce, qop_opts, ha1_algo,
)

parsed = urlparse(url)
uri = parsed.path + (f"?{parsed.query}" if parsed.query else "")

def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

ha1 = md5(f"{username}:{realm}:{password}") if ha1_algo == "md5" \
    else sha256(f"{username}:{realm}:{password}")
ha2 = sha256(f"{method.upper()}:{uri}")

_LOGGER.debug("HA1(%s)=%s  HA2(sha256)=%s  uri=%r", ha1_algo, ha1, ha2, uri)

if "auth" in qop_opts.split(","):
    cnonce = os.urandom(8).hex()
    nc = "00000001"
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

_LOGGER.debug("Built Authorization header (%s): %s", ha1_algo, header)
return header
```

def fronius_request(
method: str,
url: str,
username: str,
password: str,
timeout: int = 15,
**kwargs,
) -> requests.Response:
“”“Make an HTTP request to the Fronius Gen24, handling digest auth manually.

```
Flow:
  1. Send request with no auth → expect 401 with challenge.
  2. Try MD5 HA1 (legacy hashingVersion=1 accounts).
  3. If still 401, try SHA-256 HA1 (newer hashingVersion=2 accounts).
  4. If still 401, raise.
"""
# Step 1: unauthenticated request
resp = requests.request(method, url, timeout=timeout, **kwargs)
_LOGGER.debug("Step 1 — %s %s → HTTP %s", method, url, resp.status_code)

if resp.status_code != 401:
    resp.raise_for_status()
    return resp

# Find challenge header (Fronius uses X-WWW-Authenticate)
challenge_header = (
    resp.headers.get("www-authenticate")
    or resp.headers.get("x-www-authenticate")
)
_LOGGER.debug("Challenge header: %s", challenge_header)

if not challenge_header:
    resp.raise_for_status()
    return resp

# Try each HA1 algorithm in order: MD5 first (most accounts), then SHA-256
for attempt, ha1_algo in enumerate(("md5", "sha256"), start=2):
    authorization = _build_authorization(
        method, url, username, password, challenge_header, ha1_algo
    )
    headers = dict(kwargs.pop("headers", None) or {})
    headers["Authorization"] = authorization
    resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
    _LOGGER.debug(
        "Step %d (authenticated, HA1=%s) — %s %s → HTTP %s",
        attempt, ha1_algo, method, url, resp.status_code,
    )

    if resp.status_code != 401:
        resp.raise_for_status()
        return resp

    # Still 401 — the server issues a fresh challenge with a new nonce,
    # so re-read it before the next attempt
    challenge_header = (
        resp.headers.get("www-authenticate")
        or resp.headers.get("x-www-authenticate")
        or challenge_header
    )

# Both algorithms failed
resp.raise_for_status()
return resp
```

def fronius_get_json(url: str, username: str, password: str, timeout: int = 15) -> dict:
return fronius_request(“GET”, url, username, password, timeout=timeout).json()

def fronius_get_html(url: str, username: str, password: str, timeout: int = 15) -> str:
return fronius_request(“GET”, url, username, password, timeout=timeout).text

def fronius_post_json(
url: str, username: str, password: str, payload: dict, timeout: int = 15
) -> dict:
return fronius_request(
“POST”, url, username, password, timeout=timeout, json=payload
).json()
