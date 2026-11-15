"""Turn a shape drawn on the map into a latitude/longitude box."""

from __future__ import annotations


def box_from_drawing(feature) -> tuple[float, float, float, float] | None:
    """(lat_min, lat_max, lon_min, lon_max) of a GeoJSON shape, or None if there is none.

    The map can be scrolled sideways past the date line, which gives longitudes
    beyond +/-180. Those are shifted back by whole turns of the globe, and
    whatever still sticks out is cut off at the edge.
    """
    try:
        ring = feature["geometry"]["coordinates"][0]
        lons = [float(point[0]) for point in ring]
        lats = [float(point[1]) for point in ring]
    except (TypeError, KeyError, IndexError, ValueError):
        return None
    if not lons:
        return None

    shift = 360 * round((min(lons) + max(lons)) / 2 / 360)
    lon_min, lon_max = min(lons) - shift, max(lons) - shift
    lat_min, lat_max = min(lats), max(lats)
    return (
        round(max(lat_min, -90.0), 3),
        round(min(lat_max, 90.0), 3),
        round(max(lon_min, -180.0), 3),
        round(min(lon_max, 180.0), 3),
    )
