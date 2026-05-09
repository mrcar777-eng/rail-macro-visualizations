"""
Shared data access utilities for rail macro visualization scripts.

Provides:
- fetch_series: query fred_observations for one or more FRED series
- fetch_edgar_filings: query edgar_filings for SEC filing dates
- RECESSION_BANDS: NBER recession date ranges (1945–present)
- add_recession_shading: apply gray axvspan shading for recession bands
"""

from __future__ import annotations

import pandas as pd
import matplotlib.axes

from src.database import get_db_connection


# ---------------------------------------------------------------------------
# Recession band constants (NBER official dates, 1945–present)
# ---------------------------------------------------------------------------

RECESSION_BANDS: list[tuple[str, str]] = [
    ("1948-10-01", "1949-10-01"),
    ("1953-07-01", "1954-05-01"),
    ("1957-08-01", "1958-04-01"),
    ("1960-04-01", "1961-02-01"),
    ("1969-12-01", "1970-11-01"),
    ("1973-11-01", "1975-03-01"),
    ("1980-01-01", "1980-07-01"),
    ("1981-07-01", "1982-11-01"),
    ("1990-07-01", "1991-03-01"),
    ("2001-03-01", "2001-11-01"),
    ("2007-12-01", "2009-06-01"),
    ("2020-02-01", "2020-04-01"),
]


# ---------------------------------------------------------------------------
# FRED series query
# ---------------------------------------------------------------------------

def fetch_series(
    series_ids: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Query fred_observations for one or more FRED series.

    Parameters
    ----------
    series_ids : list[str]
        One or more FRED series identifiers to fetch.
    start_date : str | None
        ISO-format date string (``"YYYY-MM-DD"``). When provided, only rows
        with ``observation_date >= start_date`` are returned.
    end_date : str | None
        ISO-format date string (``"YYYY-MM-DD"``). When provided, only rows
        with ``observation_date <= end_date`` are returned.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping of series_id -> DataFrame with columns:
        - ``observation_date`` (datetime64[ns])
        - ``value`` (float64)
        Rows with NULL/NaN values are excluded. Results are sorted ascending
        by ``observation_date``. If a series has no matching rows, an empty
        DataFrame with the correct columns is returned for that key.
    """
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError(
            "Could not establish a database connection. "
            "Check DB credentials and connectivity."
        )

    # Build the empty-DataFrame template once
    _empty = pd.DataFrame({
        "observation_date": pd.Series(dtype="datetime64[ns]"),
        "value": pd.Series(dtype="float64"),
    })

    result: dict[str, pd.DataFrame] = {}

    cursor = conn.cursor()
    try:
        for series_id in series_ids:
            # Build parameterized query dynamically based on which date
            # filters are requested — never interpolate user values.
            sql = (
                "SELECT observation_date, value "
                "FROM fred_observations "
                "WHERE series_id = %s "
                "AND value IS NOT NULL"
            )
            params: list = [series_id]

            if start_date is not None:
                sql += " AND observation_date >= %s"
                params.append(start_date)

            if end_date is not None:
                sql += " AND observation_date <= %s"
                params.append(end_date)

            sql += " ORDER BY observation_date ASC"

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            if not rows:
                result[series_id] = _empty.copy()
                continue

            df = pd.DataFrame(rows, columns=["observation_date", "value"])
            df["observation_date"] = pd.to_datetime(df["observation_date"])
            df["value"] = df["value"].astype("float64")

            # Drop any remaining NaN values (e.g. from DECIMAL -> float cast)
            df = df.dropna(subset=["value"]).reset_index(drop=True)

            result[series_id] = df

    finally:
        cursor.close()
        conn.close()

    return result


# ---------------------------------------------------------------------------
# Edgar filings query
# ---------------------------------------------------------------------------

def fetch_edgar_filings(
    tickers: list[str],
    form_type: str = "10-K",
) -> pd.DataFrame:
    """
    Query edgar_filings for the given tickers and form type.

    Parameters
    ----------
    tickers : list[str]
        Ticker symbols to include (e.g. ``["UNP", "CSX", "NSC"]``).
    form_type : str
        SEC form type to filter on (default ``"10-K"``).

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - ``ticker`` (str)
        - ``filing_date`` (datetime64[ns])
        - ``report_date`` (datetime64[ns])
        Returns an empty DataFrame with the correct columns when no rows match.
    """
    _empty = pd.DataFrame({
        "ticker": pd.Series(dtype="str"),
        "filing_date": pd.Series(dtype="datetime64[ns]"),
        "report_date": pd.Series(dtype="datetime64[ns]"),
    })

    if not tickers:
        return _empty

    conn = get_db_connection()
    if conn is None:
        raise RuntimeError(
            "Could not establish a database connection. "
            "Check DB credentials and connectivity."
        )

    cursor = conn.cursor()
    try:
        # Build a parameterized IN clause — one %s placeholder per ticker
        placeholders = ", ".join(["%s"] * len(tickers))
        sql = (
            f"SELECT ticker, filing_date, report_date "
            f"FROM edgar_filings "
            f"WHERE ticker IN ({placeholders}) "
            f"AND form_type = %s"
        )
        params = list(tickers) + [form_type]

        cursor.execute(sql, params)
        rows = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    if not rows:
        return _empty

    df = pd.DataFrame(rows, columns=["ticker", "filing_date", "report_date"])
    df["ticker"] = df["ticker"].astype("str")
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    df["report_date"] = pd.to_datetime(df["report_date"])

    return df


# ---------------------------------------------------------------------------
# Recession shading helper
# ---------------------------------------------------------------------------

def add_recession_shading(
    ax: matplotlib.axes.Axes,
    start_date: str | None = None,
    end_date: str | None = None,
) -> None:
    """
    Apply gray ``axvspan`` shading for each NBER recession band that overlaps
    the provided date range.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes object to shade. Modified in place.
    start_date : str | None
        ISO-format date string. Recession bands that end before this date are
        skipped.
    end_date : str | None
        ISO-format date string. Recession bands that start after this date are
        skipped.

    Returns
    -------
    None
        Modifies ``ax`` in place; no return value.
    """
    chart_start = pd.Timestamp(start_date) if start_date is not None else None
    chart_end = pd.Timestamp(end_date) if end_date is not None else None

    for band_start_str, band_end_str in RECESSION_BANDS:
        band_start = pd.Timestamp(band_start_str)
        band_end = pd.Timestamp(band_end_str)

        # Skip bands that fall entirely outside the visible date range
        if chart_start is not None and band_end < chart_start:
            continue
        if chart_end is not None and band_start > chart_end:
            continue

        ax.axvspan(band_start, band_end, alpha=0.2, color="gray")
