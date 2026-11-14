"""The climate variables the project offers, and how to talk about each one.

To add a variable, add an entry here. `parameter` is its name in the NASA POWER
monthly API; everything else is wording for the interface.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Variable:
    parameter: str   # name in the NASA POWER API
    label: str       # name shown to the user
    unit: str        # unit shown to the user
    how: str         # how the region's grid cells become one value: "max" or "mean"
    title: str       # plot title
    subject: str     # start of the summary sentence
    increase: str    # verb for an upward trend
    decrease: str    # verb for a downward trend
    note: str        # what one monthly value is


VARIABLES = {
    "t2m": Variable(
        parameter="T2M", label="Average temperature", unit="°C", how="max",
        title="Temperature of the warmest grid cell, compared with normal",
        subject="the warmest part of this region", increase="warmed", decrease="cooled",
        note="Each month shows the monthly average temperature of the warmest NASA grid cell in the region",
    ),
    "t2m_max": Variable(
        parameter="T2M_MAX", label="Maximum temperature", unit="°C", how="max",
        title="Highest temperature of the month, compared with normal",
        subject="the highest temperature reached in this region", increase="rose", decrease="fell",
        note="Each month shows the highest temperature reached that month in any NASA grid cell of the region",
    ),
    "precip": Variable(
        parameter="PRECTOTCORR", label="Precipitation", unit="mm/day", how="mean",
        title="Precipitation, compared with normal",
        subject="precipitation in this region", increase="increased", decrease="decreased",
        note="Each month shows the average precipitation over the NASA grid cells of the region",
    ),
}
DEFAULT = "t2m"


def get(name: str) -> Variable:
    """The variable with this key, or a ValueError listing the valid keys."""
    try:
        return VARIABLES[name]
    except KeyError:
        raise ValueError(f"Unknown variable {name!r}; choose one of {', '.join(VARIABLES)}.") from None
