"""Derived signal and filtering operations."""

import numpy as np
import pandas as pd

from .filtering import resolve_filtered_column_name


def add_derived_column(
    dataframe: pd.DataFrame,
    operation: str,
    source_column: str,
    new_column: str,
    second_column: str | None = None,
    window_size: int = 5,
) -> pd.DataFrame:
    """Create a derived signal column on a copy of the dataframe."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")
    if not new_column.strip():
        raise ValueError("Provide a name for the new column")

    working_frame = dataframe.copy()
    source_series = pd.to_numeric(working_frame[source_column], errors="coerce")

    if operation == "delta":
        derived_series = source_series.diff()
    elif operation == "ratio":
        if second_column not in working_frame.columns:
            raise KeyError("Select a valid denominator column")
        denominator = pd.to_numeric(working_frame[second_column], errors="coerce").replace(0, np.nan)
        derived_series = source_series / denominator
    elif operation == "rolling_mean":
        normalized_window = max(1, int(window_size))
        derived_series = source_series.rolling(window=normalized_window, min_periods=1).mean()
    elif operation == "derivative":
        reference_series = _get_reference_series(working_frame, second_column)
        derived_series = source_series.diff() / reference_series.diff().replace(0, np.nan)
    elif operation == "normalized":
        mean_value = source_series.mean()
        std_value = source_series.std(ddof=1)
        if pd.isna(std_value) or std_value == 0:
            derived_series = source_series - mean_value
        else:
            derived_series = (source_series - mean_value) / std_value
    else:
        raise ValueError(f"Unsupported operation: {operation}")

    working_frame[new_column.strip()] = derived_series
    return working_frame


def apply_signal_filter(
    dataframe: pd.DataFrame,
    source_column: str,
    operation: str,
    new_column: str,
    window_size: int = 5,
    alpha: float = 0.2,
) -> pd.DataFrame:
    """Create a filtered signal column on a copy of the dataframe."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")
    resolved_column_name = resolve_filtered_column_name(source_column, new_column)

    numeric_series = pd.to_numeric(dataframe[source_column], errors="coerce")
    normalized_window = max(1, int(window_size))
    normalized_alpha = float(alpha)
    if not 0 < normalized_alpha <= 1:
        raise ValueError("Alpha must be between 0 and 1")

    if operation == "moving_average":
        filtered_series = numeric_series.rolling(window=normalized_window, min_periods=1, center=True).mean()
    elif operation == "median":
        filtered_series = numeric_series.rolling(window=normalized_window, min_periods=1, center=True).median()
    elif operation == "exponential_smoothing":
        filtered_series = numeric_series.ewm(alpha=normalized_alpha, adjust=False, min_periods=1).mean()
    elif operation == "high_pass":
        low_pass = numeric_series.rolling(window=normalized_window, min_periods=1, center=True).mean()
        filtered_series = numeric_series - low_pass
    else:
        raise ValueError(f"Unsupported signal filter operation: {operation}")

    working_frame = dataframe.copy()
    working_frame[resolved_column_name] = filtered_series
    return working_frame


def _get_reference_series(dataframe: pd.DataFrame, reference_column: str | None) -> pd.Series:
    if reference_column is None or reference_column == "Index":
        return pd.Series(np.arange(len(dataframe), dtype=float), index=dataframe.index)

    if reference_column not in dataframe.columns:
        raise KeyError(f"Unknown reference column: {reference_column}")

    reference = dataframe[reference_column]
    if pd.api.types.is_datetime64_any_dtype(reference):
        timestamps = pd.to_datetime(reference, errors="coerce")
        return pd.Series(timestamps.astype("int64") / 1_000_000_000, index=dataframe.index)
    return pd.to_numeric(reference, errors="coerce")
