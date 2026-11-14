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
