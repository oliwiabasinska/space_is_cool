"""Fetch the Switzerland data and run the statistical analysis. No plotting.

Writes to data/ (what NASA gave us):
    switzerland_t2m_cells_raw.csv     every grid cell, every month
    switzerland_t2m_monthly_max.csv   warmest grid cell of each month

Writes to outputs/ (what we computed):
    anomalies.csv         the monthly maximum series and its anomalies
    trend_summary.json    trend of the monthly maximum series
    cell_trends.csv       trend of each grid cell

Run with `python -m src.run`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import analysis, fetch

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    this_year = pd.Timestamp.now().year

    # Fetch (answers are cached on disk, so repeat runs do not call NASA again)
    cells = fetch.get_cells(*fetch.SWITZERLAND, fetch.FIRST_YEAR, this_year)
    maximum = fetch.get_series(*fetch.SWITZERLAND, fetch.FIRST_YEAR, this_year, how="max")
    cells.to_csv(DATA_DIR / "switzerland_t2m_cells_raw.csv", index=False)
    maximum.to_csv(DATA_DIR / "switzerland_t2m_monthly_max.csv")

    # Analyse
    anomaly = analysis.anomalies(maximum)
    summary = {
        "series": "Monthly 2 m air temperature of the warmest grid cell in the Switzerland box",
        "box_lat_lon": fetch.SWITZERLAND,
        "units": "degC",
        "source": maximum.attrs["source"],
        "source_url": maximum.attrs["url"],
        "anomaly_baseline": analysis.BASELINE,
        **analysis.trend(maximum),
    }
    per_cell = analysis.cell_trends(cells)

    pd.concat([maximum, anomaly], axis=1).to_csv(OUTPUT_DIR / "anomalies.csv")
    (OUTPUT_DIR / "trend_summary.json").write_text(json.dumps(summary, indent=2))
    per_cell.to_csv(OUTPUT_DIR / "cell_trends.csv", index=False)

    print(json.dumps(summary, indent=2))
    print(per_cell.round(3).to_string(index=False))
    print(f"data saved to {DATA_DIR}, results saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
