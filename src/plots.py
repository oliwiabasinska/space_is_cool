"""Plotly figures for the trend analysis. Each function returns a Figure."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.trends import BASELINE, anomalies, year_month_table

SOURCE = "Data: NASA POWER (MERRA-2 reanalysis), 2 m air temperature"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LAT_STEP, LON_STEP = 0.5, 0.625  # size of one MERRA-2 grid cell in degrees


def _p_text(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _caption(fig: go.Figure, y: float = -0.16) -> go.Figure:
    fig.add_annotation(text=SOURCE, xref="paper", yref="paper", x=0, y=y,
                       showarrow=False, font=dict(size=11, color="gray"), xanchor="left")
    return fig


def trend_figure(series: pd.Series, result: dict, title: str, baseline=BASELINE) -> go.Figure:
    """Monthly anomalies with the Sen's slope line and its confidence band."""
    anomaly = anomalies(series, baseline)
    years = anomaly.index.year + (anomaly.index.month - 0.5) / 12
    middle = years.to_series().median()
    centre = anomaly.median()

    def line(slope_per_decade):
        return centre + slope_per_decade / 10 * (years - middle)

    level = f"{result['confidence_level']:.0%}"
    verdict = "significant" if result["significant"] else "not significant"
    subtitle = (
        f"Sen's slope {result['slope_per_decade']:+.2f} °C per decade "
        f"({level} interval {result['ci_low_per_decade']:+.2f} to {result['ci_high_per_decade']:+.2f}), "
        f"{verdict}, {_p_text(result['p_value_autocorr'])}, {result['n_months']} months"
    )

    fig = go.Figure()
    fig.add_bar(x=anomaly.index, y=anomaly, name="Monthly anomaly",
                marker_color=["#c0392b" if v > 0 else "#2e6db4" for v in anomaly],
                hovertemplate="%{x|%b %Y}: %{y:+.2f} °C<extra></extra>")
    fig.add_scatter(x=anomaly.index, y=line(result["ci_high_per_decade"]), mode="lines",
                    line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=anomaly.index, y=line(result["ci_low_per_decade"]), mode="lines",
                    line=dict(width=0), fill="tonexty", fillcolor="rgba(0,0,0,0.15)",
                    name=f"{level} interval of the slope", hoverinfo="skip")
    fig.add_scatter(x=anomaly.index, y=line(result["slope_per_decade"]), mode="lines",
                    line=dict(color="black", width=2), name="Sen's slope", hoverinfo="skip")
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>{subtitle}</sup>"),
        yaxis_title=f"Difference from the {baseline[0]}–{baseline[1]} average (°C)",
        template="plotly_white", bargap=0, legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1, xanchor="right"),
        margin=dict(b=90),
    )
    return _caption(fig)


def anomaly_heatmap(series: pd.Series, title: str, baseline=BASELINE) -> go.Figure:
    """Year by month grid of anomalies: blue is colder than the baseline, red warmer."""
    table = year_month_table(anomalies(series, baseline))
    limit = float(table.abs().max().max())
    fig = go.Figure(go.Heatmap(
        z=table.to_numpy(), x=MONTHS, y=table.index,
        colorscale="RdBu_r", zmid=0, zmin=-limit, zmax=limit,
        colorbar=dict(title="°C"), hoverongaps=False,
        hovertemplate="%{x} %{y}: %{z:+.2f} °C<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>Difference from the {baseline[0]}–{baseline[1]} "
                        f"average for that month. White cells have no data yet.</sup>"),
        yaxis=dict(autorange="reversed", title="Year", dtick=5),
        template="plotly_white", height=900, width=700, margin=dict(b=90),
    )
    return _caption(fig, y=-0.07)


def cell_trend_map(cell_table: pd.DataFrame, title: str) -> go.Figure:
    """Map of Sen's slope per grid cell. Cells without a significant trend get a cross."""
    cell_table = cell_table.reset_index(drop=True)
    features = []
    for i, row in cell_table.iterrows():
        south, north = row.lat - LAT_STEP / 2, row.lat + LAT_STEP / 2
        west, east = row.lon - LON_STEP / 2, row.lon + LON_STEP / 2
        ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
        features.append({"type": "Feature", "id": i,
                         "geometry": {"type": "Polygon", "coordinates": [ring]}})

    slopes = cell_table["slope_per_decade"]
    # One-directional colours when every cell moves the same way, otherwise blue-white-red.
    if slopes.min() >= 0:
        colours = dict(colorscale="YlOrRd", zmin=0, zmax=float(slopes.max()))
    else:
        limit = float(slopes.abs().max())
        colours = dict(colorscale="RdBu_r", zmid=0, zmin=-limit, zmax=limit)

    hover = [
        f"{r.lat:.2f}°N, {r.lon:.3f}°E, {r.elevation_m:.0f} m<br>"
        f"{r.slope_per_decade:+.2f} °C per decade "
        f"({r.ci_low_per_decade:+.2f} to {r.ci_high_per_decade:+.2f})<br>"
        f"{_p_text(r.p_value_autocorr)}, {'significant' if r.significant else 'not significant'}"
        for r in cell_table.itertuples()
    ]
    fig = go.Figure(go.Choroplethmap(
        geojson={"type": "FeatureCollection", "features": features},
        locations=cell_table.index, z=slopes, text=hover, hovertemplate="%{text}<extra></extra>",
        marker=dict(opacity=0.65, line=dict(width=0.5, color="white")),
        colorbar=dict(title="°C per<br>decade"), **colours,
    ))
    weak = cell_table[~cell_table["significant"]]
    if len(weak):
        fig.add_trace(go.Scattermap(
            lat=weak["lat"], lon=weak["lon"], mode="text", text=["✕"] * len(weak),
            textfont=dict(size=18, color="black"), hoverinfo="skip", name="Not significant",
        ))

    n_weak = len(weak)
    note = ("Every cell has a statistically significant trend." if n_weak == 0
            else f"✕ marks the {n_weak} cells whose trend is not statistically significant.")
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>Sen's slope per grid cell (about 50 km wide). {note}</sup>"),
        map=dict(style="carto-positron", zoom=6.2,
                 center=dict(lat=float(cell_table.lat.mean()), lon=float(cell_table.lon.mean()))),
        height=650, width=950, margin=dict(l=10, r=10, b=60), showlegend=False,
    )
    return _caption(fig, y=-0.07)
