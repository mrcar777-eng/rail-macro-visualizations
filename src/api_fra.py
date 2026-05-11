"""
FRA Grade Crossing Inventory System — OData API fetcher.

Source: Federal Railroad Administration Safety Data API
Auth: Bearer token (20-minute expiry, requires FRA_API_TOKEN from config)
Protocol: OData with $skip/$top pagination
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import FRA_USERNAME, FRA_PASSWORD

logger = logging.getLogger(__name__)

_TOKEN_URL  = "https://safetydata.fra.dot.gov/MasterWebService/SecureApi/api/Authenticate"
_DATA_URL   = "https://safetydata.fra.dot.gov/MasterWebService/SecureApi/gcis/v1/odata/Crossings"
_TOKEN_TTL  = 1200  # 20 minutes in seconds
_REFRESH_BUFFER = 120  # refresh 2 minutes before expiry


@dataclass
class _TokenState:
    token: str
    acquired_at: datetime


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _acquire_token() -> _TokenState:
    """
    GET FRA token endpoint using HTTP Basic auth (username:password).
    Returns a _TokenState. Raises on HTTP error.
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = _make_session()
    credential = base64.b64encode(f"{FRA_USERNAME}:{FRA_PASSWORD}".encode()).decode()
    headers = {"Authorization": f"Basic {credential}"}
    # verify=False needed: FRA server has an incomplete certificate chain
    response = session.get(_TOKEN_URL, headers=headers, timeout=30, verify=False)
    response.raise_for_status()
    token_value = response.json().get("token") or response.text.strip().strip('"')
    return _TokenState(token=token_value, acquired_at=datetime.utcnow())


def _token_needs_refresh(state: _TokenState, refresh_before_seconds: int = _REFRESH_BUFFER) -> bool:
    """Return True if the token will expire within refresh_before_seconds."""
    elapsed = (datetime.utcnow() - state.acquired_at).total_seconds()
    return elapsed >= (_TOKEN_TTL - refresh_before_seconds)


def fetch_all_crossings(page_size: int = 1_000) -> list[dict]:
    """
    Paginate the FRA OData API using $skip/$top with token refresh.
    Returns accumulated list of crossing record dicts.
    """
    if not FRA_USERNAME or not FRA_PASSWORD:
        logger.warning("FRA: FRA_USERNAME or FRA_PASSWORD not set — skipping FRA fetch")
        return []

    try:
        state = _acquire_token()
        logger.info("FRA: token acquired")
    except Exception as e:
        logger.warning("FRA: failed to acquire token: %s", e)
        return []

    session = _make_session()
    all_records: list[dict] = []
    skip = 0

    while True:
        # Refresh token if approaching expiry
        if _token_needs_refresh(state):
            try:
                state = _acquire_token()
                logger.info("FRA: token refreshed at skip=%d", skip)
            except Exception as e:
                logger.warning("FRA: token refresh failed: %s — stopping", e)
                break

        params = {
            "$skip": skip,
            "$top": page_size,
            "$format": "json",
        }
        headers = {"X-ApiAccessToken": state.token}

        try:
            response = session.get(_DATA_URL, params=params, headers=headers, timeout=60, verify=False)

            # Handle 401 — refresh token once and retry
            if response.status_code == 401:
                logger.info("FRA: 401 received, refreshing token and retrying skip=%d", skip)
                try:
                    state = _acquire_token()
                    headers = {"X-ApiAccessToken": state.token}
                    response = session.get(_DATA_URL, params=params, headers=headers, timeout=60, verify=False)
                except Exception as e:
                    logger.warning("FRA: token refresh on 401 failed: %s — stopping", e)
                    break

            if response.status_code != 200:
                logger.warning("FRA: HTTP %d at skip=%d — stopping", response.status_code, skip)
                break

            records = response.json().get("value", [])
        except Exception as e:
            logger.warning("FRA: request failed at skip=%d: %s", skip, e)
            break

        if not records:
            break  # empty page = end of data

        all_records.extend(records)
        logger.info(
            "FRA: fetched %d records (skip=%d, total=%d)",
            len(records),
            skip,
            len(all_records),
        )
        skip += page_size

    logger.info("FRA: total crossings fetched: %d", len(all_records))
    return all_records
