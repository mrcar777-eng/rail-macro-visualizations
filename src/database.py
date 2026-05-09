from __future__ import annotations

import logging

import mysql.connector
from mysql.connector import Error

from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)


def get_db_connection() -> mysql.connector.MySQLConnection | None:
    """Return an open MySQL connection, or None on failure."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
        if conn.is_connected():
            return conn
    except Error as e:
        logger.error("Database connection error: %s", e)
    return None


def create_tables() -> None:
    """Create fred_observations and edgar_filings tables if they don't exist."""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fred_observations (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                series_id        VARCHAR(50)    NOT NULL,
                observation_date DATE           NOT NULL,
                value            DECIMAL(20, 4),
                fetched_at       TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_series_date (series_id, observation_date)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edgar_filings (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                ticker           VARCHAR(10)    NOT NULL,
                cik              VARCHAR(20)    NOT NULL,
                form_type        VARCHAR(20),
                filing_date      DATE,
                report_date      DATE,
                accession_number VARCHAR(30),
                fetched_at       TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_accession (accession_number)
            )
        """)
        conn.commit()
        logger.info("Tables created/verified.")
    except Error as e:
        logger.error("Error creating tables: %s", e)
    finally:
        cursor.close()
        conn.close()


def get_latest_fred_date(series_id: str) -> str | None:
    """Return the most recent observation_date stored for a series, or None."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT MAX(observation_date) FROM fred_observations WHERE series_id = %s",
            (series_id,)
        )
        row = cursor.fetchone()
        return str(row[0]) if row and row[0] else None
    finally:
        cursor.close()
        conn.close()


def save_fred_data(series_id: str, observations: list) -> int:
    """
    Bulk-insert FRED observations for one series.
    Uses INSERT IGNORE to skip rows that already exist (uq_series_date).
    Returns the number of newly inserted rows.
    """
    if not observations:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    sql = """
        INSERT IGNORE INTO fred_observations (series_id, observation_date, value)
        VALUES (%s, %s, %s)
    """
    rows = [
        (series_id, obs["date"], obs["value"])
        for obs in observations
    ]

    cursor = conn.cursor()
    inserted = 0
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        inserted = cursor.rowcount
    except Error as e:
        logger.error("Error saving FRED data for %s: %s", series_id, e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return inserted


def save_edgar_filings(filings: list) -> int:
    """
    Bulk-insert Edgar filings.
    Uses INSERT IGNORE to skip filings already stored (uq_accession).
    Returns the number of newly inserted rows.
    """
    if not filings:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    sql = """
        INSERT IGNORE INTO edgar_filings
            (ticker, cik, form_type, filing_date, report_date, accession_number)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    rows = [
        (
            f["ticker"],
            f["cik"],
            f["form_type"],
            f["filing_date"]      or None,
            f["report_date"]      or None,
            f["accession_number"],
        )
        for f in filings
    ]

    cursor = conn.cursor()
    inserted = 0
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        inserted = cursor.rowcount
    except Error as e:
        logger.error("Error saving Edgar filings: %s", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return inserted
