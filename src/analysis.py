"""Trend statistics for monthly temperature series.

Method: seasonal Mann-Kendall test (is there a trend?) with the seasonal Sen's
slope (how big is it?). Both compare each calendar month only with the same
month in other years, so the summer-winter cycle cannot be mistaken for a trend.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy.stats import norm

BASELINE = (1991, 2020)  # the current WMO standard reference period


def year_month_table(series: pd.Series) -> pd.DataFrame:
    """Reshape a monthly series into rows of years and columns of months 1-12."""
    index = pd.DatetimeIndex(series.index)
    table = pd.Series(series.to_numpy(dtype=float), index=[index.year, index.month]).unstack()
    table = table.reindex(columns=range(1, 13))
    table.index.name, table.columns.name = "year", "month"
    return table


def anomalies(series: pd.Series, baseline: tuple[int, int] = BASELINE) -> pd.Series:
    """Each month minus the baseline-period average for that calendar month."""
    index = pd.DatetimeIndex(series.index)
    in_baseline = (index.year >= baseline[0]) & (index.year <= baseline[1])
    if not in_baseline.any():
        raise ValueError(f"no data inside the baseline period {baseline}")
    normal = series[in_baseline].groupby(index.month[in_baseline]).mean()
    result = series - normal.reindex(index.month).to_numpy()
    result.name = "anomaly_C"
    return result


def trend_line(values: pd.Series, slope_per_decade: float) -> pd.Series:
    """A straight line with the given slope, passing through the middle of the data.

    Like Sen's method, the line goes through the median value at the median
    date, so a few extreme months do not pull it up or down.
    """
    index = pd.DatetimeIndex(values.index)
    years = index.year + (index.month - 0.5) / 12
    line = values.median() + slope_per_decade / 10 * (years - np.median(years))
    return pd.Series(np.asarray(line, dtype=float), index=index, name="trend")


def trend(series: pd.Series, alpha: float = 0.05) -> dict:
    """Seasonal Mann-Kendall test and seasonal Sen's slope of a monthly series.

    Returns the slope in units per decade with its confidence interval, and two
    p-values: the standard one, and a stricter one that allows for neighbouring
    months being correlated. "significant" uses the stricter one.
    """
    table = year_month_table(series)
    values = table.to_numpy()
    test = mk.seasonal_test(values, period=12, alpha=alpha)
    strict = mk.correlated_seasonal_test(values, period=12, alpha=alpha)
    slope, low, high = _sens_slope_with_interval(table, float(test.var_s), alpha)

    years = table.index.max() - table.index.min() + 1
    return {
        "method": "seasonal Mann-Kendall test, seasonal Sen's slope",
        "start": f"{pd.DatetimeIndex(series.index).min():%Y-%m}",
        "end": f"{pd.DatetimeIndex(series.index).max():%Y-%m}",
        "n_months": int(np.isfinite(values).sum()),
        "n_years": int(years),
        "slope_per_decade": slope * 10,
        "ci_low_per_decade": low * 10,
        "ci_high_per_decade": high * 10,
        "confidence_level": 1 - alpha,
        "tau": float(test.Tau),
        "p_value": float(test.p),
        "p_value_autocorr": float(strict.p),
        "significant": bool(strict.p < alpha),
        "direction": strict.trend,
    }


def cell_trends(cells: pd.DataFrame, value: str = "t2m_C", alpha: float = 0.05) -> pd.DataFrame:
    """Run trend() separately on every grid cell of a raw cell table."""
    rows = []
    for (lat, lon), cell in cells.groupby(["lat", "lon"]):
        series = cell.set_index(pd.to_datetime(cell["date"]))[value]
        result = trend(series, alpha)
        rows.append({
            "lat": lat,
            "lon": lon,
            "elevation_m": cell["elevation_m"].iloc[0] if "elevation_m" in cell else np.nan,
            **{k: result[k] for k in (
                "slope_per_decade", "ci_low_per_decade", "ci_high_per_decade",
                "p_value", "p_value_autocorr", "significant",
            )},
        })
    return pd.DataFrame(rows)


def _sens_slope_with_interval(table: pd.DataFrame, var_s: float, alpha: float):
    """Seasonal Sen's slope per year, with its confidence interval (Gilbert 1987).

    The slope is the median of the change per year between every pair of years,
    taken month by month. The interval picks the slopes ranked a distance of
    z * sqrt(var_s) / 2 on each side of the median.
    """
    years = table.index.to_numpy(dtype=float)
    first, second = np.triu_indices(len(years), k=1)
    slopes = []
    for month in table.columns:
        column = table[month].to_numpy()
        pair = (column[second] - column[first]) / (years[second] - years[first])
        slopes.append(pair[np.isfinite(pair)])
    slopes = np.sort(np.concatenate(slopes))
    if len(slopes) == 0:
        return np.nan, np.nan, np.nan

    half_width = norm.ppf(1 - alpha / 2) * np.sqrt(var_s)
    low_rank = int(round((len(slopes) - half_width) / 2)) - 1
    high_rank = int(round((len(slopes) + half_width) / 2))
    low = slopes[max(low_rank, 0)]
    high = slopes[min(high_rank, len(slopes) - 1)]
    return float(np.median(slopes)), float(low), float(high)
