"""Streamlit app: choose a region on the world map and see its climate trend.

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
import streamlit.components.v1 as components
from folium.plugins import Draw
from streamlit_folium import st_folium

from src import analysis, fetch, plotting, run, variables
from src.region import box_from_drawing

# Session keys of the four coordinate fields, in the order fetch and run expect.
FIELDS = ("lat_min", "lat_max", "lon_min", "lon_max")
THIS_YEAR = pd.Timestamp.now().year

st.set_page_config(page_title="Earth System Trend Detective", layout="wide")
state = st.session_state
state.setdefault("page", "landing")

if state.page == "landing":
    st.title("Earth System Trend Detective")
    st.write("Explore the examples, then open the interactive climate analysis map.")
    components.html(
        """
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <style>
            html, body { margin: 0; background: #080b10; color: #fff; font-family: sans-serif; }
            #world-map { width: 100%; height: 480px; background: #080b10; }
            .leaflet-container { background: #080b10; }
            .coastline-glow {
              filter: drop-shadow(0 0 2px #fff) drop-shadow(0 0 6px rgba(255, 255, 255, .9));
            }
            .laser-marker { background: transparent; border: 0; }
            .laser-marker span {
              display: block; width: 12px; height: 12px; margin: 3px;
              border-radius: 50%; background: #ff2020;
              box-shadow: 0 0 6px 3px rgba(255, 32, 32, .9), 0 0 18px 7px rgba(255, 32, 32, .55);
              animation: pulse 1.5s ease-in-out infinite;
            }
            @keyframes pulse {
              50% { box-shadow: 0 0 9px 5px rgba(255, 32, 32, 1), 0 0 24px 10px rgba(255, 32, 32, .65); }
            }
            .slide-indicators {
              height: 34px; display: flex; justify-content: center; align-items: center; gap: 12px;
            }
            .slide-dot {
              width: 10px; height: 10px; padding: 0; border: 0; border-radius: 50%;
              background: #59616b; cursor: default;
            }
            .slide-dot.active { background: #ff2020; box-shadow: 0 0 8px 3px rgba(255, 32, 32, .7); }
            #map-error {
              display: none; position: absolute; z-index: 1000; top: 10px; left: 50px;
              padding: 6px 10px; background: #241313; color: #fff; border-radius: 4px;
            }
          </style>
        </head>
        <body>
          <div id="world-map"></div>
          <div class="slide-indicators" role="status" aria-label="Slideshow position">
            <button class="slide-dot active" aria-label="Slide 1 of 3"></button>
            <button class="slide-dot" aria-label="Slide 2 of 3"></button>
            <button class="slide-dot" aria-label="Slide 3 of 3"></button>
          </div>
          <div id="map-error"></div>
          <script>
            const map = L.map("world-map", {
              center: [20, 0], zoom: 2, minZoom: 2, maxZoom: 6
            });
            const locations = [
              { name: "Amsterdam, Netherlands", coordinates: [52.3676, 4.9041] },
              { name: "Uluwatu, Bali, Indonesia", coordinates: [-8.8291, 115.0849] },
              { name: "San Francisco, United States", coordinates: [37.7749, -122.4194] }
            ];
            const laserIcon = L.divIcon({
              className: "laser-marker",
              html: "<span></span>",
              iconSize: [18, 18],
              iconAnchor: [9, 9]
            });
            locations.forEach(location => {
              L.marker(location.coordinates, { icon: laserIcon })
                .bindTooltip(location.name)
                .addTo(map);
            });

            fetch("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson")
              .then(response => {
                if (!response.ok) throw new Error(`Coastline data request failed (${response.status})`);
                return response.json();
              })
              .then(land => L.geoJSON(land, {
                style: {
                  color: "#fff",
                  weight: 1.5,
                  opacity: 1,
                  fillColor: "#11151b",
                  fillOpacity: 1,
                  className: "coastline-glow"
                }
              }).addTo(map))
              .catch(error => {
                const message = document.getElementById("map-error");
                message.textContent = `Unable to load glowing coastlines: ${error.message}`;
                message.style.display = "block";
                console.error(error);
              });

            const dots = Array.from(document.querySelectorAll(".slide-dot"));
            let currentSlide = 0;
            window.setInterval(() => {
              dots[currentSlide].classList.remove("active");
              currentSlide = (currentSlide + 1) % dots.length;
              dots[currentSlide].classList.add("active");
              dots.forEach((dot, index) => {
                dot.setAttribute(
                  "aria-label",
                  `Slide ${index + 1} of 3${index === currentSlide ? ", current" : ""}`
                );
              });
            }, 10000);
          </script>
        </body>
        </html>
        """,
        height=514,
        scrolling=False,
    )
    st.markdown(
        """
        <style>
          div[data-testid="stButton"] > button {
            border: 1.5px solid #ff2020;
            color: #ff2020;
            background: transparent;
          }
          div[data-testid="stButton"] > button:hover {
            border-color: #ff5555;
            color: #fff;
            background: rgba(255, 32, 32, .15);
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, explore_column = st.columns([5, 1])
    if explore_column.button("Explore", key="explore_button", use_container_width=True):
        state.page = "explore"
        st.rerun()
    st.stop()

st.title("Earth System Trend Detective")
st.write(
    "Draw a rectangle on the map with the square button at the top left, "
    "or type the coordinates below the map. Then choose a variable and a time frame and press Analyse."
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
def cached_analysis(box, start, end, variable):
    """Fetch and analyse one region, time frame and variable; repeats are answered from memory."""
    return run.analyse_region(*box, start=start, end=end, variable=variable)


def p_text(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def describe(result):
    """One plain sentence about the trend."""
    trend = result["trend"]
    chosen = variables.get(result["variable"])
    period = f"Between {result['start']} and {result['end']}"
    if not trend["significant"]:
        return f"{period}, {chosen.subject} shows no statistically significant trend."
    rate = abs(trend["slope_per_decade"])
    verb = chosen.increase if trend["slope_per_decade"] > 0 else chosen.decrease
    years = trend["n_months"] / 12
    return (
        f"{period}, {chosen.subject} {verb} by about {rate:.2f} {chosen.unit} per decade, "
        f"roughly {rate * years / 10:.1f} {chosen.unit} over those {years:.0f} years."
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

# --- Variable, time frame and Analyse button -----------------------------------
variable_column, start_column, end_column, button_column = st.columns(
    [2, 1, 1, 2], vertical_alignment="bottom")
variable = variable_column.selectbox(
    "Variable", options=list(variables.VARIABLES), key="variable",
    format_func=lambda name: variables.VARIABLES[name].label)
start_year = start_column.number_input("Start year", key="start_year", min_value=fetch.FIRST_YEAR,
                                       max_value=THIS_YEAR, value=fetch.FIRST_YEAR, step=1)
end_year = end_column.number_input("End year", key="end_year", min_value=fetch.FIRST_YEAR,
                                   max_value=THIS_YEAR, value=THIS_YEAR, step=1)
if button_column.button("Analyse", key="analyse", type="primary", disabled=not box_is_valid):
    with st.spinner("Fetching NASA data and computing the trend..."):
        try:
            state.result = cached_analysis(box, int(start_year), int(end_year), variable)
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
    chosen = variables.get(result["variable"])
    unit = chosen.unit
    st.subheader(
        f"{chosen.label}: latitude {south:g} to {north:g}, longitude {west:g} to {east:g}, "
        f"{result['start']} to {result['end']}"
    )

    figure = plotting.build_time_series_figure(
        {"Monthly anomaly": result["anomalies"].to_frame()},
        title=chosen.title,
        y_title=f"Difference from the {result['anomaly_baseline'][0]}–{result['anomaly_baseline'][1]} "
                f"average for that month ({unit})",
        x_title="",
    )
    if trend:
        st.write(describe(result))
        slope = trend["slope_per_decade"]
        # A line that is not statistically significant is drawn grey and says so.
        label = f"Sen's slope: {slope:+.2f} {unit} per decade"
        plotting.add_trend_line(
            figure, analysis.trend_line(result["anomalies"], slope),
            f"Trend ({label})" if trend["significant"] else f"{label} (not significant)",
            color="black" if trend["significant"] else "gray",
        )
        level = f"{trend['confidence_level']:.0%}"
        verdict = "Yes" if trend["significant"] else "No"
        metrics = st.columns(4)
        metrics[0].metric("Change per decade", f"{slope:+.2f} {unit}")
        metrics[1].metric(f"Likely range ({level})",
                          f"{trend['ci_low_per_decade']:+.2f} to {trend['ci_high_per_decade']:+.2f} {unit}")
        metrics[2].metric("Statistically significant",
                          f"{verdict} ({p_text(trend['p_value_autocorr'])})")
        metrics[3].metric("Months of data", trend["n_months"])
    else:
        st.warning(result["trend_note"])

    st.plotly_chart(figure, key="trend_plot")
    st.caption(
        f"Data: {result['source']} reanalysis, variable {result['parameter']}, [original NASA request]"
        f"({result['source_url']}). A reanalysis is a weather model corrected with observations, "
        f"not a direct measurement. {chosen.note} "
        f"({result['grid_cells']} cells, each about 50 km wide). "
        "Method: seasonal Mann-Kendall test and seasonal Sen's slope."
    )
