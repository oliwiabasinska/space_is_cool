"""Monthly 2 m air temperature time series from the NASA POWER API.

Source: NASA POWER "Monthly and Annual" time-series API (no login needed)
        https://power.larc.nasa.gov/docs/services/api/temporal/monthly/
Data:   T2M, temperature at 2 metres, from the MERRA-2 reanalysis
        (model plus assimilated observations, not a direct satellite measurement).
Grid:   0.5 deg latitude x 0.625 deg longitude. Available from January 1981.

Run `python -m src.fetch` to download the Switzerland series to a CSV file.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import requests

API_ROOT = "https://power.larc.nasa.gov/api/temporal/monthly"
PARAMETER = "T2M"
FIRST_YEAR = 1981  # the API rejects earlier start years
MIN_BOX_DEG = 2.0  # the regional endpoint rejects boxes smaller than this
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

# Bounding box around Switzerland: lat_min, lat_max, lon_min, lon_max
SWITZERLAND = (45.8, 47.8, 5.9, 10.5)


def get_series(lat_min, lat_max, lon_min, lon_max, start, end, refresh=False) -> pd.Series:
    """Area-weighted mean monthly 2 m temperature of a lat/lon box, in Kelvin.

    start and end are years (1981) or dates ("1981-06"). Months that NASA has
    not published yet are left out. Boxes smaller than 2 degrees on a side
    return the grid cell at the centre of the box instead of an average.
    """
    start, end = pd.Period(str(start), "M"), _end_period(end)
    if start.year < FIRST_YEAR:
        raise ValueError(f"NASA POWER data starts in {FIRST_YEAR}, got start={start}")

    years = {"start": start.year, "end": end.year}
    if lat_max - lat_min < MIN_BOX_DEG or lon_max - lon_min < MIN_BOX_DEG:
        payload = _request("point", {
            "latitude": (lat_min + lat_max) / 2,
            "longitude": (lon_min + lon_max) / 2,
            **years,
        }, refresh)
        features = [payload]
    else:
        payload = _request("regional", {
            "latitude-min": lat_min, "latitude-max": lat_max,
            "longitude-min": lon_min, "longitude-max": lon_max,
            **years,
        }, refresh)
        features = payload["features"]

    series = _weighted_mean(features, payload["header"]["fill_value"])
    series = series[(series.index >= start.to_timestamp()) & (series.index <= end.to_timestamp())]
    series.attrs = {
        "source": "NASA POWER Monthly API, " + ", ".join(payload["header"]["sources"]),
        "variable": "Temperature at 2 Meters (T2M)",
        "units": "K",
        "kind": "reanalysis",
        "box": (lat_min, lat_max, lon_min, lon_max),
        "grid_cells": len(features),
    }
    return series


def _end_period(end) -> pd.Period:
    """A bare year means the whole year, so 2025 ends in December 2025."""
    text = str(end)
    return pd.Period(f"{text}-12", "M") if len(text) == 4 else pd.Period(text, "M")


def _request(kind: str, params: dict, refresh: bool) -> dict:
    """Call the API, keeping a copy of each answer on disk."""
    params = {"parameters": PARAMETER, "community": "RE", "format": "JSON", **params}
    key = hashlib.sha1(json.dumps([kind, params], sort_keys=True).encode()).hexdigest()[:16]
    cache_file = CACHE_DIR / f"power_{kind}_{key}.json"
    if cache_file.exists() and not refresh:
        return json.loads(cache_file.read_text())

    response = requests.get(f"{API_ROOT}/{kind}", params=params, timeout=120)
    payload = response.json()
    if not response.ok:
        raise RuntimeError(f"NASA POWER error: {payload.get('messages') or payload}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload))
    return payload


def _weighted_mean(features: list[dict], fill_value: float) -> pd.Series:
    """Average the grid cells, weighting each by cos(latitude), and convert C to K."""
    columns, weights = [], []
    for feature in features:
        values = feature["properties"]["parameter"][PARAMETER]
        # Keys are YYYYMM. Month "13" is the API's annual mean, which we skip.
        monthly = {pd.Timestamp(f"{k[:4]}-{k[4:]}-01"): v for k, v in values.items() if k[4:] != "13"}
        columns.append(pd.Series(monthly, dtype=float))
        weights.append(math.cos(math.radians(feature["geometry"]["coordinates"][1])))

    cells = pd.concat(columns, axis=1).sort_index().replace(fill_value, float("nan"))
    cells = cells.dropna(how="any")  # keep only months where every cell has data
    weights = pd.Series(weights, index=cells.columns)
    series = (cells * weights).sum(axis=1) / weights.sum() + 273.15
    series.index.name = "date"
    series.name = "t2m_K"
    return series


if __name__ == "__main__":
    out = CACHE_DIR.parent / "switzerland_t2m_monthly.csv"
    switzerland = get_series(*SWITZERLAND, FIRST_YEAR, pd.Timestamp.now().year)
    switzerland.to_csv(out)
    print(switzerland.attrs)
    print(f"{len(switzerland)} months, {switzerland.index[0]:%Y-%m} to {switzerland.index[-1]:%Y-%m}")
    print(f"saved to {out}")
