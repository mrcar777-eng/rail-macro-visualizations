"""
SEC Event Overlay Chart
=======================
Plots Rail Freight Carloads (RAILFRTCARLOADSD11) for the full available date
range and overlays vertical markers at each 10-K filing date for UNP, CSX,
and NSC, color-coded by ticker.

Run from the project root:
    python visualizations/sec_event_overlay.py
"""

from __future__ import annotations

import sys

import matplotlib.lines as mlines
import matplotlib.pyplot as plt

from visualizations.utils import fetch_edgar_filings, fetch_series

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CARLOADS_ID = "RAILFRTCARLOADSD11"
TICKERS = ["UNP", "CSX", "NSC"]

# Color mapping for each ticker
TICKER_COLORS: dict[str, str] = {
    "UNP": "green",
    "CSX": "orange",
    "NSC": "purple",
}

# Vertical line style shared across all tickers
VLINE_KWARGS = dict(alpha=0.6, linewidth=1.0, linestyle="--")


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Fetch carloads — full date range (no start/end filter)
    # ------------------------------------------------------------------
    try:
        data = fetch_series([CARLOADS_ID])
    except RuntimeError as exc:
        print(f"ERROR: Database connection failed — {exc}")
        sys.exit(1)

    carloads_df = data[CARLOADS_ID]

    if carloads_df.empty:
        print(
            f"WARNING: Series {CARLOADS_ID} returned no data. "
            "Cannot render chart. Exiting."
        )
        sys.exit(0)

    # ------------------------------------------------------------------
    # 2. Fetch 10-K filings for UNP, CSX, NSC
    # ------------------------------------------------------------------
    try:
        filings_df = fetch_edgar_filings(TICKERS, form_type="10-K")
    except RuntimeError as exc:
        print(f"ERROR: Database connection failed — {exc}")
        sys.exit(1)

    # Determine whether we have any usable filing rows
    has_filings = not filings_df.empty

    if not has_filings:
        print(
            f"WARNING: No 10-K filings found for {TICKERS}. "
            "Rendering carloads only."
        )

    # ------------------------------------------------------------------
    # 3. Build figure
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 6))

    # Plot carloads line
    (carloads_line,) = ax.plot(
        carloads_df["observation_date"],
        carloads_df["value"],
        color="steelblue",
        linewidth=1.5,
        label="Rail Freight Carloads",
    )

    # ------------------------------------------------------------------
    # 4. Overlay axvline markers per ticker (only when filings exist)
    # ------------------------------------------------------------------
    if has_filings:
        for ticker in TICKERS:
            color = TICKER_COLORS[ticker]
            ticker_rows = filings_df[filings_df["ticker"] == ticker]
            for filing_date in ticker_rows["filing_date"]:
                ax.axvline(
                    x=filing_date,
                    color=color,
                    **VLINE_KWARGS,
                )

    # ------------------------------------------------------------------
    # 5. Build legend
    # ------------------------------------------------------------------
    legend_handles = [carloads_line]

    if has_filings:
        for ticker in TICKERS:
            # Only add a legend entry if this ticker actually has filings
            if not filings_df[filings_df["ticker"] == ticker].empty:
                handle = mlines.Line2D(
                    [],
                    [],
                    color=TICKER_COLORS[ticker],
                    linewidth=1.0,
                    linestyle="--",
                    alpha=0.8,
                    label=f"{ticker} 10-K Filing",
                )
                legend_handles.append(handle)

    ax.legend(handles=legend_handles, loc="upper left", fontsize=9)

    # ------------------------------------------------------------------
    # 6. Labels and title
    # ------------------------------------------------------------------
    ax.set_title(
        "Rail Freight Carloads with SEC 10-K Filing Events (UNP, CSX, NSC)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Rail Freight Carloads", fontsize=12)

    # ------------------------------------------------------------------
    # 7. Finalize
    # ------------------------------------------------------------------
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
