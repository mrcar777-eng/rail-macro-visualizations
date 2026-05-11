# Requirements Document

## Introduction

This feature extends the existing `rail-macro-db` data pipeline to ingest data from five new sources:
STB Public Use Carload Waybill Sample, FAF5 Freight Flow Data, NCDOT Rail Infrastructure,
FRA Grade Crossing Inventory System, and NC DEQ Environmental Data (UST/Landfill).
All new data is gathered through `main.py` using the existing fetch → clean → save pattern,
stored in the MySQL `rail_macro_db` database, and deduplicated via `INSERT IGNORE`.
No visualizations are produced by this feature. API credentials are stored as placeholders
in `.env` and loaded through `config.py`.

## Glossary

- **Pipeline**: The `main.py` orchestration script that runs all data-gathering modules in sequence.
- **STB_Fetcher**: The module responsible for fetching data from the STB Waybill Socrata/SODA API.
- **FAF5_Fetcher**: The module responsible for downloading and ingesting FAF5 CSV freight flow files.
- **NCDOT_Fetcher**: The module responsible for querying NCDOT ArcGIS REST endpoints for rail infrastructure geometry.
- **FRA_Fetcher**: The module responsible for paginating the FRA Grade Crossing OData API with token refresh.
- **NCDEQ_Fetcher**: The module responsible for querying NC DEQ ArcGIS REST endpoints for environmental spatial data.
- **Cleaner**: The `data_cleaner.py` module extended with cleaning functions for each new source.
- **Database**: The `database.py` module extended with table-creation and save functions for each new source.
- **Config**: The `config.py` module that loads all credentials and settings from `.env`.
- **SRID 4326**: The WGS 84 geographic coordinate reference system used for all spatial columns.
- **INSERT IGNORE**: MySQL statement that silently skips rows that violate a UNIQUE constraint, preventing duplicates.
- **App_Token**: The Socrata application token sent in the `X-App-Token` HTTP header for STB API requests.
- **FRA_Token**: The time-limited bearer token (20-minute expiry) required by the FRA OData API.
- **Chunk**: A fixed-size batch of rows read from a large CSV file using pandas `chunksize` to limit memory use.
- **ArcGIS_REST**: The Esri ArcGIS REST API pattern used by both NCDOT and NC DEQ spatial endpoints.
- **UST**: Underground Storage Tank, an environmental facility type tracked by NC DEQ.

---

## Requirements

### Requirement 1: Configuration and Credential Management

**User Story:** As a developer, I want all new API keys and tokens stored as named placeholders in `.env`,
so that I can replace them with real values when credentials become available without changing source code.

#### Acceptance Criteria

1. THE Config SHALL load `STB_APP_TOKEN` from the `.env` file and expose it as `STB_APP_TOKEN`.
2. THE Config SHALL load `FRA_API_TOKEN` from the `.env` file and expose it as `FRA_API_TOKEN`.
3. THE `.env` file SHALL contain placeholder entries `STB_APP_TOKEN=YOUR_STB_APP_TOKEN_HERE` and `FRA_API_TOKEN=YOUR_FRA_API_TOKEN_HERE`.
4. THE `.env.example` file SHALL contain the same placeholder keys as the `.env` file so that new developers can replicate the required environment.
5. WHEN any fetcher module reads a credential from Config, THE Config SHALL return the value loaded by `python-dotenv` without modification.

---

### Requirement 2: STB Waybill Data Ingestion

**User Story:** As a data analyst, I want US railroad carload movement records from the STB Waybill dataset,
so that I can analyze commodity flows, routing miles, and equipment types across BEA origin/destination zones.

#### Acceptance Criteria

1. WHEN the Pipeline runs the STB step, THE STB_Fetcher SHALL send a GET request to the STB Socrata/SODA API endpoint with the `X-App-Token` header set to `STB_APP_TOKEN`.
2. WHEN the STB API returns a successful response, THE STB_Fetcher SHALL parse the JSON array and return a list of waybill record dictionaries.
3. IF the STB API returns an HTTP error status, THEN THE STB_Fetcher SHALL log a warning with the status code and return an empty list without raising an exception.
4. THE Database SHALL maintain a `stb_waybill` table with columns for: commodity code, STCC description, origin BEA zone, destination BEA zone, routing miles, car type, car loads, and a `fetched_at` timestamp.
5. THE `stb_waybill` table SHALL have a UNIQUE constraint on the natural key that identifies a single waybill record to prevent duplicate rows.
6. WHEN the Cleaner processes STB records, THE Cleaner SHALL drop any record where commodity code or origin BEA zone is null or empty.
7. WHEN the Cleaner processes STB records, THE Cleaner SHALL coerce routing miles to a numeric type and drop records where the coercion fails.
8. WHEN the Database saves STB records, THE Database SHALL use `INSERT IGNORE` so that re-running the Pipeline does not create duplicate rows.
9. WHEN the Database saves STB records, THE Database SHALL return the count of newly inserted rows.

---

### Requirement 3: FAF5 Freight Flow Data Ingestion

