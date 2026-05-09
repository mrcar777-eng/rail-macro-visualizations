from __future__ import annotations

import logging
import requests
from datetime import date, timedelta

from config import FRED_API_KEY, FRED_SERIES_IDS

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(series_id: str, observation_start: str | None = None) -> list:
    """Return observations for one FRED series, optionally starting from a given date."""
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "asc",
    }
    if observation_start:
        params["observation_start"] = observation_start
    response = requests.get(_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("observations", [])


def fetch_all_series(latest_dates: dict | None = None) -> dict:
    """Fetch observations for every series in FRED_SERIES_IDS, starting after the latest known date."""
    results = {}
    for series_id, label in FRED_SERIES_IDS.items():
        start = (latest_dates or {}).get(series_id)
        if start:
            # Advance by one day so we don't re-fetch the already-stored observation
            next_day = str(date.fromisoformat(start) + timedelta(days=1))
            logger.info("Fetching FRED: %s (%s) from %s", series_id, label, next_day)
        else:
            next_day = None
            logger.info("Fetching FRED: %s (%s) [full history]", series_id, label)
        try:
            results[series_id] = fetch_series(series_id, observation_start=next_day)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", series_id, e)
            results[series_id] = []
    return results
