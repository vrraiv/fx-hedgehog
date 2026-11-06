"""Thin HTTP helpers shared by the loaders: retries, timeouts and the offline guard."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from fx_treasury_risk import __version__, config

log = logging.getLogger(__name__)

USER_AGENT = f"fx-treasury-risk/{__version__} (+https://github.com/vrraiv/fx-hedgehog)"
DEFAULT_TIMEOUT = 60.0
_RETRY_STATUS = {429, 500, 502, 503, 504}


class OfflineError(RuntimeError):
    """Raised when network access is attempted while ``FXRISK_OFFLINE`` is set."""


def _check_online(url: str) -> None:
    if config.offline():
        raise OfflineError(f"FXRISK_OFFLINE is set; refusing to fetch {url}")


def _request(
    method: str, url: str, *, retries: int, timeout: float, **kwargs: Any
) -> requests.Response:
    _check_online(url)
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
            if resp.status_code in _RETRY_STATUS and attempt < retries:
                log.warning("%s %s -> %s, retrying", method, url, resp.status_code)
            else:
                resp.raise_for_status()
                return resp
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            log.warning("%s %s failed (%s), retrying", method, url, exc)
        time.sleep(2**attempt)
    raise requests.ConnectionError(f"giving up on {url}") from last_exc


def get(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    retries: int = 3,
    timeout: float = DEFAULT_TIMEOUT,
) -> requests.Response:
    """HTTP GET with retries on transient failures."""
    return _request("GET", url, retries=retries, timeout=timeout, params=params)


def post_json(
    url: str, payload: Any, *, retries: int = 3, timeout: float = DEFAULT_TIMEOUT
) -> requests.Response:
    """HTTP POST of a JSON body with retries on transient failures."""
    return _request("POST", url, retries=retries, timeout=timeout, json=payload)
