"""
NCDOT Rail Infrastructure — ArcGIS REST fetcher.

Source: NC OneMap / NCDOT ArcGIS MapServer (unauthenticated)
Layers: Rail Track Lines, Railroad Crossings, Railroad Facilities
"""
from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_BASE = "https://gis11.services.ncdot.gov/arcgis/rest/services/NCDOT_RailSystem/MapServer"

_LAYERS: dict[str, str] = {
    "rail_facilities": f"{_BASE}/0/query",   # Railroad Facilities (yards, intermodal, transload)
    "rail_crossings":  f"{_BASE}/1/query",   # Railroad Crossings (public & pedestrian)
    "rail_lines":      f"{_BASE}/2/query",   # Rail Lines (freight & passenger track)
}


def _make_session() -> requests.Session:
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


def fetch_layer(
    url: str,
    layer_name: str,
    max_record_count: int = 1_000,
) -> list[dict]:
    """
    Paginate an ArcGIS REST /query endpoint using resultOffset.
    Returns list of GeoJSON feature dicts, or [] on error.
    """
    session = _make_session()
    all_features: list[dict] = []
    offset = 0

    while True:
        params = {
            "f": "geojson",
            "outFields": "*",
            "where": "1=1",
            "outSR": "4326",
            "resultOffset": offset,
            "resultRecordCount": max_record_count,
        }
        try:
            response = session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
        except requests.HTTPError as e:
            logger.warning("NCDOT %s: HTTP error: %s", layer_name, e)
            break
        except Exception as e:
            logger.warning("NCDOT %s: request failed: %s", layer_name, e)
            break

        if "error" in data:
            logger.warning(
                "NCDOT %s: API error: %s",
                layer_name,
                data["error"].get("message", data["error"]),
            )
            break

        features = data.get("features", [])
        all_features.extend(features)
        logger.info(
            "NCDOT %s: fetched %d features (offset=%d)",
            layer_name,
            len(features),
            offset,
        )

        exceeded = data.get("exceededTransferLimit", False)
        if not exceeded or len(features) < max_record_count:
            break

        offset += len(features)

    return all_features


def fetch_all_layers() -> dict[str, list[dict]]:
    """Fetch all three NCDOT layers. Returns dict mapping layer_name -> features."""
    results: dict[str, list[dict]] = {}
    for layer_name, url in _LAYERS.items():
        logger.info("NCDOT: fetching layer '%s'", layer_name)
        results[layer_name] = fetch_layer(url, layer_name)
        logger.info(
            "NCDOT: layer '%s' -> %d features",
            layer_name,
            len(results[layer_name]),
        )
    return results
