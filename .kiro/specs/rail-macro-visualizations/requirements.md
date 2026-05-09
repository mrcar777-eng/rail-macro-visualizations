# Requirements Document: Rail Macro Visualizations

## Introduction

This document defines the functional and non-functional requirements for the Rail Macro Visualizations feature. The feature consists of five standalone Python scripts that query the existing `rail_macro_db` MySQL database and render financial/economic charts for rail sector analysis. Requirements are derived from the design document.

---

## Requirements

### 1. Shared Data Access Utilities

#### 1.1 DB Query Utility — FRED Series

**User Story**: As a data analyst, I want a reusable function to fetch FRED time-series data from the database so that each visualization script does not duplicate query logic.

**Acceptance Criteria**:

- 1.1.1 `fetch_series(series_ids, start_date, end_date)` queries `fred_observations` and returns a `dict[str, pd.DataFrame]` with one key per requested series ID.
- 1.1.2 Each returned DataFrame has exactly two columns: `observation_date` (datetime) and `value` (float64), sorted ascending by `observation_date`.
- 1.1.3 Rows where `value` is NULL or NaN are excluded from the returned DataFrames.
- 1.1.4 When `start_date` is provided, only rows with `observation_date >= start_date` are returned.
- 1.1.5 When a series ID has no matching rows, the function returns an empty DataFrame for that key (not an exception).
- 1.1.6 The function uses parameterized SQL queries (no string interpolation of user values).

#### 1.2 DB Query Utility — Edgar Filings

**User Story**: As a data analyst, I want a reusable function to fetch SEC filing dates from the database so that the event overlay chart can access them without duplicating query logic.

**Acceptance Criteria**:

- 1.2.1 `fetch_edgar_filings(tickers, form_type)` queries `edgar_filings` and returns a `pd.DataFrame` with columns: `ticker` (str), `filing_date` (datetime), `report_date` (datetime).
- 1.2.2 Results are filtered to only the specified `tickers` and `form_type`.
- 1.2.3 When no matching rows exist, the function returns an empty DataFrame (not an exception).

#### 1.3 Recession Band Constants

**User Story**: As a data analyst, I want NBER recession date ranges available as a constant so that any chart can apply consistent recession shading without hardcoding dates in each script.

**Acceptance Criteria**:

- 1.3.1 `RECESSION_BANDS` is defined in `visualizations/utils.py` as a list of `(start_date, end_date)` string tuples covering all official US recessions from 1945 to present.
- 1.3.2 `add_recession_shading(ax, start_date, end_date)` applies a gray `axvspan` for each recession band that overlaps the provided date range.
- 1.3.3 Recession bands outside the chart's visible date range are silently skipped (no error).

---

### 2. Commodity Flow vs. Pricing Power Chart

**User Story**: As a financial analyst, I want to see Rail Freight Carloads plotted against the Rail PPI on a dual-axis chart from 2015 onward so that I can assess whether volume drops correlate with pricing power changes.

**Acceptance Criteria**:

- 2.1 The script `visualizations/commodity_flow_pricing.py` is independently executable via `python visualizations/commodity_flow_pricing.py`.
- 2.2 The chart fetches `RAILFRTCARLOADSD11` and `PCU4821114821114` with `start_date = "2015-01-01"`.
- 2.3 Carloads are plotted on the left y-axis in blue; Rail PPI is plotted on the right y-axis in red.
- 2.4 The chart title or subtitle displays the Pearson correlation coefficient between the two series.
- 2.5 Both axes are labeled with the series name and units.
- 2.6 A legend identifies each line.

---

### 3. Intermodal Shift Trendline Chart

**User Story**: As a supply chain analyst, I want a comparative time-series chart from 2000 to 2026 showing Carloads vs. Intermodal volume with trendlines so that I can visualize the structural shift in rail freight over two decades.

**Acceptance Criteria**:

- 3.1 The script `visualizations/intermodal_shift.py` is independently executable.
- 3.2 The chart fetches `RAILFRTCARLOADSD11` and `RAILFRTINTERMODALD11` with `start_date = "2000-01-01"`.
- 3.3 Both series are plotted on the same y-axis with distinct colors and a legend.
- 3.4 A linear trendline (computed via `numpy.polyfit`) is overlaid for each series as a dashed line.
- 3.5 If the two series cross (intermodal volume exceeds carloads), the crossover point is annotated on the chart.
- 3.6 Trendlines do not extend beyond the range of available data.

