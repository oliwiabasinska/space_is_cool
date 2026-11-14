"""Connect data fetching and statistical analysis. No plotting.

analyse_region() does both steps for any lat/lon box and time frame. It is the
one function an interface needs to call.

Running this file (`python -m src.run`) does it for Switzerland and saves:

    data/switzerland_t2m_cells_raw.csv     every grid cell, every month
    data/switzerland_t2m_monthly_max.csv   warmest grid cell of each month
    outputs/anomalies.csv                  the monthly series and its anomalies
    outputs/trend_summary.json             trend of the monthly series
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import analysis, fetch

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"

MIN_TREND_YEARS = 10  # shorter periods are too noisy for a climate trend


def analyse_region(lat_min, lat_max, lon_min, lon_max, start=None, end=None, how="max") -> dict:
    """Fetch a region's monthly temperature and analyse it for a time frame.

    start and end are years (1990) or months ("1990-06"); leave them out for the
    whole record. how="max" uses the warmest grid cell of the box each month,
    how="mean" the area average.

    Returns a dictionary with:
        series      monthly temperature in degrees Celsius, inside the time frame
        anomalies   the same months minus the 1991-2020 average for that month
        trend       the numbers from analysis.trend(), or None if the time frame
                    is shorter than MIN_TREND_YEARS (trend_note then says why)
        plus the box, time frame, aggregation, source and source URL.

    Raises ValueError with a readable message for an invalid box or time frame.
    """
    this_year = pd.Timestamp.now().year
    start = fetch.FIRST_YEAR if start is None else start
    end = this_year if end is None else end
    first = pd.Period(str(start), "M")
    last = pd.Period(f"{end}-12", "M") if len(str(end)) == 4 else pd.Period(str(end), "M")
    if first > last:
        raise ValueError(f"The start ({first}) is after the end ({last}).")
    if first.year < fetch.FIRST_YEAR:
        raise ValueError(f"NASA POWER data starts in {fetch.FIRST_YEAR}, got start={first}.")

    # Always fetch the whole record: the anomaly baseline needs 1991-2020 whatever
    # time frame is shown, and one cached answer then serves every time frame.
    full = fetch.get_series(lat_min, lat_max, lon_min, lon_max, fetch.FIRST_YEAR, this_year, how=how)
    in_frame = (full.index >= first.to_timestamp()) & (full.index <= last.to_timestamp())
    series = full[in_frame]
    if series.empty:
        raise ValueError(f"NASA has no data between {first} and {last} for this region.")
    anomalies = analysis.anomalies(full)[in_frame]

    years = series.index.year.max() - series.index.year.min() + 1
    if years >= MIN_TREND_YEARS:
        trend, note = analysis.trend(series), None
    else:
        trend = None
        note = f"A trend needs at least {MIN_TREND_YEARS} years of data; this time frame has {years}."

    return {
        "box_lat_lon": (lat_min, lat_max, lon_min, lon_max),
        "start": f"{series.index.min():%Y-%m}",
        "end": f"{series.index.max():%Y-%m}",
        "aggregation": how,
        "units": "degC",
        "grid_cells": full.attrs.get("grid_cells"),
        "source": full.attrs.get("source"),
        "source_url": full.attrs.get("url"),
        "anomaly_baseline": analysis.BASELINE,
        "series": series,
        "anomalies": anomalies,
        "trend": trend,
        "trend_note": note,
    }


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    result = analyse_region(*fetch.SWITZERLAND, how="max")
    series, anomalies = result["series"], result["anomalies"]

    cells = fetch.get_cells(*fetch.SWITZERLAND, fetch.FIRST_YEAR, pd.Timestamp.now().year)
    cells.to_csv(DATA_DIR / "switzerland_t2m_cells_raw.csv", index=False)
    series.to_csv(DATA_DIR / "switzerland_t2m_monthly_max.csv")

    summary = {key: value for key, value in result.items()
               if key not in ("series", "anomalies", "trend", "trend_note")}
    summary = {
        "series": "Monthly 2 m air temperature of the warmest grid cell in the Switzerland box",
        **summary,
        **result["trend"],
    }
    pd.concat([series, anomalies], axis=1).to_csv(OUTPUT_DIR / "anomalies.csv")
    (OUTPUT_DIR / "trend_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"data saved to {DATA_DIR}, results saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
