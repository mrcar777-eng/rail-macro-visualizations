"""
Lead-Lag Correlation Heatmap
=============================
Shows the Pearson correlation between Rail Freight Carloads at time ``t``
and each target series (Rail PPI, Employment) at ``t + lag`` for lags of
1, 2, 3, 6, 9, and 12 months.

Interpretation: a positive correlation at lag=3 means that when carloads
are high today, the target series tends to be high 3 months from now.

Run from the project root:
    python visualizations/lead_lag_heatmap.py
"""

from __future__ import annotations

import sys

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr

from visualizations.utils import fetch_series

# ---------------------------------------------------------------------------
# Series identifiers
# ---------------------------------------------------------------------------

CARLOADS_ID = "RAILFRTCARLOADSD11"
PPI_ID = "PCU4821114821114"
EMPLOYMENT_ID = "CES4348200001"

# Minimum number of overlapping observations required to compute a valid
# Pearson correlation.  Cells below this threshold are set to NaN.
MIN_OBSERVATIONS = 12

# Lag values (in months) to evaluate
LAGS: list[int] = [1, 2, 3, 6, 9, 12]


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_lead_lag_correlation(
    base: pd.Series,
    targets: dict[str, pd.Series],
    lags: list[int],
) -> pd.DataFrame:
    """
    Compute Pearson correlation between ``base[t]`` and each target series
    at ``t + lag`` for every requested lag.

    Parameters
    ----------
    base : pd.Series
        Carloads series with a DatetimeIndex.
    targets : dict[str, pd.Series]
        Mapping of label -> series with a DatetimeIndex.
    lags : list[int]
        Positive integer month offsets.  For lag=3 we ask: "does carloads
        today predict the target 3 months from now?"

    Returns
    -------
    pd.DataFrame
        Shape ``(len(targets), len(lags))``.
        Index = target labels, columns = lag values.
        Cells with fewer than ``MIN_OBSERVATIONS`` overlapping points are NaN.
    """
    records: dict[str, list[float | None]] = {label: [] for label in targets}

    for label, target in targets.items():
        for lag in lags:
            # Shift the target index BACKWARD by lag months so that the
            # shifted value at date d represents the original value at d+lag.
            # After alignment with base (which is at time t), we are
            # correlating base[t] with target[t+lag].
            shifted_target = target.copy()
            shifted_target.index = target.index - pd.DateOffset(months=lag)

            # Align on common dates (inner join)
            aligned = pd.concat(
                [base.rename("base"), shifted_target.rename("target")],
                axis=1,
                join="inner",
            ).dropna()

            n = len(aligned)

            if n < MIN_OBSERVATIONS:
                print(
                    f"WARNING: Insufficient overlap for {label} at lag "
                    f"{lag} months ({n} points). Setting to NaN."
                )
                records[label].append(float("nan"))
            else:
                r_value, _ = pearsonr(aligned["base"], aligned["target"])
                records[label].append(r_value)

    corr_df = pd.DataFrame(records, index=lags).T
    corr_df.columns = lags
    return corr_df


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # ------------------------------------------------------------------
    # Task 7.1 — Fetch all three series (no date filter)
    # ------------------------------------------------------------------
    try:
        data = fetch_series([CARLOADS_ID, PPI_ID, EMPLOYMENT_ID])
    except RuntimeError as exc:
        print(f"ERROR: Database connection failed — {exc}", file=sys.stderr)
        sys.exit(1)

    carloads_df = data[CARLOADS_ID]
    ppi_df = data[PPI_ID]
    employment_df = data[EMPLOYMENT_ID]

    # ------------------------------------------------------------------
    # Guard against empty series (Requirement 7.2)
    # ------------------------------------------------------------------
    missing: list[str] = []
    if carloads_df.empty:
        missing.append(CARLOADS_ID)
    if ppi_df.empty:
        missing.append(PPI_ID)
    if employment_df.empty:
        missing.append(EMPLOYMENT_ID)

    if missing:
        print(
            f"WARNING: The following series returned no data and cannot be "
            f"used: {', '.join(missing)}. Exiting."
        )
        sys.exit(0)

    # ------------------------------------------------------------------
    # Convert to DatetimeIndex Series
    # ------------------------------------------------------------------
    carloads = carloads_df.set_index("observation_date")["value"]
    ppi_series = ppi_df.set_index("observation_date")["value"]
    employment_series = employment_df.set_index("observation_date")["value"]

    # ------------------------------------------------------------------
    # Task 7.2 / 7.3 — Build correlation matrix
    # ------------------------------------------------------------------
    targets = {
        "Rail PPI": ppi_series,
        "Employment": employment_series,
    }

    corr_matrix = compute_lead_lag_correlation(
        base=carloads,
        targets=targets,
        lags=LAGS,
    )

    # ------------------------------------------------------------------
    # Task 7.4 / 7.5 — Render heatmap
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 4))

    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        vmin=-1,
        vmax=1,
        linewidths=0.5,
        ax=ax,
    )

    ax.set_xlabel("Lag (months)", fontsize=12)
    ax.set_ylabel("Target Series", fontsize=12)
    ax.set_title(
        "Lead-Lag Correlation: Rail Carloads (t) vs. Target Series (t + lag)",
        fontsize=13,
        fontweight="bold",
    )

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
