"""
NC DEQ Environmental Data — ArcGIS REST fetcher.

Source: NC DEQ Open Data Portal (unauthenticated ArcGIS FeatureServer)
Layers: UST Active Facilities, UST Incidents, Active Landfills
"""
from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_LAYERS: dict[str, str] = {
    # TODO: NC1Map_Environment MapServer does not contain UST data.
    # Find the correct FeatureServer endpoint for each dataset on the NCDEQ GIS Open Data Portal:
    #   UST Active Facilities: https://data-ncdenr.opendata.arcgis.com/datasets/ncdenr::ust-active-facilities/
    #   UST Incidents:         https://data-ncdenr.opendata.arcgis.com/datasets/ncdenr::ust-incidents/
    # On each page, click "I want to use this" > "View API Resources" to get the FeatureServer query URL.
    # Then replace the placeholder URLs below and remove this TODO.
    "ust_facilities": (
        "https://services.nconemap.gov/secure/rest/services/NC1Map_Environment/MapServer/3/query"
    ),
    "ust_incidents": (
        "https://services.nconemap.gov/secure/rest/services/NC1Map_Environment/MapServer/4/query"
    ),
    "active_landfills": (
        "https://services.nconemap.gov/secure/rest/services/NC1Map_Environment/MapServer/1/query"
    ),
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
    Paginate an ArcGIS REST FeatureServer /query endpoint using resultOffset.
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
            logger.warning("NC DEQ %s: HTTP error: %s", layer_name, e)
            break
        except Exception as e:
            logger.warning("NC DEQ %s: request failed: %s", layer_name, e)
            break

        if "error" in data:
            logger.warning(
                "NC DEQ %s: API error: %s",
                layer_name,
                data["error"].get("message", data["error"]),
            )
            break

        features = data.get("features", [])
        all_features.extend(features)
        logger.info(
            "NC DEQ %s: fetched %d features (offset=%d)",
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
    """Fetch all three NC DEQ layers. Returns dict mapping layer_name -> features."""
    results: dict[str, list[dict]] = {}
    for layer_name, url in _LAYERS.items():
        logger.info("NC DEQ: fetching layer '%s'", layer_name)
        results[layer_name] = fetch_layer(url, layer_name)
        logger.info(
            "NC DEQ: layer '%s' -> %d features",
            layer_name,
            len(results[layer_name]),
        )
    return results
