import logging

from config import FRED_SERIES_IDS
from src.api_fred import fetch_all_series
from src.api_edgar import fetch_all_companies
from src.database import create_tables, save_fred_data, save_edgar_filings, get_latest_fred_date
from src.data_cleaner import clean_fred_observations, clean_edgar_filings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    logger.info("=== Rail Macro Data Pipeline ===")

    create_tables()

    logger.info("[1/2] Fetching FRED macro series...")
    latest_dates = {sid: get_latest_fred_date(sid) for sid in FRED_SERIES_IDS}
    fred_data = fetch_all_series(latest_dates=latest_dates)
    for series_id, observations in fred_data.items():
        cleaned = clean_fred_observations(observations)
        count = save_fred_data(series_id, cleaned)
        logger.info("%s: %d new rows saved (%d fetched from API)", series_id, count, len(cleaned))

    logger.info("[2/2] Fetching SEC Edgar filings (10-K / 10-Q)...")
    edgar_data = fetch_all_companies()
    for ticker, filings in edgar_data.items():
        cleaned = clean_edgar_filings(filings)
        count = save_edgar_filings(cleaned)
        logger.info("%s: %d new filings saved (%d fetched from API)", ticker, count, len(cleaned))

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
