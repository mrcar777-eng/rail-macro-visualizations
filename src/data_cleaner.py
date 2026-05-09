from __future__ import annotations

import logging
from datetime import date

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
