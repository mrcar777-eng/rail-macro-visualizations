"""
Rail Freight: Carloads vs. Intermodal Volume Chart
===================================================
Plots RAILFRTCARLOADSD11 (carloads) and RAILFRTINTERMODALD11 (intermodal)
on the same y-axis from 2000 onward, with linear trendlines overlaid as
dashed lines. If intermodal volume ever exceeds carloads, the first crossover
date is annotated on the chart.

Run from the project root:
    python visualizations/intermodal_shift.py
"""

from __future__ import annotations

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from visualizations.utils import fetch_series

# ---------------------------------------------------------------------------
# Series identifiers and constants
# ---------------------------------------------------------------------------

CARLOADS_ID = "RAILFRTCARLOADSD11"
INTERMODAL_ID = "RAILFRTINTERMODALD11"
START_DATE = "2000-01-01"

COLOR_CARLOADS = "steelblue"
COLOR_INTERMODAL = "darkorange"


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    try:
        data = fetch_series([CARLOADS_ID, INTERMODAL_ID], start_date=START_DATE)
    except RuntimeError as exc:
        print(f"ERROR: Database connection failed — {exc}", file=sys.stderr)
        sys.exit(1)

    carloads_df = data[CARLOADS_ID]
    intermodal_df = data[INTERMODAL_ID]

    # ------------------------------------------------------------------
    # 2. Guard against empty series
    # ------------------------------------------------------------------
    missing = []
    if carloads_df.empty:
        missing.append(CARLOADS_ID)
    if intermodal_df.empty:
        missing.append(INTERMODAL_ID)

    if missing:
        print(
            f"WARNING: The following series returned no data and cannot be "
            f"plotted: {', '.join(missing)}. Exiting."
        )
        sys.exit(0)

    # ------------------------------------------------------------------
    # 3. Prepare series (set date index, sort ascending)
    # ------------------------------------------------------------------
    carloads = (
        carloads_df.set_index("observation_date")["value"]
        .sort_index()
    )
    intermodal = (
        intermodal_df.set_index("observation_date")["value"]
        .sort_index()
    )

    # ------------------------------------------------------------------
    # 4. Compute linear trendlines via numpy.polyfit
    #    x = ordinal integer representation of dates
    # ------------------------------------------------------------------
    def compute_trendline(series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
        """Return (x_dates, y_trend) arrays for a linear trendline."""
        x_ord = np.array([d.toordinal() for d in series.index])
        y = series.values
        coeffs = np.polyfit(x_ord, y, 1)
        poly = np.poly1d(coeffs)
        y_trend = poly(x_ord)
        return series.index, y_trend

    carloads_trend_dates, carloads_trend_y = compute_trendline(carloads)
    intermodal_trend_dates, intermodal_trend_y = compute_trendline(intermodal)

    # ------------------------------------------------------------------
    # 5. Detect crossover: first date where intermodal > carloads
    # ------------------------------------------------------------------
    # Align both series on a shared date index for comparison
    combined = pd.concat(
        [carloads.rename("carloads"), intermodal.rename("intermodal")],
        axis=1,
        join="inner",
    ).dropna()

    crossover_date: pd.Timestamp | None = None
    if not combined.empty:
        crossover_mask = combined["intermodal"] > combined["carloads"]
        if crossover_mask.any():
            crossover_date = combined.index[crossover_mask.argmax()]

    # ------------------------------------------------------------------
    # 6. Build figure
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 6))

    # Plot raw series
    ax.plot(
        carloads.index,
        carloads.values,
        color=COLOR_CARLOADS,
        linewidth=1.8,
        label="Carloads (RAILFRTCARLOADSD11)",
    )
    ax.plot(
        intermodal.index,
        intermodal.values,
        color=COLOR_INTERMODAL,
        linewidth=1.8,
        label="Intermodal (RAILFRTINTERMODALD11)",
    )

    # Overlay trendlines as dashed lines (same color, no extra legend entry)
    ax.plot(
        carloads_trend_dates,
        carloads_trend_y,
        color=COLOR_CARLOADS,
        linewidth=1.2,
        linestyle="--",
        alpha=0.75,
        label="Carloads trend",
    )
    ax.plot(
        intermodal_trend_dates,
        intermodal_trend_y,
        color=COLOR_INTERMODAL,
        linewidth=1.2,
        linestyle="--",
        alpha=0.75,
        label="Intermodal trend",
    )

    # ------------------------------------------------------------------
    # 7. Annotate crossover point if detected
    # ------------------------------------------------------------------
    if crossover_date is not None:
        crossover_value = combined.loc[crossover_date, "intermodal"]
        label_text = f"Crossover: {crossover_date.strftime('%Y-%m')}"
        ax.annotate(
            label_text,
            xy=(crossover_date, crossover_value),
            xytext=(40, 30),
            textcoords="offset points",
            fontsize=10,
            color="black",
            arrowprops=dict(
                arrowstyle="->",
                color="black",
                lw=1.5,
            ),
        )

    # ------------------------------------------------------------------
    # 8. Labels, title, legend
    # ------------------------------------------------------------------
    ax.set_title(
        "Rail Freight: Carloads vs. Intermodal Volume (2000–Present)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Volume (Carloads)", fontsize=12)
    ax.legend(loc="best", fontsize=10)

    # ------------------------------------------------------------------
    # 9. Finalize
    # ------------------------------------------------------------------
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
