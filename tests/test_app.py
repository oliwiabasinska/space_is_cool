"""Tests for the Streamlit page in app/app.py, without a browser.

The map component cannot be clicked from a test, so the drawing test replaces
it with a fake that reports one drawn rectangle.
"""

from pathlib import Path

import pytest

streamlit_folium = pytest.importorskip("streamlit_folium")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "app.py")
FIELDS = ("lat_min", "lat_max", "lon_min", "lon_max")


def start():
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    return app


def type_box(app, box):
    for field, value in zip(FIELDS, box):
        app.number_input(key=field).set_value(value)
    app.run()
    assert not app.exception
    return app


def test_starts_with_no_region():
    app = start()
    assert [message.value for message in app.info] == ["No region selected yet."]
    assert not app.success and not app.error


def test_typed_coordinates_select_a_region():
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    assert "latitude 45.8 to 47.8, longitude 5.9 to 10.5" in app.success[0].value
    assert not app.error


def test_too_large_region_is_explained():
    app = type_box(start(), (30.0, 60.0, 0.0, 10.0))
    assert "too large" in app.error[0].value
    assert not app.success


def test_small_region_mentions_the_single_grid_cell():
    app = type_box(start(), (40.0, 41.0, -4.0, -3.0))
    assert app.success
    assert "single NASA grid cell" in app.caption[0].value


def test_clear_button_empties_the_selection():
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    app.button[0].click().run()
    assert [message.value for message in app.info] == ["No region selected yet."]


def test_drawn_rectangle_fills_the_fields(monkeypatch):
    ring = [[5.9, 45.8], [5.9, 47.8], [10.5, 47.8], [10.5, 45.8], [5.9, 45.8]]
    drawing = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}}

    def fake_map(figure, key=None, **options):
        # Only the first map reports a drawing; the redrawn one starts clean.
        return {"last_active_drawing": drawing if key == "map_0" else None}

    monkeypatch.setattr(streamlit_folium, "st_folium", fake_map)
    app = start()
    assert [app.number_input(key=field).value for field in FIELDS] == [45.8, 47.8, 5.9, 10.5]
    assert "latitude 45.8 to 47.8" in app.success[0].value


def test_map_script_draws_on_double_click_and_makes_the_region_resizable():
    import folium

    from src.map_selector import RegionSelector

    def script(corners):
        world = folium.Map()
        RegionSelector(corners).add_to(world)
        return streamlit_folium._get_map_string(world).replace(
            streamlit_folium.get_full_id(world), "map_div")

    empty = script(None)
    assert 'map.on("dblclick"' in empty and "doubleClickZoom.disable()" in empty
    assert "editing.enable()" not in empty
    selected = script([[45.8, 5.9], [47.8, 10.5]])
    assert "L.rectangle([[45.8, 5.9], [47.8, 10.5]]" in selected
    assert "editing.enable()" in selected and 'map.fire("draw:created"' in selected


