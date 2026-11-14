"""Streamlit app: choose a region on the world map and see its temperature trend.

Run from the project folder with:
    python -m streamlit run app/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `src` can be imported

import folium
import pandas as pd
import requests
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

from src import analysis, fetch, plotting, run
from src.region import box_from_drawing

# Session keys of the four coordinate fields, in the order fetch and run expect.
FIELDS = ("lat_min", "lat_max", "lon_min", "lon_max")
THIS_YEAR = pd.Timestamp.now().year

st.set_page_config(page_title="Earth System Trend Detective", layout="wide")
st.title("Earth System Trend Detective")
st.write(
    "Draw a rectangle on the map with the square button at the top left, "
    "or type the coordinates below the map. Then choose a time frame and press Analyse."
)

state = st.session_state
state.setdefault("map_version", 0)
state.setdefault("result", None)
state.setdefault("result_error", None)
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
    state.result = None
    state.result_error = None
    redraw_map()


@st.cache_data(show_spinner=False)
def cached_analysis(box, start, end):
    """Fetch and analyse one region and time frame; repeats are answered from memory."""
    return run.analyse_region(*box, start=start, end=end, how="max")


def p_text(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def describe(result):
    """One plain sentence about the trend."""
    trend = result["trend"]
    period = f"Between {result['start']} and {result['end']}"
    subject = "the warmest part of this region"
    if not trend["significant"]:
        return f"{period}, {subject} shows no statistically significant temperature trend."
    rate = abs(trend["slope_per_decade"])
    verb = "warmed" if trend["slope_per_decade"] > 0 else "cooled"
    years = trend["n_months"] / 12
    return (
        f"{period}, {subject} {verb} by about {rate:.2f} °C per decade, "
        f"roughly {rate * years / 10:.1f} °C over those {years:.0f} years."
    )


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
box_is_valid = False
if box is None:
    st.info("No region selected yet.")
else:
    try:
        fetch.check_box(*box)
    except ValueError as problem:
        st.error(str(problem))
    else:
        box_is_valid = True
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

# --- Time frame and Analyse button ---------------------------------------------
start_column, end_column, button_column = st.columns([1, 1, 2], vertical_alignment="bottom")
start_year = start_column.number_input("Start year", key="start_year", min_value=fetch.FIRST_YEAR,
                                       max_value=THIS_YEAR, value=fetch.FIRST_YEAR, step=1)
end_year = end_column.number_input("End year", key="end_year", min_value=fetch.FIRST_YEAR,
                                   max_value=THIS_YEAR, value=THIS_YEAR, step=1)
if button_column.button("Analyse", key="analyse", type="primary", disabled=not box_is_valid):
    with st.spinner("Fetching NASA data and computing the trend..."):
        try:
            state.result = cached_analysis(box, int(start_year), int(end_year))
            state.result_error = None
        except (ValueError, RuntimeError, requests.RequestException) as problem:
            state.result = None
            state.result_error = str(problem)

# --- Analysis result -----------------------------------------------------------
if state.result_error:
    st.error(state.result_error)

result = state.result
if result:
    south, north, west, east = result["box_lat_lon"]
    trend = result["trend"]
    st.subheader(
        f"Latitude {south:g} to {north:g}, longitude {west:g} to {east:g}, "
        f"{result['start']} to {result['end']}"
    )

    figure = plotting.build_time_series_figure(
        {"Monthly anomaly": result["anomalies"].to_frame()},
        title="Temperature of the warmest grid cell, compared with normal",
        y_title=f"Difference from the {result['anomaly_baseline'][0]}–{result['anomaly_baseline'][1]} "
                "average for that month (°C)",
        x_title="",
    )
    if trend:
        st.write(describe(result))
        slope = trend["slope_per_decade"]
        plotting.add_trend_line(
            figure, analysis.trend_line(result["anomalies"], slope),
            f"Trend (Sen's slope): {slope:+.2f} °C per decade",
        )
        level = f"{trend['confidence_level']:.0%}"
        verdict = "Yes" if trend["significant"] else "No"
        metrics = st.columns(4)
        metrics[0].metric("Change per decade", f"{slope:+.2f} °C")
        metrics[1].metric(f"Likely range ({level})",
                          f"{trend['ci_low_per_decade']:+.2f} to {trend['ci_high_per_decade']:+.2f} °C")
        metrics[2].metric("Statistically significant",
                          f"{verdict} ({p_text(trend['p_value_autocorr'])})")
        metrics[3].metric("Months of data", trend["n_months"])
    else:
        st.warning(result["trend_note"])

    st.plotly_chart(figure, key="trend_plot")
    st.caption(
        f"Data: {result['source']} reanalysis, 2 m air temperature, [original NASA request]"
        f"({result['source_url']}). A reanalysis is a weather model corrected with observations, "
        "not a direct measurement. Each month shows the warmest NASA grid cell in the region "
        f"({result['grid_cells']} cells, each about 50 km wide). "
        "Method: seasonal Mann-Kendall test and seasonal Sen's slope."
    )