**User Story:** As a data analyst, I want national freight tonnage, value, and ton-miles data from the FAF5
Origin-Destination-Commodity-Mode matrices, so that I can compare rail freight volumes against other modes.

#### Acceptance Criteria

1. WHEN the Pipeline runs the FAF5 step, THE FAF5_Fetcher SHALL download the FAF5 CSV file from the configured public URL using an HTTP GET request.
2. WHEN the FAF5 CSV file exceeds 100 MB, THE FAF5_Fetcher SHALL read the file using pandas with a `chunksize` parameter so that no single chunk exceeds available memory.
3. WHEN the FAF5_Fetcher processes each Chunk, THE FAF5_Fetcher SHALL pass the chunk to the Cleaner before inserting it into the Database.
4. THE Database SHALL maintain a `faf5_freight_flows` table with columns for: origin zone, destination zone, commodity code, mode code, tons, value (USD millions), ton-miles, and a `fetched_at` timestamp.
5. THE `faf5_freight_flows` table SHALL have a UNIQUE constraint on the combination of origin zone, destination zone, commodity code, and mode code to prevent duplicate rows.
6. WHEN the Cleaner processes a FAF5 Chunk, THE Cleaner SHALL drop rows where origin zone, destination zone, commodity code, or mode code is null.
7. WHEN the Cleaner processes a FAF5 Chunk, THE Cleaner SHALL coerce tons, value, and ton-miles columns to numeric types and replace non-numeric values with NULL rather than dropping the row.
8. WHEN the Database saves FAF5 rows, THE Database SHALL use `INSERT IGNORE` so that re-running the Pipeline does not create duplicate rows.
9. WHEN the Database saves FAF5 rows, THE Database SHALL return the cumulative count of newly inserted rows across all chunks.
10. IF the FAF5 download request fails with an HTTP error, THEN THE FAF5_Fetcher SHALL log a warning and return without inserting any rows.

---

### Requirement 4: NCDOT Rail Infrastructure Spatial Data Ingestion

**User Story:** As a data analyst, I want NC rail track lines, railroad crossings, and railroad facility locations
from NCDOT stored with proper spatial geometry, so that I can perform proximity and corridor analysis.

#### Acceptance Criteria

1. WHEN the Pipeline runs the NCDOT step, THE NCDOT_Fetcher SHALL query the NCDOT ArcGIS REST API for three feature layers: rail track lines (polyline), railroad crossings (point), and railroad facilities (point).
2. WHEN the NCDOT_Fetcher queries an ArcGIS REST endpoint, THE NCDOT_Fetcher SHALL request GeoJSON output format and paginate using `resultOffset` until all features are retrieved.
3. IF an ArcGIS REST request returns an HTTP error or a JSON error object, THEN THE NCDOT_Fetcher SHALL log a warning and skip that layer without halting the Pipeline.
4. THE Database SHALL maintain a `ncdot_rail_lines` table with a `GEOMETRY` column typed as `LINESTRING` with SRID 4326, plus columns for: railroad name, track class, and a `fetched_at` timestamp.
5. THE Database SHALL maintain a `ncdot_rail_crossings` table with a `GEOMETRY` column typed as `POINT` with SRID 4326, plus columns for: crossing ID, street name, railroad name, and a `fetched_at` timestamp.
6. THE Database SHALL maintain a `ncdot_rail_facilities` table with a `GEOMETRY` column typed as `POINT` with SRID 4326, plus columns for: facility name, facility type, railroad name, and a `fetched_at` timestamp.
7. THE `ncdot_rail_lines` table SHALL have a UNIQUE constraint on a natural key (such as a feature object ID) to prevent duplicate rows.
8. THE `ncdot_rail_crossings` table SHALL have a UNIQUE constraint on crossing ID to prevent duplicate rows.
9. THE `ncdot_rail_facilities` table SHALL have a UNIQUE constraint on a natural key (such as a feature object ID) to prevent duplicate rows.
10. WHEN the Cleaner processes NCDOT features, THE Cleaner SHALL drop any feature whose geometry is null or whose coordinate array is empty.
11. WHEN the Database saves NCDOT spatial records, THE Database SHALL use `ST_GeomFromText` with SRID 4326 to insert geometry values.
12. WHEN the Database saves NCDOT spatial records, THE Database SHALL use `INSERT IGNORE` so that re-running the Pipeline does not create duplicate rows.

---

### Requirement 5: FRA Grade Crossing Inventory Data Ingestion

**User Story:** As a data analyst, I want national railroad grade crossing records including safety data and
accident statistics from the FRA Grade Crossing Inventory System, so that I can assess crossing risk along rail corridors.

#### Acceptance Criteria

