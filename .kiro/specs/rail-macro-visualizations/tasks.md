# Tasks: Rail Macro Visualizations

## Task List

- [x] 1. Set up project structure and dependencies
  - [x] 1.1 Create `visualizations/` directory with `__init__.py`
  - [x] 1.2 Add `matplotlib`, `pandas`, `numpy`, `seaborn`, `scipy` to `requirements.txt`

- [x] 2. Implement shared utilities (`visualizations/utils.py`)
  - [x] 2.1 Implement `fetch_series(series_ids, start_date, end_date)` using parameterized SQL queries
  - [x] 2.2 Implement `fetch_edgar_filings(tickers, form_type)` using parameterized SQL queries
  - [x] 2.3 Define `RECESSION_BANDS` constant with all NBER recession date ranges (1945–present)
  - [x] 2.4 Implement `add_recession_shading(ax, start_date, end_date)` using `axvspan`

- [x] 3. Implement Commodity Flow vs. Pricing Power chart (`visualizations/commodity_flow_pricing.py`)
  - [x] 3.1 Fetch `RAILFRTCARLOADSD11` and `PCU4821114821114` from 2015-01-01
  - [x] 3.2 Build dual-axis matplotlib figure (carloads left/blue, PPI right/red)
  - [x] 3.3 Compute and display Pearson correlation coefficient in chart title/subtitle
  - [x] 3.4 Add axis labels, legend, and `plt.tight_layout()` / `plt.show()`

- [x] 4. Implement Intermodal Shift Trendline chart (`visualizations/intermodal_shift.py`)
  - [x] 4.1 Fetch `RAILFRTCARLOADSD11` and `RAILFRTINTERMODALD11` from 2000-01-01
  - [x] 4.2 Plot both series on the same axis with distinct colors and legend
  - [x] 4.3 Compute and overlay linear trendlines via `numpy.polyfit` as dashed lines
  - [x] 4.4 Detect and annotate crossover point if intermodal volume exceeds carloads

- [x] 5. Implement SEC Event Overlay chart (`visualizations/sec_event_overlay.py`)
  - [x] 5.1 Fetch `RAILFRTCARLOADSD11` for full date range
  - [x] 5.2 Fetch 10-K filings for UNP, CSX, NSC from `edgar_filings`
  - [x] 5.3 Plot carloads line and add color-coded `axvline` markers per ticker
  - [x] 5.4 Add legend mapping tickers to colors; handle empty filings gracefully with warning

- [x] 6. Implement Historical Resilience Model chart (`visualizations/historical_resilience.py`)
  - [x] 6.1 Fetch `CES4348200001` for full date range (1947+)
  - [x] 6.2 Apply NBER recession shading via `add_recession_shading`
  - [x] 6.3 Annotate peak-to-trough drop percentage for each major recession
  - [x] 6.4 Format x-axis in decade increments

- [x] 7. Implement Lead-Lag Correlation Heatmap (`visualizations/lead_lag_heatmap.py`)
  - [x] 7.1 Fetch `RAILFRTCARLOADSD11`, `PCU4821114821114`, `CES4348200001`
  - [x] 7.2 Implement `compute_lead_lag_correlation(base, targets, lags)` using `scipy.stats.pearsonr`
  - [x] 7.3 Build correlation matrix DataFrame (rows = target series, columns = lag months)
  - [x] 7.4 Render heatmap with `seaborn.heatmap`, annotated values, and `"coolwarm"` colormap
  - [x] 7.5 Handle insufficient-overlap cells as NaN with stdout warning

- [x] 8. Add error handling across all scripts
  - [x] 8.1 Add DB connection failure guard (print error + `sys.exit(1)`) to each script
  - [x] 8.2 Add missing-series guard (print warning + graceful exit) to each script
