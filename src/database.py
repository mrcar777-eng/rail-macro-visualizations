from __future__ import annotations

import json
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
        # Task 2.1 — STB Waybill
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stb_waybill (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                commodity_code  VARCHAR(10)    NOT NULL,
                stcc_desc       VARCHAR(255),
                origin_bea      VARCHAR(10)    NOT NULL,
                dest_bea        VARCHAR(10),
                routing_miles   DECIMAL(10, 2),
                car_type        VARCHAR(50),
                car_loads       INT,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_stb_waybill (commodity_code, origin_bea, dest_bea, car_type)
            )
        """)
        # Task 2.1 — FAF5 Freight Flows
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faf5_freight_flows (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                dms_orig        VARCHAR(10)    NOT NULL,
                dms_dest        VARCHAR(10)    NOT NULL,
                sctg2           VARCHAR(10)    NOT NULL,
                dms_mode        VARCHAR(10)    NOT NULL,
                tons            DECIMAL(20, 4),
                value_usd_mil   DECIMAL(20, 4),
                tmiles          DECIMAL(20, 4),
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_faf5 (dms_orig, dms_dest, sctg2, dms_mode)
            )
        """)
        # Task 2.2 — NCDOT Rail Lines (spatial)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ncdot_rail_lines (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                objectid        INT            NOT NULL,
                railroad_name   VARCHAR(255),
                track_class     VARCHAR(50),
                geom            LINESTRING     NOT NULL SRID 4326,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ncdot_lines (objectid)
            )
        """)
        # Task 2.2 — NCDOT Rail Crossings (spatial)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ncdot_rail_crossings (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                crossing_id     VARCHAR(50)    NOT NULL,
                street_name     VARCHAR(255),
                railroad_name   VARCHAR(255),
                geom            POINT          NOT NULL SRID 4326,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ncdot_crossings (crossing_id)
            )
        """)
        # Task 2.2 — NCDOT Rail Facilities (spatial)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ncdot_rail_facilities (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                objectid        INT            NOT NULL,
                facility_name   VARCHAR(255),
                facility_type   VARCHAR(100),
                railroad_name   VARCHAR(255),
                geom            POINT          NOT NULL SRID 4326,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ncdot_facilities (objectid)
            )
        """)
        # Task 2.3 — FRA Grade Crossings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fra_grade_crossings (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                crossing_id     VARCHAR(20)    NOT NULL,
                state_code      VARCHAR(5),
                county_name     VARCHAR(100),
                railroad_name   VARCHAR(255),
                street_name     VARCHAR(255),
                crossing_type   VARCHAR(50),
                aadt            INT,
                nbr_tracks      INT,
                total_acc       INT,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_fra_crossing (crossing_id)
            )
        """)
        # Task 2.4 — NC DEQ UST Facilities (spatial)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ncdeq_ust_facilities (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                facility_id     VARCHAR(50)    NOT NULL,
                facility_name   VARCHAR(255),
                owner_name      VARCHAR(255),
                county          VARCHAR(100),
                geom            POINT          NOT NULL SRID 4326,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ncdeq_ust_fac (facility_id)
            )
        """)
        # Task 2.4 — NC DEQ UST Incidents (spatial)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ncdeq_ust_incidents (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                incident_id     VARCHAR(50)    NOT NULL,
                facility_name   VARCHAR(255),
                county          VARCHAR(100),
                incident_date   DATE,
                status          VARCHAR(100),
                geom            POINT          NOT NULL SRID 4326,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ncdeq_ust_inc (incident_id)
            )
        """)
        # Task 2.4 — NC DEQ Active Landfills (spatial, mixed point/polygon)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ncdeq_active_landfills (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                objectid        INT            NOT NULL,
                facility_name   VARCHAR(255),
                county          VARCHAR(100),
                permit_number   VARCHAR(50),
                geom            GEOMETRY       NOT NULL SRID 4326,
                fetched_at      TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ncdeq_landfill (objectid)
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