1. WHEN the Pipeline runs the FRA step, THE FRA_Fetcher SHALL obtain a valid `FRA_Token` before making any data requests.
2. WHEN the `FRA_Token` is within 2 minutes of its 20-minute expiry, THE FRA_Fetcher SHALL request a new token before continuing pagination.
3. WHEN the FRA_Fetcher paginates the OData API, THE FRA_Fetcher SHALL use `$skip` and `$top` query parameters to retrieve all records in sequential pages.
4. WHEN the FRA OData API returns a page of records, THE FRA_Fetcher SHALL append the records to the result set and advance the `$skip` offset by the page size.
5. WHEN the FRA OData API returns an empty `value` array, THE FRA_Fetcher SHALL stop pagination and return the accumulated records.
6. IF the FRA OData API returns an HTTP 401 response, THEN THE FRA_Fetcher SHALL refresh the token once and retry the same page before logging a failure.
7. IF the FRA OData API returns any other HTTP error status, THEN THE FRA_Fetcher SHALL log a warning with the status code and stop pagination, returning records collected so far.
8. THE Database SHALL maintain a `fra_grade_crossings` table with columns for: crossing ID, state code, county name, railroad name, street name, crossing type, annual average daily traffic, number of tracks, accident count, and a `fetched_at` timestamp.
9. THE `fra_grade_crossings` table SHALL have a UNIQUE constraint on crossing ID to prevent duplicate rows.
10. WHEN the Cleaner processes FRA records, THE Cleaner SHALL drop any record where crossing ID is null or empty.
11. WHEN the Cleaner processes FRA records, THE Cleaner SHALL coerce numeric fields (traffic count, track count, accident count) to integers and replace non-numeric values with NULL rather than dropping the row.
12. WHEN the Database saves FRA records, THE Database SHALL use `INSERT IGNORE` so that re-running the Pipeline does not create duplicate rows.
13. WHEN the Database saves FRA records, THE Database SHALL return the count of newly inserted rows.

---

### Requirement 6: NC DEQ Environmental Spatial Data Ingestion

**User Story:** As a data analyst, I want locations of active UST facilities, UST incidents, and active landfills
from NC DEQ stored with spatial geometry, so that I can identify environmental risk factors near rail corridors.

#### Acceptance Criteria

1. WHEN the Pipeline runs the NC DEQ step, THE NCDEQ_Fetcher SHALL query the NC DEQ ArcGIS REST API for three feature layers: active UST facilities (point), UST incidents (point), and active landfills (point or polygon).
2. WHEN the NCDEQ_Fetcher queries an ArcGIS REST endpoint, THE NCDEQ_Fetcher SHALL request GeoJSON output format and paginate using `resultOffset` until all features are retrieved.
3. IF an ArcGIS REST request returns an HTTP error or a JSON error object, THEN THE NCDEQ_Fetcher SHALL log a warning and skip that layer without halting the Pipeline.
4. THE Database SHALL maintain a `ncdeq_ust_facilities` table with a `GEOMETRY` column typed as `POINT` with SRID 4326, plus columns for: facility ID, facility name, owner name, county, and a `fetched_at` timestamp.
5. THE Database SHALL maintain a `ncdeq_ust_incidents` table with a `GEOMETRY` column typed as `POINT` with SRID 4326, plus columns for: incident ID, facility name, county, incident date, status, and a `fetched_at` timestamp.
6. THE Database SHALL maintain a `ncdeq_active_landfills` table with a `GEOMETRY` column typed as `GEOMETRY` with SRID 4326 (to accommodate both point and polygon features), plus columns for: facility ID, facility name, county, permit number, and a `fetched_at` timestamp.
7. THE `ncdeq_ust_facilities` table SHALL have a UNIQUE constraint on facility ID to prevent duplicate rows.
8. THE `ncdeq_ust_incidents` table SHALL have a UNIQUE constraint on incident ID to prevent duplicate rows.
9. THE `ncdeq_active_landfills` table SHALL have a UNIQUE constraint on a natural key (such as a feature object ID) to prevent duplicate rows.
10. WHEN the Cleaner processes NC DEQ features, THE Cleaner SHALL drop any feature whose geometry is null or whose coordinate array is empty.
11. WHEN the Database saves NC DEQ spatial records, THE Database SHALL use `ST_GeomFromText` with SRID 4326 to insert geometry values.
12. WHEN the Database saves NC DEQ spatial records, THE Database SHALL use `INSERT IGNORE` so that re-running the Pipeline does not create duplicate rows.

---

### Requirement 7: Pipeline Orchestration

**User Story:** As a developer, I want all five new data sources to run sequentially through `main.py`
alongside the existing FRED and Edgar steps, so that a single command gathers all data in a consistent order.

#### Acceptance Criteria

1. WHEN `main.py` is executed, THE Pipeline SHALL run the five new data-gathering steps after the existing FRED and Edgar steps.
2. THE Pipeline SHALL run the new steps in this order: STB Waybill, FAF5 Freight Flow, NCDOT Rail Infrastructure, FRA Grade Crossings, NC DEQ Environmental.
3. WHEN any single data-gathering step raises an unhandled exception, THE Pipeline SHALL log the error and continue to the next step rather than halting the entire run.
4. WHEN each step completes, THE Pipeline SHALL log the step name and the count of newly inserted rows.
5. THE Pipeline SHALL call `create_tables()` once at startup so that all new tables are created before any fetch step runs.
6. WHEN the Pipeline completes all steps, THE Pipeline SHALL log a final "Pipeline complete" message.
