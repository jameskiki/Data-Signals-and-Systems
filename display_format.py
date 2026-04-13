"""Shared display-format helpers for consistent numeric rendering."""

from __future__ import annotations

import math
from numbers import Real

from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import matplotlib.dates as mdates

DISPLAY_DECIMALS = 3


def format_display_number(value: Real, decimals: int = DISPLAY_DECIMALS) -> str:
    """Format one numeric value with at most the configured decimal precision."""

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return str(numeric_value)
    return f"{numeric_value:.{decimals}f}".rstrip("0").rstrip(".")


def format_display_percent(value: Real, decimals: int = DISPLAY_DECIMALS) -> str:
    """Format a ratio as a percentage with at most the configured decimal precision."""

    return f"{format_display_number(float(value) * 100.0, decimals)}%"


def format_display_value(value: object, decimals: int = DISPLAY_DECIMALS) -> str:
    """Format one display value, handling timestamps, missing values, and numbers."""

    if value is None or pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.isoformat(sep=" ")
    if isinstance(value, (np.integer, int)) and not isinstance(value, (bool, np.bool_)):
        return str(int(value))
    if isinstance(value, (np.floating, float)) and not isinstance(value, (bool, np.bool_)):
        return format_display_number(float(value), decimals)
    return str(value)


def apply_numeric_axis_format(axis, *, format_x: bool = False, format_y: bool = True) -> None:
    """Apply 3-decimal tick formatting to numeric axes only."""

    formatter = FuncFormatter(lambda tick_value, _position: format_display_number(tick_value))
    if format_x and _axis_looks_numeric(axis, "x"):
        axis.xaxis.set_major_formatter(formatter)
    elif format_x:
        axis.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M:%S'))
    if format_y and _axis_looks_numeric(axis, "y"):
        axis.yaxis.set_major_formatter(formatter)


def _axis_looks_numeric(axis, dimension: str) -> bool:
    # Check axis label for date/time keywords
    label = axis.get_xlabel() if dimension == "x" else axis.get_ylabel()
    label_lower = label.lower()
    if any(kw in label_lower for kw in ("date", "timestamp")):
        return False

    for line in axis.lines:
        raw_values = line.get_xdata(orig=False) if dimension == "x" else line.get_ydata(orig=False)
        values = np.asarray(raw_values)
        if values.size == 0:
            continue
        if np.issubdtype(values.dtype, np.datetime64):
            return False
        if np.issubdtype(values.dtype, np.number):
            return True
        coerced = pd.to_numeric(pd.Series(values), errors="coerce")
        if coerced.notna().any() and coerced.notna().all():
            return True
    return False