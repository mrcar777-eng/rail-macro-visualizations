"""
FAF5 Freight Analysis Framework — CSV download and chunked reader.

Source: Oak Ridge National Laboratory / BTS public download
No authentication required.
"""
from __future__ import annotations

import logging
import os
import zipfile
from typing import Iterator

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    """Return a Session with retry adapter."""
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


def download_faf5_csv(url: str, dest_path: str) -> bool:
    """
    Stream-download the FAF5 file to dest_path.
    If the URL points to a .zip, extracts the first .csv inside it to dest_path.
    Returns True on success, False on HTTP error (logs warning).
    """
    session = _make_session()
    # ORNL server requires a browser-like User-Agent to avoid connection resets
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        # TODO: ORNL server blocks automated downloads even with browser User-Agent.
        # Manually download the zip from https://faf.ornl.gov/faf5/data/download_files/FAF5.7.1_2017-2024.zip
        # extract the CSV, then set FAF5_CSV_URL=file:///path/to/FAF5.csv in .env (or pass local path directly).
        logger.info("FAF5: downloading from %s", url)
        response = session.get(url, stream=True, timeout=600, headers=headers)
        response.raise_for_status()

        # Write raw download to a temp file first
        raw_path = dest_path + ".download"
        with open(raw_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        # If it's a zip, extract the first CSV inside it
        if url.lower().endswith(".zip") or zipfile.is_zipfile(raw_path):
            logger.info("FAF5: extracting CSV from zip archive")
            with zipfile.ZipFile(raw_path, "r") as zf:
                csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if not csv_names:
                    logger.warning("FAF5: no CSV found inside zip archive")
                    os.remove(raw_path)
                    return False
                # Extract the first (usually only) CSV
                with zf.open(csv_names[0]) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
            os.remove(raw_path)
            logger.info("FAF5: extracted %s -> %s", csv_names[0], dest_path)
        else:
            # Plain CSV — just rename
            os.rename(raw_path, dest_path)

        logger.info("FAF5: download complete -> %s", dest_path)
        return True
    except requests.HTTPError as e:
        logger.warning("FAF5: HTTP error downloading file: %s", e)
        return False
    except Exception as e:
        logger.warning("FAF5: failed to download file: %s", e)
        return False


def iter_faf5_chunks(
    dest_path: str,
    chunksize: int = 100_000,
) -> Iterator[pd.DataFrame]:
    """
    Yield successive DataFrame chunks from the downloaded CSV file.
    Uses dtype=str to prevent silent coercion before the cleaner runs.
    All freight modes are retained so rail can be compared against truck,
    air, water, and pipeline in visualizations.

    FAF5 mode codes:
        1 = Truck
        2 = Rail
        3 = Water
        4 = Air (inc. truck-air)
        5 = Multiple modes & mail
        6 = Pipeline
        7 = Other and unknown
    """
    logger.info("FAF5: reading CSV in chunks of %d rows (all modes)", chunksize)
    reader = pd.read_csv(dest_path, chunksize=chunksize, dtype=str, low_memory=False)
    for chunk in reader:
        yield chunk