def test_dark_basemap_draws_outlines_and_names_from_the_files_the_app_serves():
    import json

    import folium

    from src.map_selector import OUTLINES, DarkBasemap

    world = folium.Map(tiles=None)
    DarkBasemap().add_to(world)
    script = streamlit_folium._get_map_string(world)
    assert "tileLayer" not in script  # no outside map tiles: the basemap is all our own files
    for name in ("land", "borders", "labels"):
        assert f'pane("{name}"' in script
        local = OUTLINES[name][0]
        assert local in script and local.startswith("/app/static/")
        data = json.loads((Path(APP).parent / "static" / local.rsplit("/", 1)[1]).read_text(encoding="utf-8"))
        assert data["features"] if name != "labels" else data["countries"] and data["cities"]
    config = (Path(APP).parent.parent / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "enableStaticServing = true" in config


# --- Automatic analysis --------------------------------------------------------

def fake_analysis(calls):
    """A stand-in for run.analyse_region that uses synthetic data, not NASA."""
    import numpy as np
    import pandas as pd

    from src import analysis

    def analyse_region(lat_min, lat_max, lon_min, lon_max, start=None, end=None, how=None,
                       variable="t2m"):
        from src import variables
        chosen = variables.get(variable)
        how = how or chosen.how
        calls.append((lat_min, lat_max, lon_min, lon_max, start, end, variable))
        if start > end:
            raise ValueError(f"The start ({start}) is after the end ({end}).")
        rng = np.random.default_rng(0)
        dates = pd.date_range("1981-01-01", "2025-12-01", freq="MS")
        t = np.arange(len(dates)) / 12
        full = pd.Series(8 + 10 * np.sin(2 * np.pi * (dates.month - 4) / 12) + 0.05 * t
                         + rng.normal(0, 0.5, len(dates)), index=dates, name="t2m_C")
        series = full[str(start):str(end)]
        years = series.index.year.max() - series.index.year.min() + 1
        return {
            "box_lat_lon": (lat_min, lat_max, lon_min, lon_max),
            "start": f"{series.index.min():%Y-%m}", "end": f"{series.index.max():%Y-%m}",
            "variable": variable, "variable_label": chosen.label, "parameter": chosen.parameter,
            "aggregation": how, "units": "degC", "unit_label": chosen.unit, "grid_cells": 28,
            "source": "fake source", "source_url": "http://example.invalid",
            "anomaly_baseline": analysis.BASELINE,
            "series": series, "anomalies": analysis.anomalies(full)[str(start):str(end)],
            "trend": analysis.trend(series) if years >= 10 else None,
            "trend_note": None if years >= 10 else f"A trend needs at least 10 years of data; this time frame has {years}.",
        }

    return analyse_region


@pytest.fixture
def analysed(monkeypatch):
    import streamlit as st

    from src import run

    calls = []
    monkeypatch.setattr(run, "analyse_region", fake_analysis(calls))
    st.cache_data.clear()
    yield calls
    st.cache_data.clear()


def test_nothing_is_analysed_until_a_valid_region_is_selected(analysed):
    app = start()
    app = type_box(app, (30.0, 60.0, 0.0, 10.0))
    assert analysed == [] and not app.get("plotly_chart")
    app = type_box(app, (45.8, 47.8, 5.9, 10.5))
    assert len(analysed) == 1 and len(app.get("plotly_chart")) == 1


def test_there_is_no_analyse_button(analysed):
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    assert [button.label for button in app.button] == ["Clear selection"]


def test_drawn_rectangle_is_analysed_without_a_click(analysed, monkeypatch):
    ring = [[5.9, 45.8], [5.9, 47.8], [10.5, 47.8], [10.5, 45.8], [5.9, 45.8]]
    drawing = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}}
    monkeypatch.setattr(
        streamlit_folium, "st_folium",
        lambda figure, key=None, **options: {"last_active_drawing": drawing if key == "map_0" else None})
    app = start()
    assert analysed == [(45.8, 47.8, 5.9, 10.5, 1981, pd_year(), "t2m")]
    assert len(app.get("plotly_chart")) == 1


def test_selected_region_shows_the_trend_and_the_plot(analysed):
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    assert not app.exception and not app.error
    assert analysed == [(45.8, 47.8, 5.9, 10.5, 1981, pd_year(), "t2m")]
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Change per decade"] == "+0.50 °C"
    assert metrics["Statistically significant"].startswith("Yes")
    assert len(app.get("plotly_chart")) == 1
    assert any("warmed by about 0.50 °C per decade" in text.value for text in app.markdown)


def test_time_frame_is_passed_on_and_a_short_one_gives_a_note(analysed):
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    app.number_input(key="start_year").set_value(2018)
    app.number_input(key="end_year").set_value(2022).run()
    assert analysed[-1][4:6] == (2018, 2022)
    assert "at least 10 years" in app.warning[0].value
    assert not app.metric
    assert len(app.get("plotly_chart")) == 1


def test_analysis_errors_are_shown(analysed):
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    app.number_input(key="start_year").set_value(2020)
    app.number_input(key="end_year").set_value(2010).run()
    assert "after the end" in app.error[0].value
    assert not app.get("plotly_chart")


def test_result_follows_the_time_frame_and_clear_removes_it(analysed):
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    app.number_input(key="end_year").set_value(2020).run()
    assert analysed[-1][4:6] == (1981, 2020)
    assert len(app.get("plotly_chart")) == 1
    app.button[0].click().run()
    assert not app.get("plotly_chart")


def pd_year():
    import pandas as pd
    return pd.Timestamp.now().year


def test_chosen_variable_is_analysed_and_worded_in_its_own_unit(analysed):
    app = type_box(start(), (45.8, 47.8, 5.9, 10.5))
    assert app.selectbox(key="variable").options == [
        "Average temperature", "Maximum temperature", "Precipitation"]
    app.selectbox(key="variable").set_value("precip").run()
    assert not app.exception and not app.error
    assert analysed[-1][-1] == "precip"
    assert app.subheader[0].value.startswith("Precipitation:")
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Change per decade"] == "+0.50 mm/day"
    assert any("precipitation in this region increased by about 0.50 mm/day per decade" in text.value
               for text in app.markdown)
