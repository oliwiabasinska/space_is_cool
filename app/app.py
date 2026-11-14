"""Streamlit app: choose a region on the world map.

Run from the project folder with:
    python -m streamlit run app/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `src` can be imported

import folium
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

from src import fetch
from src.region import box_from_drawing

# Session keys of the four coordinate fields, in the order fetch and run expect.
FIELDS = ("lat_min", "lat_max", "lon_min", "lon_max")

st.set_page_config(page_title="Earth System Trend Detective", layout="wide")
st.title("Earth System Trend Detective")
st.write(
    "Draw a rectangle on the map with the square button at the top left, "
    "or type the coordinates below the map."
)

state = st.session_state
state.setdefault("map_version", 0)
for field in FIELDS:
    state.setdefault(field, None)


def selected_box():
    """The four coordinates, or None while any of them is still empty."""
    values = tuple(state[field] for field in FIELDS)
    return None if any(value is None for value in values) else values


def redraw_map():
    """Rebuild the map so it shows the current box and drops old drawings."""
    state.map_version += 1


def clear_selection():
    for field in FIELDS:
        state[field] = None
    redraw_map()


# --- Map ---------------------------------------------------------------------
world = folium.Map(location=[20, 0], zoom_start=2)
Draw(
    draw_options={
        "rectangle": True, "polyline": False, "polygon": False,
        "circle": False, "marker": False, "circlemarker": False,
    },
    edit_options={"edit": False, "remove": False},
).add_to(world)

box = selected_box()
if box and box[0] < box[1] and box[2] < box[3]:
    corners = [[box[0], box[2]], [box[1], box[3]]]
    folium.Rectangle(corners, color="#d62728", fill=True, fill_opacity=0.15,
                     tooltip="Selected region").add_to(world)
    world.fit_bounds(corners, padding=(80, 80))

map_data = st_folium(
    world, key=f"map_{state.map_version}", height=480, use_container_width=True,
    returned_objects=["last_active_drawing"],
)
drawn = box_from_drawing((map_data or {}).get("last_active_drawing"))
if drawn:
    for field, value in zip(FIELDS, drawn):
        state[field] = value
    redraw_map()
    st.rerun()

# --- Coordinate fields -------------------------------------------------------
labels = {
    "lat_min": "South (minimum latitude)", "lat_max": "North (maximum latitude)",
    "lon_min": "West (minimum longitude)", "lon_max": "East (maximum longitude)",
}
for column, field in zip(st.columns(4), FIELDS):
    limit = 90.0 if field.startswith("lat") else 180.0
    column.number_input(labels[field], key=field, min_value=-limit, max_value=limit,
                        step=0.5, format="%.3f", on_change=redraw_map)
st.button("Clear selection", on_click=clear_selection)

# --- Result of the selection ---------------------------------------------------
box = selected_box()
if box is None:
    st.info("No region selected yet.")
else:
    try:
        fetch.check_box(*box)
    except ValueError as problem:
        st.error(str(problem))
    else:
        lat_span, lon_span = box[1] - box[0], box[3] - box[2]
        st.success(
            f"Selected region: latitude {box[0]:g} to {box[1]:g}, longitude {box[2]:g} to {box[3]:g} "
            f"({lat_span:g}° × {lon_span:g}°)."
        )
        if lat_span < fetch.MIN_BOX_DEG or lon_span < fetch.MIN_BOX_DEG:
            st.caption(
                f"This region is smaller than {fetch.MIN_BOX_DEG:g}° on one side, so the data "
                "will come from the single NASA grid cell (about 50 km wide) at its centre."
            )
