from __future__ import annotations

from collections.abc import Mapping
from math import ceil

import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative



def build_time_series_figure(
    datasets: Mapping[str, pd.DataFrame],
    title: str = "Time series by place",
    y_title: str = "Value",
    x_title: str | None = None,
) -> go.Figure:
    """Plot one date-indexed or date-column dataframe for each place."""
    if not datasets:
        raise ValueError("At least one place dataframe is required.")

    traces: list[tuple[str, pd.DatetimeIndex, pd.Series]] = []
    observed_dates: list[pd.Timestamp] = []

    for place, dataframe in datasets.items():
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError(f"Data for {place!r} must be a pandas DataFrame.")

        date_column = next(
            (column for column in dataframe.columns if str(column).lower() == "date"),
            None,
        )
        if date_column is None:
            if isinstance(dataframe.index, pd.RangeIndex):
                raise ValueError(
                    f"Data for {place!r} needs a 'date' column or date-like index."
                )
            raw_dates = dataframe.index
            value_columns = list(dataframe.columns)
        else:
            raw_dates = dataframe[date_column]
            value_columns = [
                column for column in dataframe.columns if column != date_column
            ]

        if len(value_columns) != 1:
            raise ValueError(
                f"Data for {place!r} must contain exactly one value column."
            )

        dates = pd.DatetimeIndex(pd.to_datetime(raw_dates, errors="coerce"))
        values = pd.to_numeric(dataframe[value_columns[0]], errors="coerce")
        valid_dates = dates[~dates.isna()]
        observed_dates.extend(valid_dates.normalize().tolist())

        valid_rows = ~dates.isna() & values.notna().to_numpy()
        traces.append(
            (
                place,
                dates[valid_rows].normalize(),
                values.loc[valid_rows].reset_index(drop=True),
            )
        )

    if not observed_dates:
        raise ValueError("The place dataframes contain no valid dates.")

    start = min(observed_dates)
    end = max(observed_dates)
    day_count = (end - start).days
    tick_count = min(9, day_count + 1)
    day_step = max(1, ceil(day_count / max(1, tick_count - 1)))
    tick_dates = list(pd.date_range(start, end, freq=f"{day_step}D"))
    if tick_dates[-1] != end:
        tick_dates.append(end)

    figure = go.Figure()
    colors = qualitative.Plotly
    for index, (place, dates, values) in enumerate(traces):
        color = colors[index % len(colors)]
        figure.add_trace(
            go.Scatter(
                x=dates,
                y=values,
                name=place,
                mode="lines+markers",
                connectgaps=False,
                line={"color": color, "width": 2},
                marker={"color": color, "size": 6},
            )
        )

    figure.update_layout(
        title=title,
        xaxis_title=x_title if x_title is not None else f"Day: {start:%Y-%m-%d} to {end:%Y-%m-%d}",
        yaxis_title=y_title,
        legend_title="Place",
        margin={"l": 60, "r": 30, "t": 60, "b": 90},
    )
    figure.update_xaxes(
        type="date",
        range=[start.isoformat(), (end + pd.Timedelta(days=1)).isoformat()],
        tickmode="array",
        tickvals=tick_dates,
        ticktext=[day.strftime("%Y-%m-%d") for day in tick_dates],
        ticks="outside",
        tickangle=-35,
        showgrid=True,
        gridcolor="#d9d9d9",
    )
    return figure


def add_trend_line(figure: go.Figure, line: pd.Series, label: str, color: str = "black") -> go.Figure:
    """Draw a straight trend line on top of a figure, and thin the data lines under it."""
    figure.update_traces(line={"width": 1}, marker={"size": 3}, opacity=0.6)
    figure.add_trace(
        go.Scatter(
            x=line.index,
            y=line.to_numpy(),
            name=label,
            mode="lines",
            line={"color": color, "width": 3},
            hoverinfo="skip",
        )
    )
    return figure