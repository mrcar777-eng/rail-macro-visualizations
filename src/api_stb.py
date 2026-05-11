"""
STB Public Use Carload Waybill Sample — Socrata SODA API fetcher.

Endpoint: USDA Agricultural Marketing Service via Socrata
Auth: X-App-Token header (STB_APP_TOKEN from config)
"""
from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import STB_APP_TOKEN

logger = logging.getLogger(__name__)

# Socrata SODA endpoint for STB Public Use Waybill Sample
# TODO: dataset requires an approved app token registered at https://data.transportation.gov
# Register an account, request access to dataset w96p-f2qv, then set STB_APP_TOKEN in .env
_ENDPOINT = "https://data.transportation.gov/resource/w96p-f2qv.json"


def _make_session() -> requests.Session:
    """Return a Session with retry adapter mounted for http:// and https://."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_waybill_records(limit: int = 50_000, offset: int = 0) -> list[dict]:
    """
    Fetch one page of STB waybill records from the Socrata SODA API.
    Sends X-App-Token header. Returns list of record dicts, or [] on HTTP error.
    """
    session = _make_session()
    headers = {}
    if STB_APP_TOKEN:
        headers["X-App-Token"] = STB_APP_TOKEN

    params = {
        "$limit": limit,
        "$offset": offset,
    }

    try:
        response = session.get(_ENDPOINT, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        logger.warning("STB API HTTP error (offset=%d): %s", offset, e)
        return []
    except Exception as e:
        logger.warning("STB API request failed (offset=%d): %s", offset, e)
        return []


def fetch_all_waybill_records() -> list[dict]:
    """
    Paginate the SODA API using $limit/$offset until an empty page is returned.
    Returns the accumulated list of all waybill record dicts.
    """
    if not STB_APP_TOKEN:
        logger.warning("STB: STB_APP_TOKEN not set — skipping STB fetch")
        return []

    all_records: list[dict] = []
    offset = 0
    limit = 50_000

    while True:
        logger.info("STB: fetching records offset=%d", offset)
        page = fetch_waybill_records(limit=limit, offset=offset)
        if not page:
            break
        all_records.extend(page)
        if len(page) < limit:
            break  # last page
        offset += limit

    logger.info("STB: fetched %d total records", len(all_records))
    return all_records
