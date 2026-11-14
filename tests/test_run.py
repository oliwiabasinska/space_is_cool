"""Tests for analyse_region in src/run.py, with the NASA call replaced by fake data."""

import numpy as np
import pandas as pd
import pytest

from src import fetch, run

BOX = (40.0, 44.0, 0.0, 4.0)


def fake_series(slope_per_year=0.05):
    """Monthly data from 1981 to the current year: seasonal cycle, trend and noise."""
    rng = np.random.default_rng(1)
    dates = pd.date_range("1981-01-01", f"{pd.Timestamp.now().year}-12-01", freq="MS")
    t = np.arange(len(dates)) / 12
    seasonal = 10 * np.sin(2 * np.pi * (dates.month - 4) / 12)
    series = pd.Series(8 + seasonal + slope_per_year * t + rng.normal(0, 0.5, len(dates)),
                       index=dates, name="t2m_C")
    series.attrs = {"source": "fake", "url": "http://example.invalid", "grid_cells": 4}
    return series


@pytest.fixture
def fake_nasa(monkeypatch):
    calls = []

    def get_series(lat_min, lat_max, lon_min, lon_max, start, end, how="max", refresh=False):
        fetch.check_box(lat_min, lat_max, lon_min, lon_max)
        calls.append((start, end, how))
        return fake_series()

    monkeypatch.setattr(fetch, "get_series", get_series)
    return calls


def test_whole_record_by_default(fake_nasa):
    result = run.analyse_region(*BOX)
    assert result["start"] == "1981-01"
    assert result["aggregation"] == "max"
    assert result["trend"]["slope_per_decade"] == pytest.approx(0.5, abs=0.06)
    assert result["trend"]["significant"]
    assert len(result["series"]) == len(result["anomalies"])


def test_time_frame_limits_the_series_and_the_trend(fake_nasa):
    result = run.analyse_region(*BOX, start=2000, end="2015-06")
    assert result["start"] == "2000-01" and result["end"] == "2015-06"
    assert result["series"].index.min() == pd.Timestamp("2000-01-01")
    assert result["series"].index.max() == pd.Timestamp("2015-06-01")
    assert result["trend"]["start"] == "2000-01" and result["trend"]["end"] == "2015-06"


def test_anomalies_do_not_depend_on_the_time_frame(fake_nasa):
    whole = run.analyse_region(*BOX)["anomalies"]
    part = run.analyse_region(*BOX, start=2021, end=2023)["anomalies"]
    pd.testing.assert_series_equal(part, whole["2021":"2023"])


def test_whole_record_is_fetched_whatever_the_time_frame(fake_nasa):
    run.analyse_region(*BOX, start=2005, end=2020)
    assert fake_nasa[0][0] == fetch.FIRST_YEAR


def test_short_time_frame_gives_no_trend_but_still_gives_data(fake_nasa):
    result = run.analyse_region(*BOX, start=2018, end=2022)
    assert result["trend"] is None
    assert "at least" in result["trend_note"]
    assert len(result["series"]) == 60


@pytest.mark.parametrize("box, word", [
    ((40, 52, 0, 4), "too large"),
    ((40, 44, 0, 14), "too large"),
    ((44, 40, 0, 4), "minimum below"),
    ((40, 44, 4, 4), "minimum below"),
    ((95, 99, 0, 4), "Latitude"),
    ((40, 44, 175, 190), "Longitude"),
])
def test_invalid_boxes_are_explained(fake_nasa, box, word):
    with pytest.raises(ValueError, match=word):
        run.analyse_region(*box)


def test_invalid_time_frames_are_explained(fake_nasa):
    with pytest.raises(ValueError, match="after the end"):
        run.analyse_region(*BOX, start=2020, end=2010)
    with pytest.raises(ValueError, match="starts in 1981"):
        run.analyse_region(*BOX, start=1970, end=2010)


def test_largest_allowed_box_passes_the_check():
    fetch.check_box(40, 50, 0, 10)
