"""Run the trend analysis for Switzerland and save the results.

Reads the two CSV files written by `python -m src.fetch` (and downloads them
first if they are missing), then writes to the outputs/ folder:

    trend_summary.json     trend of the monthly maximum series
    cell_trends.csv        trend of each grid cell
    trend.html             anomalies with the Sen's slope line
    anomaly_heatmap.html   year by month grid of anomalies
    cell_trend_map.html    map of the trend per grid cell

Run with `python -m src.analysis`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import fetch, plots, trends

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
MAX_FILE = DATA_DIR / "switzerland_t2m_monthly_max.csv"
RAW_FILE = DATA_DIR / "switzerland_t2m_cells_raw.csv"


def load_data() -> tuple[pd.Series, pd.DataFrame]:
    """The monthly maximum series and the raw cell table, downloading if needed."""
    if not (MAX_FILE.exists() and RAW_FILE.exists()):
        this_year = pd.Timestamp.now().year
        DATA_DIR.mkdir(exist_ok=True)
        fetch.get_cells(*fetch.SWITZERLAND, fetch.FIRST_YEAR, this_year).to_csv(RAW_FILE, index=False)
        fetch.get_series(*fetch.SWITZERLAND, fetch.FIRST_YEAR, this_year, how="max").to_csv(MAX_FILE)
    maximum = pd.read_csv(MAX_FILE, index_col="date", parse_dates=True)["t2m_C"]
    cells = pd.read_csv(RAW_FILE, parse_dates=["date"])
    return maximum, cells


def main() -> None:
    maximum, cells = load_data()
    OUTPUT_DIR.mkdir(exist_ok=True)

    summary = trends.trend(maximum)
    summary = {
        "series": "Monthly 2 m air temperature of the warmest grid cell in the Switzerland box",
        "box_lat_lon": fetch.SWITZERLAND,
        "units": "degC",
        "source": "NASA POWER Monthly API (MERRA-2 reanalysis)",
        **summary,
    }
    (OUTPUT_DIR / "trend_summary.json").write_text(json.dumps(summary, indent=2))

    per_cell = trends.cell_trends(cells)
    per_cell.to_csv(OUTPUT_DIR / "cell_trends.csv", index=False)

    figures = {
        "trend.html": plots.trend_figure(
            maximum, summary, "Warmest grid cell of the Switzerland box, monthly"),
        "anomaly_heatmap.html": plots.anomaly_heatmap(
            maximum, "Warmest grid cell of the Switzerland box: every month since 1981"),
        "cell_trend_map.html": plots.cell_trend_map(
            per_cell, f"Where it is warming fastest, {summary['start'][:4]}–{summary['end'][:4]}"),
    }
    for name, figure in figures.items():
        figure.write_html(OUTPUT_DIR / name, include_plotlyjs="cdn")

    print(json.dumps(summary, indent=2))
    print(per_cell.round(3).to_string(index=False))
    print(f"saved {len(figures) + 2} files to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
