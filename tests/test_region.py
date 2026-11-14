"""Tests for src/region.py."""

from src.region import box_from_drawing


def rectangle(west, south, east, north):
    ring = [[west, south], [west, north], [east, north], [east, south], [west, south]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}}


def test_rectangle_becomes_lat_lon_box():
    assert box_from_drawing(rectangle(5.9, 45.8, 10.5, 47.8)) == (45.8, 47.8, 5.9, 10.5)


def test_coordinates_are_rounded():
    assert box_from_drawing(rectangle(5.90004, 45.79996, 10.5, 47.8)) == (45.8, 47.8, 5.9, 10.5)


def test_map_scrolled_past_the_date_line_is_shifted_back():
    assert box_from_drawing(rectangle(365.9, 45.8, 370.5, 47.8)) == (45.8, 47.8, 5.9, 10.5)
    assert box_from_drawing(rectangle(-354.1, 45.8, -349.5, 47.8)) == (45.8, 47.8, 5.9, 10.5)


def test_box_is_cut_off_at_the_edge_of_the_world():
    assert box_from_drawing(rectangle(170, 80, 185, 95)) == (80.0, 90.0, 170.0, 180.0)


def test_nothing_drawn_gives_none():
    assert box_from_drawing(None) is None
    assert box_from_drawing({}) is None
    assert box_from_drawing({"geometry": {"coordinates": []}}) is None
