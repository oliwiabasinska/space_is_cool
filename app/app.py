"""Streamlit app: a landing page, then choose a region on the world map and see its climate trend.

Run from the project folder with:
    python -m streamlit run app/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `src` can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))  # so sibling app modules can be imported

import folium
import pandas as pd
import requests
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

from app_landing import render_landing_page
from src import analysis, fetch, plotting, run, variables
from src.map_selector import DarkBasemap, RegionSelector
from src.region import box_from_drawing

# Session keys of the four coordinate fields, in the order fetch and run expect.
FIELDS = ("lat_min", "lat_max", "lon_min", "lon_max")
THIS_YEAR = pd.Timestamp.now().year

st.set_page_config(page_title="Earth System Trend Detective", layout="wide")
state = st.session_state
state.setdefault("page", "landing")

if state.page == "landing":
    render_landing_page()
    st.stop()

st.title("Earth System Trend Detective")
st.write("Double-click to draw a region. Optional fine adjustment with coordinates.")

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


def mark_variable_selected():
    state["variable_user_selected"] = True


@st.cache_data(show_spinner=False)
def cached_analysis(box, start, end, variable):
    """Fetch and analyse one region, time frame and variable; repeats are answered from memory."""
    return run.analyse_region(*box, start=start, end=end, variable=variable)


def p_text(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def investigation_copy(variable, slope, significant, p_value, start, end, unit):
    """Build the question and plain-language evidence summary for one variable."""
    rising = slope > 0
    direction = "upward" if rising else "downward"
    if variable == "precip":
        question = "Is precipitation changing in this region?" if slope == 0 else (
            "Is precipitation increasing in this region?"
            if rising else "Is precipitation decreasing in this region?"
        )
        subject = "Precipitation in this region"
        change = "has increased" if rising else "has decreased"
    elif variable == "t2m_max":
        question = "Is there a clear trend in the highest temperatures?" if slope == 0 else (
            "Are the highest temperatures getting hotter?"
            if rising else "Are the highest temperatures getting cooler?"
        )
        subject = "The highest temperatures recorded in this region"
        change = "have risen" if rising else "have fallen"
    else:
        question = "Is the region's temperature changing?" if slope == 0 else (
            "Is the region getting warmer?"
            if rising else "Is the region getting cooler?"
        )
        subject = "The monthly average temperature in the warmest part of this region"
        change = "has risen" if rising else "has fallen"

    p_label = p_text(p_value)
    if significant:
        interpretation = (
            f"{subject} {change} between {start} and {end}. The estimated change is "
            f"{slope:+.2f} {unit} per decade, with statistical evidence of a "
            f"{direction} trend."
        )
        evidence = f"Statistical evidence of a {direction} trend ({p_label})."
    else:
        interpretation = (
            f"The estimated change in {subject.lower()} is {slope:+.2f} {unit} per decade, "
            f"but the data from {start} to {end} do not establish a clear upward or "
            f"downward trend."
        )
        evidence = f"The data do not establish a clear trend ({p_label})."
    return question, interpretation, evidence


# --- Map ---------------------------------------------------------------------
world = folium.Map(location=[20, 0], zoom_start=2, min_zoom=2, max_zoom=8, tiles=None)
DarkBasemap().add_to(world)
# Draw is added only for its drawing code; with every shape off it shows no toolbar.
Draw(
    draw_options={
        "rectangle": False, "polyline": False, "polygon": False,
        "circle": False, "marker": False, "circlemarker": False,
    },
    edit_options={"edit": False, "remove": False},
).add_to(world)

box = selected_box()
corners = None
if box and box[0] < box[1] and box[2] < box[3]:
    corners = [[box[0], box[2]], [box[1], box[3]]]
    world.fit_bounds(corners, padding=(80, 80))
RegionSelector(corners).add_to(world)

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

# --- Variable and time frame ---------------------------------------------------
start_column, end_column = st.columns(2)
start_year = start_column.number_input(
    "Start year", key="start_year", min_value=fetch.FIRST_YEAR,
    max_value=THIS_YEAR, value=fetch.FIRST_YEAR, step=1)
end_year = end_column.number_input(
    "End year", key="end_year", min_value=fetch.FIRST_YEAR,
    max_value=THIS_YEAR, value=THIS_YEAR, step=1)

# --- Analysis: compare available variables for the current region and time frame --
results_by_variable = {}
if box_is_valid:
    with st.spinner("Comparing climate trends across available variables..."):
        try:
            results_by_variable = {
                name: cached_analysis(box, int(start_year), int(end_year), name)
                for name in variables.VARIABLES
            }
        except (ValueError, RuntimeError, requests.RequestException) as problem:
            st.error(str(problem))
            results_by_variable = {}

if results_by_variable:
    def evidence_score(name):
        trend_result = results_by_variable[name]["trend"]
        if trend_result is None:
            return float("inf")
        p_value = trend_result["p_value_autocorr"]
        return p_value if pd.notna(p_value) else float("inf")

    ranked_variables = sorted(results_by_variable, key=evidence_score)
    if not state.get("variable_user_selected", False):
        state["variable"] = ranked_variables[0]
    current_variable = state.get("variable")
    selected_index = (
        ranked_variables.index(current_variable)
        if current_variable in ranked_variables else 0
    )
    variable = st.selectbox(
        "Variable (ranked by statistical evidence)",
        options=ranked_variables,
        index=selected_index,
        key="variable",
        on_change=mark_variable_selected,
        format_func=lambda name: variables.VARIABLES[name].label,
        help=(
            "Variables are ordered by their autocorrelation-adjusted p-value, "
            "with the strongest statistical evidence first. Select another to explore it."
        ),
    )
    result = results_by_variable[variable]
else:
    result = None

if result:
    south, north, west, east = result["box_lat_lon"]
    trend = result["trend"]
    chosen = variables.get(result["variable"])
    unit = chosen.unit
    st.caption(
        f"{chosen.label} · latitude {south:g} to {north:g}, longitude {west:g} to {east:g} · "
        f"{result['start']} to {result['end']}"
    )

    figure = plotting.build_time_series_figure(
        {"Monthly anomaly": result["anomalies"].to_frame()},
        title=chosen.title,
        y_title=f"Difference from the {result['anomaly_baseline'][0]}–{result['anomaly_baseline'][1]} "
                f"average for that month ({unit})",
        x_title="Year",
    )
    is_precipitation = result["variable"] == "precip"
    is_light = st.context.theme.type == "light"
    theme = {
        "accent": (
            "#007c91" if is_precipitation else "#bf3568"
        ) if is_light else (
            "#35e6ff" if is_precipitation else "#ff4d8d"
        ),
        "soft": (
            "#e6f5f7" if is_precipitation else "#faeaf0"
        ) if is_light else (
            "#10252b" if is_precipitation else "#291724"
        ),
        "line": (
            "#007c91" if is_precipitation else "#bf3568"
        ) if is_light else (
            "#5aeaff" if is_precipitation else "#ff6b9d"
        ),
        "value": (
            "#075e6d" if is_precipitation else "#9c2451"
        ) if is_light else (
            "#9af3ff" if is_precipitation else "#ff91b5"
        ),
        "glow": (
            "rgba(0, 124, 145, 0.12)" if is_precipitation
            else "rgba(191, 53, 104, 0.12)"
        ) if is_light else (
            "rgba(53, 230, 255, 0.2)" if is_precipitation
            else "rgba(255, 77, 141, 0.2)"
        ),
        "band": (
            "rgba(0, 124, 145, 0.14)" if is_precipitation
            else "rgba(191, 53, 104, 0.14)"
        ) if is_light else (
            "rgba(53, 230, 255, 0.18)" if is_precipitation
            else "rgba(255, 77, 141, 0.18)"
        ),
        "icon": "🌧️" if is_precipitation else "🌡️",
        "panel": "#ffffff" if is_light else "#10141d",
        "heading": "#172033" if is_light else "#f8fafc",
        "text": "#344054" if is_light else "#e2e8f0",
        "muted": "#526173" if is_light else "#cbd5e1",
        "interpretation": "#344054" if is_light else "#d4dce8",
        "plot": "#ffffff" if is_light else "#0b0f17",
        "grid": "#e4e7ec" if is_light else "#263244",
        "zero": "#98a2b3" if is_light else "#475569",
        "insignificant": "#98a2b3" if is_light else "#a8b3c2",
    }
    figure.data[0].update(
        line={"color": theme["accent"], "width": 1.5},
        marker={"color": theme["accent"], "size": 4},
    )

    if trend:
        slope = trend["slope_per_decade"]
        significant = trend["significant"]
        level = f"{trend['confidence_level']:.0%}"
        question, interpretation, evidence = investigation_copy(
            result["variable"], slope, significant, trend["p_value_autocorr"],
            result["start"], result["end"], unit,
        )
        lower = analysis.trend_line(
            result["anomalies"], trend["ci_low_per_decade"])
        upper = analysis.trend_line(
            result["anomalies"], trend["ci_high_per_decade"])
        figure.add_scatter(
            x=lower.index, y=lower.to_numpy(), mode="lines",
            line={"color": "rgba(0, 0, 0, 0)", "width": 0},
            showlegend=False, hoverinfo="skip",
        )
        figure.add_scatter(
            x=upper.index, y=upper.to_numpy(), mode="lines",
            line={"color": "rgba(0, 0, 0, 0)", "width": 0},
            fill="tonexty", fillcolor=theme["band"],
            showlegend=False, hoverinfo="skip",
        )
        trend_label = f"Sen's slope: {slope:+.2f} {unit} per decade"
        plotting.add_trend_line(
            figure, analysis.trend_line(result["anomalies"], slope),
            trend_label if significant else f"{trend_label} (not significant)",
            color=theme["line"] if significant else theme["insignificant"],
        )
        observations = result["anomalies"].dropna()
        if not observations.empty:
            peak_date = observations.idxmax()
            figure.add_annotation(
                x=peak_date, y=float(observations.loc[peak_date]),
                text=f"Highest anomaly · {peak_date:%Y}",
                showarrow=True, arrowhead=2, ax=0, ay=-32,
                font={"size": 10, "color": theme["heading"]},
                bgcolor=theme["panel"],
                bordercolor=theme["accent"], borderwidth=1, borderpad=4,
            )

    figure.update_layout(
        title=None, template="plotly_white" if is_light else "plotly_dark",
        height=390, showlegend=False, font={"color": theme["text"]},
        margin={"l": 58, "r": 16, "t": 16, "b": 48},
        paper_bgcolor="rgba(0, 0, 0, 0)", plot_bgcolor=theme["plot"],
    )
    figure.update_xaxes(
        title_text="Year", tickangle=0, showgrid=True, gridcolor=theme["grid"],
        zeroline=False, zerolinecolor=theme["zero"],
        tickfont={"color": theme["muted"]}, title_font={"color": theme["text"]},
    )
    figure.update_yaxes(
        showgrid=True, gridcolor=theme["grid"], zeroline=False,
        tickfont={"color": theme["muted"]}, title_font={"color": theme["text"]},
    )

    if trend:
        question_icon = theme["icon"]
        direction_icon = "✓" if significant else "–"
        evidence_title = "Evidence detected" if significant else "Inconclusive"
        evidence_color = (
            "#187a30" if significant else "#9a5d00"
        ) if is_light else (
            "#a3ff4d" if significant else "#ffc857"
        )
        evidence_glow = (
            ("rgba(24, 122, 48, 0.12)" if significant else "rgba(154, 93, 0, 0.12)")
            if is_light else
            ("rgba(163, 255, 77, 0.18)" if significant else "rgba(255, 200, 87, 0.16)")
        )
        trend_tooltip = (
            "Sen's slope is the median of pairwise changes over time, expressed per decade. "
            f"The shaded {level} chart band shows its confidence interval."
        )
        evidence_tooltip = (
            "Based on the autocorrelation-adjusted seasonal Mann-Kendall test. "
            "Statistical significance indicates evidence for a trend, not its size "
            "or practical importance."
        )
        chart_tooltip = (
            f"{chosen.note}. The shaded {level} interval represents uncertainty in "
            "Sen's slope; it is not a prediction interval for individual observations."
        )
        chart_title = f"Monthly {chosen.label.lower()} trend"
        with st.container(border=True):
            st.markdown("### Climate Investigation")
            findings, visualization = st.columns([43, 57], gap="medium")
            with findings:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:0.8rem;'
                    f'margin:0.2rem 0 1rem;">'
                    f'<div aria-hidden="true" style="display:flex;align-items:center;'
                    f'justify-content:center;flex:0 0 3.2rem;height:3.2rem;'
                    f'border:1px solid {theme["accent"]};border-radius:0.9rem;'
                    f'background:{theme["soft"]};font-size:1.6rem;'
                    f'box-shadow:0 0 14px {theme["glow"]};">'
                    f'{question_icon}</div>'
                    f'<div style="font-size:1.35rem;font-weight:750;line-height:1.2;'
                    f'color:{theme["heading"]};">{question}</div></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));'
                    f'gap:0.65rem;align-items:stretch;">'
                    f'<div style="box-sizing:border-box;min-height:145px;padding:0.9rem;'
                    f'border:1px solid {theme["accent"]};border-radius:0.9rem;'
                    f'background:{theme["panel"]};box-shadow:0 0 0 1px {theme["glow"]},'
                    f'0 0 16px {theme["glow"]};">'
                    f'<div style="font-size:0.84rem;font-weight:700;color:{theme["text"]};">'
                    f'Estimated trend <span title="{trend_tooltip}" '
                    f'aria-label="Trend estimate information" '
                    f'style="cursor:help;color:{theme["accent"]};">ⓘ</span></div>'
                    f'<div style="margin-top:0.55rem;font-size:1.5rem;font-weight:750;'
                    f'line-height:1.1;color:{theme["value"]};">{slope:+.2f} {unit}</div>'
                    f'<div style="margin-top:0.3rem;font-size:0.82rem;color:{theme["muted"]};">'
                    f'per decade</div></div>'
                    f'<div style="box-sizing:border-box;min-height:145px;padding:0.9rem;'
                    f'border:1px solid {evidence_color};border-radius:0.9rem;'
                    f'background:{theme["panel"]};box-shadow:0 0 0 1px {evidence_glow},'
                    f'0 0 16px {evidence_glow};">'
                    f'<div style="font-size:0.84rem;font-weight:700;color:{theme["text"]};">'
                    f'Statistical evidence <span title="{evidence_tooltip}" '
                    f'aria-label="Statistical evidence information" '
                    f'style="cursor:help;color:{evidence_color};">ⓘ</span></div>'
                    f'<div style="margin-top:0.55rem;font-size:1.08rem;font-weight:750;'
                    f'line-height:1.2;color:{evidence_color};">'
                    f'{direction_icon} {evidence_title}</div>'
                    f'<div style="margin-top:0.45rem;font-size:0.78rem;line-height:1.3;'
                    f'color:{theme["muted"]};">{evidence}</div></div></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="margin-top:1rem;">'
                    f'<div style="margin-bottom:0.4rem;font-size:1rem;font-weight:700;'
                    f'color:{theme["heading"]};">What does this mean?</div>'
                    f'<div style="border-left:3px solid {theme["accent"]};'
                    f'padding:0.1rem 0 0.1rem 0.8rem;font-size:0.9rem;'
                    f'line-height:1.5;color:{theme["interpretation"]};">{interpretation}</div></div>',
                    unsafe_allow_html=True,
                )
            with visualization:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="margin:0.1rem 0 0.1rem;font-size:1.05rem;'
                        f'font-weight:750;color:{theme["heading"]};">{chart_title} '
                        f'<span title="{chart_tooltip}" aria-label="Chart information" '
                        f'style="cursor:help;font-size:0.85rem;color:{theme["accent"]};">'
                        f'ⓘ</span></div>',
                        unsafe_allow_html=True,
                    )
                    st.plotly_chart(
                        figure, key="trend_plot", use_container_width=True,
                        config={"displayModeBar": False},
                    )
                    st.markdown(
                        f'<div style="display:flex;flex-wrap:wrap;gap:0.8rem;'
                        f'font-size:0.76rem;color:{theme["muted"]};">'
                        f'<span><span style="color:{theme["accent"]};">●</span> '
                        f'Monthly observations</span>'
                        f'<span><span style="color:{theme["line"]};">━</span> '
                        f"Sen's slope</span>"
                        f'<span><span style="display:inline-block;width:0.8rem;'
                        f'height:0.55rem;background:{theme["band"]};'
                        f'vertical-align:middle;"></span> {level} slope confidence interval</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.warning(result["trend_note"])
        st.plotly_chart(figure, key="trend_plot", use_container_width=True)

    st.caption(
        f"Data: {result['source']} reanalysis, variable {result['parameter']}, [original NASA request]"
        f"({result['source_url']}). A reanalysis is a weather model corrected with observations, "
        f"not a direct measurement. {chosen.note} "
        f"({result['grid_cells']} cells, each about 50 km wide). "
        "Method: seasonal Mann-Kendall test and seasonal Sen's slope."
    )
