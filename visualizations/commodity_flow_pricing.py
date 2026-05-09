"""
Commodity Flow vs. Pricing Power Chart
=======================================
Plots Rail Freight Carloads (RAILFRTCARLOADSD11) on the left y-axis and
Rail PPI (PCU4821114821114) on the right y-axis from 2015 onward.
Displays the Pearson correlation coefficient between the two series.

Run from the project root:
    python visualizations/commodity_flow_pricing.py
"""

from __future__ import annotations

import sys

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import pearsonr

from visualizations.utils import fetch_series

# ---------------------------------------------------------------------------
# Series identifiers
# ---------------------------------------------------------------------------

CARLOADS_ID = "RAILFRTCARLOADSD11"
PPI_ID = "PCU4821114821114"
START_DATE = "2015-01-01"


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    try:
        data = fetch_series([CARLOADS_ID, PPI_ID], start_date=START_DATE)
    except RuntimeError as exc:
        print(f"ERROR: Database connection failed — {exc}", file=sys.stderr)
        sys.exit(1)

    carloads_df = data[CARLOADS_ID]
    ppi_df = data[PPI_ID]

    # ------------------------------------------------------------------
    # 2. Guard against empty series
    # ------------------------------------------------------------------
    missing = []
    if carloads_df.empty:
        missing.append(CARLOADS_ID)
    if ppi_df.empty:
        missing.append(PPI_ID)

    if missing:
        print(
            f"WARNING: The following series returned no data and cannot be "
            f"plotted: {', '.join(missing)}. Exiting.",
            file=sys.stderr,
        )
        sys.exit(0)

    # ------------------------------------------------------------------
    # 3. Align both series on a shared date index (inner join)
    # ------------------------------------------------------------------
    carloads_df = carloads_df.set_index("observation_date")["value"]
    ppi_df = ppi_df.set_index("observation_date")["value"]

    aligned = pd.concat(
        [carloads_df.rename("carloads"), ppi_df.rename("ppi")],
        axis=1,
        join="inner",
    ).dropna()

    if aligned.empty:
        print(
            "WARNING: No overlapping dates between the two series after "
            "alignment. Cannot compute correlation or render chart. Exiting.",
            file=sys.stderr,
        )
        sys.exit(0)

    # ------------------------------------------------------------------
    # 4. Compute Pearson correlation coefficient
    # ------------------------------------------------------------------
    r_value, _ = pearsonr(aligned["carloads"], aligned["ppi"])

    # ------------------------------------------------------------------
    # 5. Build dual-axis figure
    # ------------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(14, 6))

    # Left axis — carloads (blue)
    color_carloads = "steelblue"
    line1, = ax1.plot(
        aligned.index,
        aligned["carloads"],
        color=color_carloads,
        linewidth=1.8,
        label="Rail Freight Carloads",
    )
    ax1.set_xlabel("Date", fontsize=12)
    ax1.set_ylabel("Rail Freight Carloads (Carloads)", color=color_carloads, fontsize=12)
    ax1.tick_params(axis="y", labelcolor=color_carloads)

    # Right axis — Rail PPI (red)
    ax2 = ax1.twinx()
    color_ppi = "firebrick"
    line2, = ax2.plot(
        aligned.index,
        aligned["ppi"],
        color=color_ppi,
        linewidth=1.8,
        label="Rail PPI",
    )
    ax2.set_ylabel("Rail PPI (Index)", color=color_ppi, fontsize=12)
    ax2.tick_params(axis="y", labelcolor=color_ppi)

    # ------------------------------------------------------------------
    # 6. Title and subtitle (Pearson r)
    # ------------------------------------------------------------------
    ax1.set_title(
        "Rail Freight Carloads vs. Rail PPI (2015–Present)",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )
    fig.suptitle(
        f"Pearson r = {r_value:.2f}",
        fontsize=11,
        y=0.97,
        color="dimgray",
    )

    # ------------------------------------------------------------------
    # 7. Combined legend from both axes
    # ------------------------------------------------------------------
    lines = [line1, line2]
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="upper left", fontsize=10)

    # ------------------------------------------------------------------
    # 8. Finalize
    # ------------------------------------------------------------------
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
