"""Redraw Paris/paris_temp.jpeg, the chart in the landing page's Paris panel.

It uses the same data, statistics and look as the analysis page's chart:
monthly anomalies from paris_temp.csv, the seasonal Sen's slope with its
confidence band, and the highest anomaly marked.

Run from the project folder (needs the kaleido package to save the image):
    python Paris/make_paris_chart.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # so `src` can be imported

from src import analysis  # noqa: E402

ACCENT, LINE, BAND = "#ff4d8d", "#ff6b9d", "rgba(255, 77, 141, 0.18)"  # the app's temperature colours
PANEL, PLOT, GRID, TEXT, SOFT_TEXT = "#080b10", "#0b0f17", "#263244", "#f8fafc", "#cbd5e1"


def main() -> None:
    table = pd.read_csv(HERE / "paris_temp.csv", parse_dates=["date"], index_col="date")
    series = table["t2m_max_C"]
    anomalies = analysis.anomalies(series)
    trend = analysis.trend(series)
    slope = trend["slope_per_decade"]
    level = f"{trend['confidence_level']:.0%}"
    baseline = f"{analysis.BASELINE[0]}–{analysis.BASELINE[1]}"

    figure = go.Figure()
    figure.add_scatter(
        x=anomalies.index, y=anomalies.to_numpy(), mode="lines+markers", name="Monthly observations",
        line={"color": ACCENT, "width": 1.5}, marker={"color": ACCENT, "size": 4},
    )
    lower = analysis.trend_line(anomalies, trend["ci_low_per_decade"])
    upper = analysis.trend_line(anomalies, trend["ci_high_per_decade"])
    figure.add_scatter(x=lower.index, y=lower.to_numpy(), mode="lines",
                       line={"color": "rgba(0, 0, 0, 0)", "width": 0}, showlegend=False)
    figure.add_scatter(x=upper.index, y=upper.to_numpy(), mode="lines",
                       line={"color": "rgba(0, 0, 0, 0)", "width": 0},
                       fill="tonexty", fillcolor=BAND, name=f"{level} slope confidence interval")
    middle = analysis.trend_line(anomalies, slope)
    figure.add_scatter(x=middle.index, y=middle.to_numpy(), mode="lines",
                       line={"color": LINE, "width": 3.5},
                       name=f"Sen's slope: {slope:+.2f} °C per decade")

    peak = anomalies.idxmax()
    figure.add_annotation(
        x=peak, y=float(anomalies.loc[peak]), text=f"Highest anomaly · {peak:%Y}",
        showarrow=True, arrowhead=2, arrowcolor=TEXT, ax=-150, ay=4,
        font={"size": 14, "color": TEXT}, bgcolor="rgba(10, 15, 23, 0.9)",
        bordercolor=ACCENT, borderwidth=1, borderpad=4,
    )

    figure.update_layout(
        template="plotly_dark", width=760, height=600,
        title={"text": "Monthly maximum temperature trend in Paris", "x": 0.02, "y": 0.96,
               "font": {"size": 22, "color": TEXT}},
        font={"color": "#e2e8f0", "size": 15},
        margin={"l": 70, "r": 22, "t": 62, "b": 118},
        paper_bgcolor=PANEL, plot_bgcolor=PLOT,
        legend={"orientation": "h", "x": 0, "y": -0.17, "xanchor": "left", "yanchor": "top",
                "font": {"size": 14, "color": SOFT_TEXT}, "bgcolor": "rgba(0, 0, 0, 0)"},
    )
    figure.update_xaxes(title_text="Year", dtick="M60", tickformat="%Y", showgrid=True, gridcolor=GRID,
                        zeroline=False, tickfont={"color": SOFT_TEXT},
                        range=[anomalies.index.min() - pd.DateOffset(months=10),
                               anomalies.index.max() + pd.DateOffset(months=10)])
    figure.update_yaxes(title_text=f"Difference from the {baseline}<br>average for that month (°C)",
                        showgrid=True, gridcolor=GRID, zeroline=False, tickfont={"color": SOFT_TEXT})

    figure.write_image(HERE / "paris_temp.jpeg", scale=2)
    print(f"{series.index.min():%Y-%m} to {series.index.max():%Y-%m}, {len(series)} months: "
          f"{slope:+.2f} °C per decade ({level} interval {trend['ci_low_per_decade']:+.2f} to "
          f"{trend['ci_high_per_decade']:+.2f}), p = {trend['p_value_autocorr']:.4f}, "
          f"highest anomaly {anomalies.loc[peak]:+.1f} °C in {peak:%Y-%m}")


if __name__ == "__main__":
    main()
