import logging
import os
import tempfile

from config import FRED_SERIES_IDS, FAF5_CSV_URL

# Existing fetchers
from src.api_fred import fetch_all_series
from src.api_edgar import fetch_all_companies

# New fetchers
from src.api_stb import fetch_all_waybill_records
from src.api_faf5 import download_faf5_csv, iter_faf5_chunks
from src.api_ncdot import fetch_all_layers as fetch_ncdot_layers
from src.api_fra import fetch_all_crossings
from src.api_ncdeq import fetch_all_layers as fetch_ncdeq_layers

# Existing DB functions
from src.database import (
    create_tables,
    save_fred_data,
    save_edgar_filings,
    get_latest_fred_date,
)

# New DB save functions
from src.database import (
    save_stb_waybill,
    save_faf5_chunk,
    save_ncdot_layer,
    save_fra_crossings,
    save_ncdeq_layer,
)

# Existing cleaners
from src.data_cleaner import clean_fred_observations, clean_edgar_filings

# New cleaners
from src.data_cleaner import (
    clean_stb_records,
    clean_faf5_chunk,
    clean_spatial_features,
    clean_fra_records,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    logger.info("=== Rail Macro Data Pipeline ===")

    create_tables()

    # ------------------------------------------------------------------ #
    # [1/7] FRED macro series
    # ------------------------------------------------------------------ #
    try:
        logger.info("[1/7] Fetching FRED macro series...")
        latest_dates = {sid: get_latest_fred_date(sid) for sid in FRED_SERIES_IDS}
        fred_data = fetch_all_series(latest_dates=latest_dates)
        for series_id, observations in fred_data.items():
            cleaned = clean_fred_observations(observations)
            count = save_fred_data(series_id, cleaned)
            logger.info("%s: %d new rows saved (%d fetched from API)", series_id, count, len(cleaned))
    except Exception as e:
        logger.error("[1/7] FRED step failed: %s", e)

    # ------------------------------------------------------------------ #
    # [2/7] SEC Edgar filings
    # ------------------------------------------------------------------ #
    try:
        logger.info("[2/7] Fetching SEC Edgar filings (10-K / 10-Q)...")
        edgar_data = fetch_all_companies()
        for ticker, filings in edgar_data.items():
            cleaned = clean_edgar_filings(filings)
            count = save_edgar_filings(cleaned)
            logger.info("%s: %d new filings saved (%d fetched from API)", ticker, count, len(cleaned))
    except Exception as e:
        logger.error("[2/7] Edgar step failed: %s", e)

    # ------------------------------------------------------------------ #
    # [3/7] STB Waybill
    # ------------------------------------------------------------------ #
    try:
        logger.info("[3/7] Fetching STB Waybill records...")
        records = fetch_all_waybill_records()
        cleaned = clean_stb_records(records)
        count = save_stb_waybill(cleaned)
        logger.info("[3/7] STB Waybill: %d new rows saved (%d fetched)", count, len(records))
    except Exception as e:
        logger.error("[3/7] STB Waybill step failed: %s", e)

    # ------------------------------------------------------------------ #
    # [4/7] FAF5 Freight Flow
    # ------------------------------------------------------------------ #
    tmp_path = None
    try:
        logger.info("[4/7] Fetching FAF5 Freight Flow data...")
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv")
        os.close(tmp_fd)

        success = download_faf5_csv(FAF5_CSV_URL, tmp_path)
        if not success:
            logger.warning("[4/7] FAF5 download failed — skipping")
        else:
            total = 0
            for chunk in iter_faf5_chunks(tmp_path):
                cleaned_chunk = clean_faf5_chunk(chunk)
                total += save_faf5_chunk(cleaned_chunk)
            logger.info("[4/7] FAF5 Freight Flow: %d new rows saved", total)
    except Exception as e:
        logger.error("[4/7] FAF5 step failed: %s", e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ------------------------------------------------------------------ #
    # [5/7] NCDOT Rail Infrastructure
    # ------------------------------------------------------------------ #
    try:
        logger.info("[5/7] Fetching NCDOT Rail Infrastructure...")
        ncdot_layers = fetch_ncdot_layers()
        total = 0
        for layer_name, features in ncdot_layers.items():
            cleaned = clean_spatial_features(features)
            count = save_ncdot_layer(layer_name, cleaned)
            total += count
            logger.info("NCDOT %s: %d new features saved (%d fetched)", layer_name, count, len(features))
        logger.info("[5/7] NCDOT Rail Infrastructure: %d total new features saved", total)
    except Exception as e:
        logger.error("[5/7] NCDOT step failed: %s", e)

    # ------------------------------------------------------------------ #
    # [6/7] FRA Grade Crossings
    # ------------------------------------------------------------------ #
    try:
        logger.info("[6/7] Fetching FRA Grade Crossings...")
        crossings = fetch_all_crossings()
        cleaned = clean_fra_records(crossings)
        count = save_fra_crossings(cleaned)
        logger.info("[6/7] FRA Grade Crossings: %d new rows saved (%d fetched)", count, len(crossings))
    except Exception as e:
        logger.error("[6/7] FRA step failed: %s", e)

    # ------------------------------------------------------------------ #
    # [7/7] NC DEQ Environmental
    # ------------------------------------------------------------------ #
    try:
        logger.info("[7/7] Fetching NC DEQ Environmental data...")
        ncdeq_layers = fetch_ncdeq_layers()
        total = 0
        for layer_name, features in ncdeq_layers.items():
            cleaned = clean_spatial_features(features)
            count = save_ncdeq_layer(layer_name, cleaned)
            total += count
            logger.info("NC DEQ %s: %d new features saved (%d fetched)", layer_name, count, len(features))
        logger.info("[7/7] NC DEQ Environmental: %d total new features saved", total)
    except Exception as e:
        logger.error("[7/7] NC DEQ step failed: %s", e)

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
