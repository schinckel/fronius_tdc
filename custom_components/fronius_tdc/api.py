"""Sample API Client."""

from __future__ import annotations

from typing import Any

import requests

from .auth import _build_authorization
from .const import LOGGER

UNAUTHORIZED = 401


def fronius_request(
    method: str,
    url: str,
    username: str,
    password: str,
    timeout: int = 15,
    **kwargs: Any,
) -> requests.Response:
    """
    Make an HTTP request to the Fronius Gen24, handling digest auth manually.

    Flow:
      1. Send request with no auth.
      2. On 401, read challenge from X-WWW-Authenticate (or WWW-Authenticate).
      3. Compute Authorization header using mixed MD5/SHA-256 scheme.
      4. Retry with Authorization header.
    """
    # Step 1: unauthenticated request
    resp = requests.request(method, url, timeout=timeout, **kwargs)
    LOGGER.debug("Step 1 — %s %s → HTTP %s", method, url, resp.status_code)

    if resp.status_code != UNAUTHORIZED:
        resp.raise_for_status()
        return resp

    # Step 2: find challenge header (Fronius uses X-WWW-Authenticate)
    challenge_header = resp.headers.get("www-authenticate") or resp.headers.get(
        "x-www-authenticate"
    )
    LOGGER.debug("Challenge header: %s", challenge_header)

    if not challenge_header:
        resp.raise_for_status()

    # Step 3: compute Authorization
    authorization = _build_authorization(
        method, url, username, password, challenge_header
    )

    # Step 4: retry with Authorization header
    headers = dict(kwargs.pop("headers", None) or {})
    headers["Authorization"] = authorization
    resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
    LOGGER.debug(
        "Step 2 (authenticated) — %s %s → HTTP %s", method, url, resp.status_code
    )
    LOGGER.debug("Step 2 response body: %s", resp.text[:400])
    resp.raise_for_status()
    return resp


def fronius_get_json(url: str, username: str, password: str, timeout: int = 15) -> dict:
    """Fetch JSON from the inverter."""
    return fronius_request("GET", url, username, password, timeout=timeout).json()


def fronius_get_html(url: str, username: str, password: str, timeout: int = 15) -> str:
    """Fetch HTML from the inverter."""
    return fronius_request("GET", url, username, password, timeout=timeout).text


def fronius_post_json(
    url: str, username: str, password: str, payload: dict, timeout: int = 15
) -> dict:
    """Post data to the inverter, parse response as JSON."""
    return fronius_request(
        "POST", url, username, password, timeout=timeout, json=payload
    ).json()
