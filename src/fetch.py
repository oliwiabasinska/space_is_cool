"""Monthly 2 m air temperature time series from the NASA POWER API.

Source: NASA POWER "Monthly and Annual" time-series API (no login needed)
        https://power.larc.nasa.gov/docs/services/api/temporal/monthly/
Data:   T2M, temperature at 2 metres, from the MERRA-2 reanalysis
        (model plus assimilated observations, not a direct satellite measurement).
Grid:   0.5 deg latitude x 0.625 deg longitude. Available from January 1981.

Run `python -m src.fetch` to save two CSV files for Switzerland: the raw grid
cells and the monthly maximum across them.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests

API_ROOT = "https://power.larc.nasa.gov/api/temporal/monthly"
PARAMETER = "T2M"
FIRST_YEAR = 1981  # the API rejects earlier start years
MIN_BOX_DEG = 2.0  # the regional endpoint rejects boxes smaller than this
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

# Bounding box around Switzerland: lat_min, lat_max, lon_min, lon_max
SWITZERLAND = (45.8, 47.8, 5.9, 10.5)


def get_cells(lat_min, lat_max, lon_min, lon_max, start, end, refresh=False) -> pd.DataFrame:
    """Raw NASA values, one row per grid cell per month, nothing averaged.

    Columns: date, lat, lon, elevation_m, t2m_C. Values are exactly as NASA
    serves them, except that months not published yet are empty instead of
    -999. start and end are years (1981) or dates ("1981-06"). Boxes smaller
    than 2 degrees on a side return the single grid cell at the box centre.
    """
    start, end = pd.Period(str(start), "M"), _end_period(end)
    if start.year < FIRST_YEAR:
        raise ValueError(f"NASA POWER data starts in {FIRST_YEAR}, got start={start}")

    years = {"start": start.year, "end": end.year}
    if lat_max - lat_min < MIN_BOX_DEG or lon_max - lon_min < MIN_BOX_DEG:
        payload, url = _request("point", {
            "latitude": (lat_min + lat_max) / 2,
            "longitude": (lon_min + lon_max) / 2,
            **years,
        }, refresh)
        features = [payload]
    else:
        payload, url = _request("regional", {
            "latitude-min": lat_min, "latitude-max": lat_max,
            "longitude-min": lon_min, "longitude-max": lon_max,
            **years,
        }, refresh)
        features = payload["features"]

    cells = _to_table(features, payload["header"]["fill_value"])
    cells = cells[(cells.date >= start.to_timestamp()) & (cells.date <= end.to_timestamp())]
    cells = cells.reset_index(drop=True)
    cells.attrs = {
        "source": "NASA POWER Monthly API, " + ", ".join(payload["header"]["sources"]),
        "variable": "Temperature at 2 Meters (T2M)",
        "units": "degC",
        "kind": "reanalysis",
        "box": (lat_min, lat_max, lon_min, lon_max),
        "grid_cells": len(features),
        "url": url,
    }
    return cells


def get_series(lat_min, lat_max, lon_min, lon_max, start, end, how="max", refresh=False) -> pd.Series:
    """One monthly 2 m temperature value for a lat/lon box, in degrees Celsius.

    how="max" gives the warmest grid cell of the box in each month.
    how="mean" gives the average of the cells, weighted by cos(latitude).
    Months that NASA has not published yet are left out.
    """
    cells = get_cells(lat_min, lat_max, lon_min, lon_max, start, end, refresh)
    series = _aggregate(cells, how)
    series.attrs = {**cells.attrs, "aggregation": how}
    return series


def _end_period(end) -> pd.Period:
    """A bare year means the whole year, so 2025 ends in December 2025."""
    text = str(end)
    return pd.Period(f"{text}-12", "M") if len(text) == 4 else pd.Period(text, "M")


def _request(kind: str, params: dict, refresh: bool) -> tuple[dict, str]:
    """Call the API, keeping a copy of each answer on disk. Returns (answer, url)."""
    params = {"parameters": PARAMETER, "community": "RE", "format": "JSON", **params}
    key = hashlib.sha1(json.dumps([kind, params], sort_keys=True).encode()).hexdigest()[:16]
    cache_file = CACHE_DIR / f"power_{kind}_{key}.json"
    url = f"{API_ROOT}/{kind}?{urlencode(params)}"
    if cache_file.exists() and not refresh:
        return json.loads(cache_file.read_text()), url

    response = requests.get(url, timeout=120)
    payload = response.json()
    if not response.ok:
        raise RuntimeError(f"NASA POWER error: {payload.get('messages') or payload}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload))
    return payload, url


def _to_table(features: list[dict], fill_value: float) -> pd.DataFrame:
    """Turn the API answer into rows of date, lat, lon, elevation_m, t2m_C."""
    rows = []
    for feature in features:
        lon, lat, elevation = feature["geometry"]["coordinates"]
        for key, value in feature["properties"]["parameter"][PARAMETER].items():
            if key[4:] == "13":  # keys are YYYYMM; "13" is the API's annual mean
                continue
            rows.append((pd.Timestamp(f"{key[:4]}-{key[4:]}-01"), lat, lon, elevation, value))
    table = pd.DataFrame(rows, columns=["date", "lat", "lon", "elevation_m", "t2m_C"])
    table["t2m_C"] = table["t2m_C"].astype(float).replace(fill_value, float("nan"))
    return table.sort_values(["date", "lat", "lon"], ignore_index=True)


def _aggregate(cells: pd.DataFrame, how: str) -> pd.Series:
    """Reduce the grid cells to one value per month."""
    # Keep only months where every cell has data.
    complete = cells.groupby("date")["t2m_C"].transform(lambda v: v.notna().all())
    cells = cells[complete]
    if how == "max":
        series = cells.groupby("date")["t2m_C"].max()
    elif how == "mean":
        weights = cells["lat"].map(lambda lat: math.cos(math.radians(lat)))
        weighted = (cells["t2m_C"] * weights).groupby(cells["date"]).sum()
        series = weighted / weights.groupby(cells["date"]).sum()
    else:
        raise ValueError(f"how must be 'max' or 'mean', got {how!r}")
    series.name = "t2m_C"
    return series


if __name__ == "__main__":
    data_dir = CACHE_DIR.parent
    this_year = pd.Timestamp.now().year
    raw_file = data_dir / "switzerland_t2m_cells_raw.csv"
    max_file = data_dir / "switzerland_t2m_monthly_max.csv"

    raw = get_cells(*SWITZERLAND, FIRST_YEAR, this_year)
    raw.to_csv(raw_file, index=False)

    maximum = get_series(*SWITZERLAND, FIRST_YEAR, this_year, how="max")
    maximum.to_csv(max_file)

    print(maximum.attrs)
    print(f"raw: {len(raw)} rows from {raw.attrs['grid_cells']} cells, saved to {raw_file}")
    print(f"max: {len(maximum)} months, {maximum.index[0]:%Y-%m} to {maximum.index[-1]:%Y-%m}, saved to {max_file}")
