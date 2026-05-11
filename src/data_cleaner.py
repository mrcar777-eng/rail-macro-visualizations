from __future__ import annotations

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

_FRED_MISSING = {".", "", "N/A"}


def clean_fred_observations(observations: list) -> list:
    """Remove FRED records with missing/non-numeric values or invalid dates."""
    cleaned = []
    skipped = 0
    for obs in observations:
        raw_value = obs.get("value") or ""
        if raw_value.strip() in _FRED_MISSING:
            skipped += 1
            continue
        try:
            date.fromisoformat(obs["date"])
        except (ValueError, KeyError):
            skipped += 1
            continue
        try:
            float(raw_value)
        except ValueError:
            skipped += 1
            continue
        cleaned.append(obs)
    if skipped:
        logger.info("Cleaned: dropped %d invalid/missing FRED observations", skipped)
    return cleaned


def clean_edgar_filings(filings: list) -> list:
    """Drop filings with no accession number; coerce unparseable dates to None.

    Accession number is the unique key for deduplication, so a filing without
    one cannot be stored and is dropped.  Dates are metadata — a filing with a
    missing or malformed date is still useful, so it is kept with date=NULL
    rather than dropped entirely.
    """
    cleaned = []
    skipped = 0
    for f in filings:
        acc = (f.get("accession_number") or "").strip()
        if not acc:
            skipped += 1
            continue
        entry = {**f, "accession_number": acc}
        for field in ("filing_date", "report_date"):
            val = entry.get(field)
            if val:
                try:
                    date.fromisoformat(str(val).strip())
                except ValueError:
                    entry[field] = None
        cleaned.append(entry)
    if skipped:
        logger.info("Cleaned: dropped %d Edgar filings missing accession number", skipped)
    return cleaned


def clean_stb_records(records: list[dict]) -> list[dict]:
    """
    Clean STB waybill records.
    - Drop records where commodity_code or origin_bea is None or empty string.
    - Drop records where routing_miles cannot be coerced to float.
    Returns cleaned list.
    """
    cleaned = []
    skipped = 0
    for rec in records:
        commodity = (rec.get("commodity_code") or "").strip()
        origin = (rec.get("origin_bea") or "").strip()
        if not commodity or not origin:
            skipped += 1
            continue
        try:
            float(rec.get("routing_miles", ""))
        except (ValueError, TypeError):
            skipped += 1
            continue
        cleaned.append(rec)
    if skipped:
        logger.info("STB clean: dropped %d invalid records", skipped)
    return cleaned


def clean_faf5_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """
    Clean one FAF5 CSV chunk.
    - Drop rows where dms_orig, dms_dest, sctg2, or dms_mode is null.
    - Coerce tons, value_usd_mil, tmiles to numeric; replace failures with NaN (row retained).
    Returns cleaned DataFrame.
    """
    required = ["dms_orig", "dms_dest", "sctg2", "dms_mode"]
    # Only drop on columns that actually exist in this chunk
    existing_required = [c for c in required if c in chunk.columns]
    chunk = chunk.dropna(subset=existing_required)
    for col in ["tons", "value_usd_mil", "tmiles"]:
        if col in chunk.columns:
            chunk = chunk.copy()
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
    return chunk.reset_index(drop=True)


def clean_spatial_features(features: list[dict]) -> list[dict]:
    """
    Clean GeoJSON feature list for NCDOT and NC DEQ layers.
    - Drop features where geometry is None.
    - Drop features where geometry coordinates list is empty or None.
    Returns cleaned list.
    """
    cleaned = []
    skipped = 0
    for feat in features:
        geom = feat.get("geometry")
        if geom is None:
            skipped += 1
            continue
        coords = geom.get("coordinates")
        if not coords:
            skipped += 1
            continue
        cleaned.append(feat)
    if skipped:
        logger.info("Spatial clean: dropped %d features with null/empty geometry", skipped)
    return cleaned


def clean_fra_records(records: list[dict]) -> list[dict]:
    """
    Clean FRA grade crossing records.
    - Drop records where CrossingID is None or empty string.
    - Coerce AADT, NbrTracks, TotalAcc to int; replace failures with None (row retained).
    Returns cleaned list.
    """
    cleaned = []
    skipped = 0
    for rec in records:
        crossing_id = (rec.get("CrossingID") or "").strip()
        if not crossing_id:
            skipped += 1
            continue
        for field in ("AADT", "NbrTracks", "TotalAcc"):
            val = rec.get(field)
            if val is not None:
                try:
                    rec[field] = int(val)
                except (ValueError, TypeError):
                    rec[field] = None
        cleaned.append(rec)
    if skipped:
        logger.info("FRA clean: dropped %d records missing CrossingID", skipped)
    return cleaned
