"""Tests for src/analysis.py on synthetic series with a known answer."""

import numpy as np
import pandas as pd
import pymannkendall as mk
import pytest

from src import analysis


def synthetic(slope_per_year=0.03, years=40, noise=0.5, months=None, seed=0):
    """A seasonal cycle plus a straight-line trend plus random noise."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1981-01-01", periods=months or years * 12, freq="MS")
    t = np.arange(len(dates)) / 12
    seasonal = 10 * np.sin(2 * np.pi * (dates.month - 4) / 12)
    return pd.Series(8 + seasonal + slope_per_year * t + rng.normal(0, noise, len(dates)), index=dates)


def test_known_slope_is_recovered_despite_the_seasonal_cycle():
    result = analysis.trend(synthetic(slope_per_year=0.03))
    assert result["slope_per_decade"] == pytest.approx(0.3, abs=0.05)
    assert result["ci_low_per_decade"] < 0.3 < result["ci_high_per_decade"]
    assert result["significant"] and result["direction"] == "increasing"


def test_no_trend_is_not_significant():
    result = analysis.trend(synthetic(slope_per_year=0.0))
    assert not result["significant"]
    assert result["ci_low_per_decade"] < 0 < result["ci_high_per_decade"]


def test_slope_matches_the_library():
    series = synthetic(seed=3)
    ours = analysis.trend(series)["slope_per_decade"] / 10
    theirs = mk.seasonal_test(analysis.year_month_table(series).to_numpy(), period=12).slope
    assert ours == pytest.approx(theirs)


def test_incomplete_last_year_is_handled():
    result = analysis.trend(synthetic(months=40 * 12 + 9))
    assert result["n_months"] == 489
    assert result["end"] == "2021-09"
    assert result["slope_per_decade"] == pytest.approx(0.3, abs=0.05)


def test_anomalies_remove_the_seasonal_cycle():
    series = synthetic(slope_per_year=0.0, noise=0.0)
    assert analysis.anomalies(series).abs().max() == pytest.approx(0.0, abs=1e-9)


def test_anomalies_average_zero_over_the_baseline():
    anomaly = analysis.anomalies(synthetic(), baseline=(1991, 2020))
    assert anomaly["1991":"2020"].mean() == pytest.approx(0.0, abs=1e-9)


def test_cell_trends_gives_one_row_per_cell():
    frames = []
    for lat, slope in ((46.0, 0.02), (47.0, 0.05)):
        series = synthetic(slope_per_year=slope, seed=int(lat))
        frames.append(pd.DataFrame({
            "date": series.index, "lat": lat, "lon": 8.0, "elevation_m": 500.0, "t2m_C": series.to_numpy(),
        }))
    result = analysis.cell_trends(pd.concat(frames))
    assert len(result) == 2
    slopes = result.set_index("lat")["slope_per_decade"]
    assert slopes[46.0] == pytest.approx(0.2, abs=0.05)
    assert slopes[47.0] == pytest.approx(0.5, abs=0.05)
