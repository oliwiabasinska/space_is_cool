"""Offline tests for the parsing and averaging in src/fetch.py (no network)."""

import math

import pytest

from src import fetch


def cell(lat, values):
    return {
        "geometry": {"coordinates": [8.0, lat, 500.0]},
        "properties": {"parameter": {"T2M": values}},
    }


def test_weighted_mean_uses_cos_latitude_and_kelvin():
    features = [cell(0.0, {"202001": 10.0}), cell(60.0, {"202001": 20.0})]
    series = fetch._weighted_mean(features, -999.0)
    w0, w60 = 1.0, math.cos(math.radians(60.0))
    expected = (10.0 * w0 + 20.0 * w60) / (w0 + w60) + 273.15
    assert series.iloc[0] == pytest.approx(expected)
    assert series.name == "t2m_K"


def test_annual_key_and_fill_values_are_dropped():
    features = [cell(46.0, {"202001": 1.0, "202002": -999.0, "202013": 5.0})]
    series = fetch._weighted_mean(features, -999.0)
    assert [d.strftime("%Y-%m") for d in series.index] == ["2020-01"]


def test_start_before_1981_is_rejected():
    with pytest.raises(ValueError):
        fetch.get_series(*fetch.SWITZERLAND, 1976, 2025)


def test_bare_end_year_means_december():
    assert str(fetch._end_period(2025)) == "2025-12"
    assert str(fetch._end_period("2025-06")) == "2025-06"