def save_stb_waybill(records: list) -> int:
    """
    Bulk-insert STB waybill records.
    Uses INSERT IGNORE to skip rows that already exist (uq_stb_waybill).
    Returns the number of newly inserted rows.
    """
    if not records:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    sql = """
        INSERT IGNORE INTO stb_waybill
            (commodity_code, stcc_desc, origin_bea, dest_bea, routing_miles, car_type, car_loads)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    rows = [
        (
            r.get("commodity_code"),
            r.get("stcc_desc"),
            r.get("origin_bea"),
            r.get("dest_bea"),
            r.get("routing_miles"),
            r.get("car_type"),
            r.get("car_loads"),
        )
        for r in records
    ]

    cursor = conn.cursor()
    inserted = 0
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        inserted = cursor.rowcount
    except Error as e:
        logger.error("Error saving STB waybill data: %s", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return inserted


def save_faf5_chunk(chunk) -> int:
    """
    Bulk-insert one FAF5 DataFrame chunk.
    Uses INSERT IGNORE to skip rows that already exist (uq_faf5).
    Returns the number of newly inserted rows.
    """
    import pandas as pd

    if chunk is None or len(chunk) == 0:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    sql = """
        INSERT IGNORE INTO faf5_freight_flows
            (dms_orig, dms_dest, sctg2, dms_mode, tons, value_usd_mil, tmiles)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    # Replace NaN with None for MySQL compatibility
    chunk = chunk.where(pd.notna(chunk), None)

    rows = [
        (
            row.get("dms_orig"),
            row.get("dms_dest"),
            row.get("sctg2"),
            row.get("dms_mode"),
            row.get("tons"),
            row.get("value_usd_mil"),
            row.get("tmiles"),
        )
        for row in chunk.to_dict(orient="records")
    ]

    cursor = conn.cursor()
    inserted = 0
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        inserted = cursor.rowcount
    except Error as e:
        logger.error("Error saving FAF5 chunk: %s", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return inserted


def save_ncdot_layer(layer_name: str, features: list) -> int:
    """
    Bulk-insert NCDOT spatial features into the appropriate table.
    Uses ST_GeomFromGeoJSON(%s, 2, 4326) for geometry.
    Uses INSERT IGNORE. Returns newly inserted row count.
    """
    if not features:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    if layer_name == "rail_lines":
        sql = """
            INSERT IGNORE INTO ncdot_rail_lines (objectid, railroad_name, track_class, geom)
            VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s, 2, 4326))
        """
        rows = [
            (
                f["properties"].get("OBJECTID"),
                f["properties"].get("RAILROAD") or f["properties"].get("OPERATOR"),
                f["properties"].get("TRACKCLASS") or f["properties"].get("TRACK_CLASS"),
                json.dumps(f["geometry"]),
            )
            for f in features
        ]
    elif layer_name == "rail_crossings":
        sql = """
            INSERT IGNORE INTO ncdot_rail_crossings (crossing_id, street_name, railroad_name, geom)
            VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s, 2, 4326))
        """
        rows = [
            (
                f["properties"].get("CrossingId") or f["properties"].get("CROSSINGID") or str(f["properties"].get("OBJECTID")),
                f["properties"].get("STREET") or f["properties"].get("STREETNAME"),
                f["properties"].get("RAILROAD") or f["properties"].get("RAILROAD_NAME"),
                json.dumps(f["geometry"]),
            )
            for f in features
        ]
    elif layer_name == "rail_facilities":
        sql = """
            INSERT IGNORE INTO ncdot_rail_facilities (objectid, facility_name, facility_type, railroad_name, geom)
            VALUES (%s, %s, %s, %s, ST_GeomFromGeoJSON(%s, 2, 4326))
        """
        rows = [
            (
                f["properties"].get("OBJECTID"),
                f["properties"].get("FACILITYNAME") or f["properties"].get("NAME"),
                f["properties"].get("FACILITYTYPE") or f["properties"].get("TYPE"),
                f["properties"].get("RAILROAD") or f["properties"].get("OPERATOR"),
                json.dumps(f["geometry"]),
            )
            for f in features
        ]
    else:
        logger.warning("save_ncdot_layer: unknown layer_name '%s'", layer_name)
        return 0

    cursor = conn.cursor()
    inserted = 0
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        inserted = cursor.rowcount
    except Error as e:
        logger.error("Error saving NCDOT layer '%s': %s", layer_name, e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return inserted


def save_ncdeq_layer(layer_name: str, features: list) -> int:
    """
    Bulk-insert NC DEQ spatial features into the appropriate table.
    Uses ST_GeomFromGeoJSON(%s, 2, 4326) for geometry.
    Uses INSERT IGNORE. Returns newly inserted row count.
    """
    if not features:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    if layer_name == "ust_facilities":
        sql = """
            INSERT IGNORE INTO ncdeq_ust_facilities (facility_id, facility_name, owner_name, county, geom)
            VALUES (%s, %s, %s, %s, ST_GeomFromGeoJSON(%s, 2, 4326))
        """
        rows = [
            (
                str(f["properties"].get("FACILITYID") or f["properties"].get("FacilityID") or f["properties"].get("OBJECTID")),
                f["properties"].get("FACILITYNAME") or f["properties"].get("FacilityName"),
                f["properties"].get("OWNERNAME") or f["properties"].get("OwnerName"),
                f["properties"].get("COUNTY") or f["properties"].get("County"),
                json.dumps(f["geometry"]),
            )
            for f in features
        ]
    elif layer_name == "ust_incidents":
        sql = """
            INSERT IGNORE INTO ncdeq_ust_incidents (incident_id, facility_name, county, incident_date, status, geom)
            VALUES (%s, %s, %s, %s, %s, ST_GeomFromGeoJSON(%s, 2, 4326))
        """
        rows = [
            (
                str(f["properties"].get("INCIDENTID") or f["properties"].get("IncidentID") or f["properties"].get("OBJECTID")),
                f["properties"].get("FACILITYNAME") or f["properties"].get("FacilityName"),
                f["properties"].get("COUNTY") or f["properties"].get("County"),
                f["properties"].get("INCIDENTDATE") or f["properties"].get("IncidentDate"),
                f["properties"].get("STATUS") or f["properties"].get("Status"),
                json.dumps(f["geometry"]),
            )
            for f in features
        ]
    elif layer_name == "active_landfills":
        sql = """
            INSERT IGNORE INTO ncdeq_active_landfills (objectid, facility_name, county, permit_number, geom)
            VALUES (%s, %s, %s, %s, ST_GeomFromGeoJSON(%s, 2, 4326))
        """
        rows = [
            (
                f["properties"].get("OBJECTID")
                or f["properties"].get("Objectid")
                or f["properties"].get("objectid")
                or f["properties"].get("FID"),
                f["properties"].get("FACILITYNAME") or f["properties"].get("FacilityName"),
                f["properties"].get("COUNTY") or f["properties"].get("County"),
                f["properties"].get("PERMITNUMBER") or f["properties"].get("PermitNumber"),
                json.dumps(f["geometry"]),
            )
            for f in features
        ]
        if rows and all(r[0] is None for r in rows):
            sample_keys = list(features[0]["properties"].keys())
            logger.warning(
                "save_ncdeq_layer active_landfills: objectid is None for all rows — "
                "available property keys: %s",
                sample_keys,
            )
    else:
        logger.warning("save_ncdeq_layer: unknown layer_name '%s'", layer_name)
        return 0

    cursor = conn.cursor()
    inserted = 0
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        inserted = cursor.rowcount
    except Error as e:
        logger.error("Error saving NC DEQ layer '%s': %s", layer_name, e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return inserted


def save_fra_crossings(records: list) -> int:
    """
    Bulk-insert FRA grade crossing records.
    Uses INSERT IGNORE to skip rows that already exist (uq_fra_crossing).
    Returns the number of newly inserted rows.
    """
    if not records:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    sql = """
        INSERT IGNORE INTO fra_grade_crossings
            (crossing_id, state_code, county_name, railroad_name, street_name,
             crossing_type, aadt, nbr_tracks, total_acc)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    rows = [
        (
            r.get("CrossingID"),
            r.get("StateCD"),
            r.get("CountyName"),
            r.get("RailroadName") or r.get("Railroad"),
            r.get("StreetName") or r.get("Street"),
            r.get("TypeXing") or r.get("CrossingType"),
            r.get("AADT"),
            r.get("NbrTracks"),
            r.get("TotalAcc"),
        )
        for r in records
    ]

    cursor = conn.cursor()
    inserted = 0
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        inserted = cursor.rowcount
    except Error as e:
        logger.error("Error saving FRA crossings: %s", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return inserted
