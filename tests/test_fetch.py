"""Offline tests for the parsing and aggregation in src/fetch.py (no network)."""

import math

import pytest

from src import fetch


def cell(lat, values, lon=8.0):
    return {
        "geometry": {"coordinates": [lon, lat, 500.0]},
        "properties": {"parameter": {"T2M": values}},
    }


def table(*cells):
    return fetch._to_table(list(cells), -999.0)


def test_raw_table_keeps_every_cell_and_skips_annual_key():
    cells = table(cell(46.0, {"202001": 1.0, "202013": 5.0}), cell(47.0, {"202001": 2.0, "202013": 6.0}))
    assert list(cells.columns) == ["date", "lat", "lon", "elevation_m", "t2m_C"]
    assert cells["t2m_C"].tolist() == [1.0, 2.0]
    assert cells["lat"].tolist() == [46.0, 47.0]


def test_fill_value_becomes_empty_in_raw_table():
    cells = table(cell(46.0, {"202001": 1.0, "202002": -999.0}))
    assert cells["t2m_C"].isna().tolist() == [False, True]


def test_max_is_the_warmest_cell_each_month():
    cells = table(cell(46.0, {"202001": 1.0, "202002": 9.0}), cell(47.0, {"202001": 4.0, "202002": 3.0}))
    assert fetch._aggregate(cells, "max").tolist() == [4.0, 9.0]


def test_mean_is_weighted_by_cos_latitude():
    cells = table(cell(0.0, {"202001": 10.0}), cell(60.0, {"202001": 20.0}))
    w0, w60 = 1.0, math.cos(math.radians(60.0))
    expected = (10.0 * w0 + 20.0 * w60) / (w0 + w60)
    assert fetch._aggregate(cells, "mean").iloc[0] == pytest.approx(expected)


def test_months_with_missing_cells_are_left_out_of_the_series():
    cells = table(cell(46.0, {"202001": 1.0, "202002": -999.0}), cell(47.0, {"202001": 2.0, "202002": 3.0}))
    series = fetch._aggregate(cells, "max")
    assert [d.strftime("%Y-%m") for d in series.index] == ["2020-01"]


def test_unknown_aggregation_is_rejected():
    with pytest.raises(ValueError):
        fetch._aggregate(table(cell(46.0, {"202001": 1.0})), "median")


def test_start_before_1981_is_rejected():
    with pytest.raises(ValueError):
        fetch.get_series(*fetch.SWITZERLAND, 1976, 2025)


def test_bare_end_year_means_december():
    assert str(fetch._end_period(2025)) == "2025-12"
    assert str(fetch._end_period("2025-06")) == "2025-06"


def test_other_parameters_get_their_own_value_column():
    feature = {
        "geometry": {"coordinates": [8.0, 46.0, 500.0]},
        "properties": {"parameter": {"PRECTOTCORR": {"202001": 2.5, "202013": 3.0}}},
    }
    cells = fetch._to_table([feature], -999.0, "PRECTOTCORR", "mm/day")
    assert cells.columns[-1] == "prectotcorr_mm_per_day"
    series = fetch._aggregate(cells, "mean")
    assert series.name == "prectotcorr_mm_per_day" and series.tolist() == [2.5]


def test_default_value_column_is_unchanged():
    assert fetch._column_name("T2M", "C") == "t2m_C"
    assert fetch._column_name("T2M_MAX", "C") == "t2m_max_C"
