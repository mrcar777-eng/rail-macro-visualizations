"""
Rail Employment Historical Resilience Chart
===========================================
Plots CES4348200001 (rail employment) from 1947 onward with NBER recession
shading and peak-to-trough drop annotations for each visible recession.

Run from the project root:
    python visualizations/historical_resilience.py
"""

from __future__ import annotations

import sys

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

from visualizations.utils import RECESSION_BANDS, add_recession_shading, fetch_series

# ---------------------------------------------------------------------------
# Series identifier
# ---------------------------------------------------------------------------

EMPLOYMENT_ID = "CES4348200001"


def compute_peak_trough(
    series: pd.Series,
    rec_start: pd.Timestamp,
    rec_end: pd.Timestamp,
) -> tuple[float | None, float | None, pd.Timestamp | None]:
    """
    Compute the peak value in the 6 months before *rec_start* and the trough
    (minimum) during the recession window [rec_start, rec_end].

    Returns
    -------
    (peak, trough, trough_date) or (None, None, None) if insufficient data.
    """
    # Pre-recession window: 6 months before recession start
    pre_start = rec_start - pd.DateOffset(months=6)
    pre_window = series[(series.index >= pre_start) & (series.index < rec_start)]

    # Recession window
    rec_window = series[(series.index >= rec_start) & (series.index <= rec_end)]

    if len(pre_window) < 1 or len(rec_window) < 3:
        return None, None, None

    peak = pre_window.max()
    trough_date = rec_window.idxmin()
    trough = rec_window.min()

    return peak, trough, trough_date


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Fetch data — no date filter to get the full available range
    # ------------------------------------------------------------------
    try:
        data = fetch_series([EMPLOYMENT_ID])
    except RuntimeError as exc:
        print(f"ERROR: Database connection failed — {exc}", file=sys.stderr)
        sys.exit(1)

    emp_df = data[EMPLOYMENT_ID]

    if emp_df.empty:
        print(
            f"WARNING: Series {EMPLOYMENT_ID} returned no data. Exiting."
        )
        sys.exit(0)

    # ------------------------------------------------------------------
    # 2. Prepare series
    # ------------------------------------------------------------------
    employment = (
        emp_df.set_index("observation_date")["value"]
        .sort_index()
    )

    chart_start = employment.index.min()
    chart_end = employment.index.max()

    chart_start_str = chart_start.strftime("%Y-%m-%d")
    chart_end_str = chart_end.strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # 3. Build figure
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 7))

    # Plot employment line
    (emp_line,) = ax.plot(
        employment.index,
        employment.values,
        color="steelblue",
        linewidth=1.8,
        label="Rail Employment (CES4348200001)",
    )

    # ------------------------------------------------------------------
    # 4. Apply NBER recession shading
    # ------------------------------------------------------------------
    add_recession_shading(ax, start_date=chart_start_str, end_date=chart_end_str)

    # ------------------------------------------------------------------
    # 5. Annotate peak-to-trough drop for each visible recession
    # ------------------------------------------------------------------
    for band_start_str, band_end_str in RECESSION_BANDS:
        rec_start = pd.Timestamp(band_start_str)
        rec_end = pd.Timestamp(band_end_str)

        # Skip bands entirely outside the chart range
        if rec_end < chart_start or rec_start > chart_end:
            continue

        peak, trough, trough_date = compute_peak_trough(
            employment, rec_start, rec_end
        )

        if peak is None or trough is None or trough_date is None:
            continue

        if peak == 0:
            continue

        drop_pct = (trough - peak) / peak * 100

        # Skip negligible drops
        if abs(drop_pct) < 0.5:
            continue

        ax.annotate(
            f"{drop_pct:.1f}%",
            xy=(trough_date, trough),
            xytext=(0, 10),
            textcoords="offset points",
            fontsize=8,
            ha="center",
            color="darkred",
        )

    # ------------------------------------------------------------------
    # 6. X-axis: decade increments
    # ------------------------------------------------------------------
    ax.xaxis.set_major_locator(mdates.YearLocator(10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.autofmt_xdate(rotation=45)

    # ------------------------------------------------------------------
    # 7. Labels and title
    # ------------------------------------------------------------------
    ax.set_title(
        "Rail Employment Historical Resilience (1947–Present)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Rail Employment (Thousands)", fontsize=12)

    # ------------------------------------------------------------------
    # 8. Legend — employment line + recession shading patch
    # ------------------------------------------------------------------
    recession_patch = mpatches.Patch(
        facecolor="gray", alpha=0.2, label="NBER Recession"
    )
    ax.legend(handles=[emp_line, recession_patch], loc="best", fontsize=10)

    # ------------------------------------------------------------------
    # 9. Finalize
    # ------------------------------------------------------------------
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
