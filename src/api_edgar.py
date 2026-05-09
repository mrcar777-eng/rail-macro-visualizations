from __future__ import annotations

import logging
import requests

from config import TARGET_RAIL_COMPANIES, SEC_USER_AGENT

logger = logging.getLogger(__name__)

_BASE_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_FILING_TYPES = {"10-K", "10-Q"}


def fetch_company_filings(ticker: str, cik: str) -> list:
    """Return recent 10-K and 10-Q filings for a company from SEC Edgar."""
    url = _BASE_URL.format(cik=cik)
    headers = {"User-Agent": SEC_USER_AGENT}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    recent = response.json().get("filings", {}).get("recent", {})
    forms        = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accessions   = recent.get("accessionNumber", [])

    # zip() stops at the shortest array, avoiding any index-mismatch data loss
    filings = []
    for form, filing_date, report_date, accession in zip(forms, filing_dates, report_dates, accessions):
        if form not in _FILING_TYPES:
            continue
        filings.append({
            "ticker":           ticker,
            "cik":              cik,
            "form_type":        form,
            "filing_date":      filing_date or None,
            "report_date":      report_date or None,
            "accession_number": accession or None,
        })
    return filings


def fetch_all_companies() -> dict:
    """Fetch filings for all configured railroad companies."""
    results = {}
    for ticker, cik in TARGET_RAIL_COMPANIES.items():
        logger.info("Fetching Edgar: %s (CIK %s)", ticker, cik)
        try:
            results[ticker] = fetch_company_filings(ticker, cik)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", ticker, e)
            results[ticker] = []
    return results