---

### 4. SEC Event Overlay Chart

**User Story**: As a corporate analyst, I want 10-K filing dates for UNP, CSX, and NSC overlaid as vertical markers on the carloads time series so that I can identify whether major corporate activity clusters around macroeconomic troughs or peaks.

**Acceptance Criteria**:

- 4.1 The script `visualizations/sec_event_overlay.py` is independently executable.
- 4.2 The chart fetches `RAILFRTCARLOADSD11` for the full available date range.
- 4.3 The chart fetches 10-K filings for tickers `["UNP", "CSX", "NSC"]` from `edgar_filings`.
- 4.4 Each filing date is rendered as a vertical line (`axvline`) color-coded by ticker (three distinct colors).
- 4.5 A legend maps each ticker to its marker color.
- 4.6 When `edgar_filings` contains no 10-K rows for the target tickers, the chart renders the carloads line without markers and prints a warning to stdout.

---

### 5. Historical Resilience Model Chart

**User Story**: As a macro economist, I want a long-run rail employment chart from 1947 onward with NBER recession shading so that I can measure how deeply the rail sector drops during economic shocks and how quickly it recovers.

**Acceptance Criteria**:

- 5.1 The script `visualizations/historical_resilience.py` is independently executable.
- 5.2 The chart fetches `CES4348200001` for the full available date range (starting from 1947 where available).
- 5.3 Each NBER recession band is shaded in light gray using `axvspan`.
- 5.4 The peak-to-trough employment drop percentage is annotated for each major recession visible in the chart.
- 5.5 The x-axis is labeled in decade increments for readability.

---

### 6. Lead-Lag Correlation Heatmap

**User Story**: As a quantitative analyst, I want a heatmap showing the Pearson correlation between rail volume at time `t` and rail PPI / employment at `t + lag` for lags of 1, 2, 3, 6, 9, and 12 months so that I can identify predictive lead-lag relationships for financial forecasting.

**Acceptance Criteria**:

- 6.1 The script `visualizations/lead_lag_heatmap.py` is independently executable.
- 6.2 The chart fetches `RAILFRTCARLOADSD11`, `PCU4821114821114`, and `CES4348200001`.
- 6.3 Pearson correlation is computed between carloads at time `t` and each target series at `t + lag` for lags `[1, 2, 3, 6, 9, 12]` months.
- 6.4 The heatmap has rows for each target series (`"Rail PPI"`, `"Employment"`) and columns for each lag value.
- 6.5 Cell values are annotated on the heatmap.
- 6.6 A diverging colormap (e.g., `"coolwarm"`) is used so positive and negative correlations are visually distinct.
- 6.7 When a `(series, lag)` pair has fewer than 12 overlapping observations, the cell is set to `NaN` and rendered as a blank/gray cell; a warning is printed to stdout.

---

### 7. Error Handling and Robustness

**User Story**: As a developer, I want each visualization script to fail gracefully with informative messages so that users can diagnose and fix data availability issues without reading tracebacks.

**Acceptance Criteria**:

- 7.1 When `get_db_connection()` returns `None`, the script prints a descriptive error message and exits with code 1 before attempting to render.
- 7.2 When a required FRED series has no rows in `fred_observations`, the script prints a warning identifying the missing series and exits gracefully (no unhandled exception).
- 7.3 No script raises an unhandled exception during normal execution when the DB is reachable and contains data.

---

### 8. Project Structure and Dependencies

**User Story**: As a developer, I want the visualization scripts organized in a `visualizations/` directory and all required packages listed in `requirements.txt` so that the project is easy to set up and navigate.

**Acceptance Criteria**:

- 8.1 All visualization scripts and `utils.py` reside in a `visualizations/` directory at the project root.
- 8.2 `visualizations/__init__.py` exists to make the directory a Python package.
- 8.3 `requirements.txt` includes `matplotlib`, `pandas`, `numpy`, `seaborn`, and `scipy`.
- 8.4 Each script imports DB utilities from `src.database` and config from `config` using the existing project import paths (no path manipulation hacks).
- 8.5 DB credentials are loaded exclusively from environment variables via `.env`; no credentials are hardcoded in any visualization script.
