"""Structural dataframe operations."""

from collections.abc import Sequence

import numpy as np
import pandas as pd


def select_dataframe_columns(
    dataframe: pd.DataFrame,
    selected_columns: Sequence[str],
) -> pd.DataFrame:
    """Return a copy containing only the requested columns in the given order."""

    if not selected_columns:
        raise ValueError("Select at least one column")

    missing_columns = [column for column in selected_columns if column not in dataframe.columns]
    if missing_columns:
        raise KeyError(f"Unknown columns: {missing_columns}")

    return dataframe.loc[:, list(selected_columns)].copy()


def drop_dataframe_columns(
    dataframe: pd.DataFrame,
    columns_to_drop: Sequence[str],
) -> pd.DataFrame:
    """Return a copy without the requested columns."""

    if not columns_to_drop:
        raise ValueError("Select at least one column")

    missing_columns = [column for column in columns_to_drop if column not in dataframe.columns]
    if missing_columns:
        raise KeyError(f"Unknown columns: {missing_columns}")

    remaining_columns = [column for column in dataframe.columns if column not in set(columns_to_drop)]
    if not remaining_columns:
        raise ValueError("Dropping these columns would leave an empty dataframe")

    return dataframe.loc[:, remaining_columns].copy()


def slice_dataframe_by_index_range(
    dataframe: pd.DataFrame,
    start_index: int,
    end_index: int,
) -> pd.DataFrame:
    """Return a row slice using a half-open interval [start, end)."""

    normalized_start, normalized_end = normalize_index_range(len(dataframe), start_index, end_index)
    return dataframe.iloc[normalized_start:normalized_end].reset_index(drop=True).copy()


def drop_dataframe_index_range(
    dataframe: pd.DataFrame,
    start_index: int,
    end_index: int,
) -> pd.DataFrame:
    """Return a copy with one half-open row interval [start, end) removed."""

    normalized_start, normalized_end = normalize_index_range(len(dataframe), start_index, end_index)
    kept_frame = pd.concat(
        [dataframe.iloc[:normalized_start], dataframe.iloc[normalized_end:]],
        ignore_index=True,
    )
    if kept_frame.empty:
        raise ValueError("Dropping this row range would leave an empty dataframe")
    return kept_frame.copy()


def split_dataframe_by_index_ranges(
    dataframe: pd.DataFrame,
    ranges: Sequence[tuple[int, int]],
) -> list[tuple[tuple[int, int], pd.DataFrame]]:
    """Split a dataframe into row-index ranges using half-open intervals [start, end)."""

    if not ranges:
        raise ValueError("Provide at least one index range")

    split_frames: list[tuple[tuple[int, int], pd.DataFrame]] = []
    for start_index, end_index in ranges:
        normalized_start, normalized_end = normalize_index_range(len(dataframe), start_index, end_index)
        split_frames.append(
            (
                (normalized_start, normalized_end),
                dataframe.iloc[normalized_start:normalized_end].reset_index(drop=True).copy(),
            )
        )

    return split_frames


def normalize_index_range(row_count: int, start_index: int, end_index: int) -> tuple[int, int]:
    """Validate and normalize one half-open row interval [start, end)."""

    normalized_start = int(start_index)
    normalized_end = int(end_index)
    if normalized_start < 0 or normalized_end < 0:
        raise ValueError("Index ranges must be non-negative")
    if normalized_end <= normalized_start:
        raise ValueError(f"Invalid range {normalized_start}:{normalized_end}; end must be greater than start")
    if normalized_start >= row_count:
        raise ValueError(f"Range start {normalized_start} exceeds dataset length {row_count}")
    return normalized_start, min(normalized_end, row_count)


def resample_to_uniform(
    dataframe: pd.DataFrame,
    time_column: str,
    target_spacing: float,
) -> pd.DataFrame:
    """Resample all numeric columns to a uniform time grid via linear interpolation."""

    if time_column not in dataframe.columns:
        raise KeyError(f"Unknown time column: {time_column}")
    if target_spacing <= 0:
        raise ValueError("Target spacing must be greater than zero")

    time_series = pd.to_numeric(dataframe[time_column], errors="coerce")
    if pd.api.types.is_datetime64_any_dtype(dataframe[time_column]):
        time_series = pd.to_datetime(dataframe[time_column], errors="coerce").astype("int64") / 1e9

    valid_mask = time_series.notna()
    t_original = time_series.loc[valid_mask].to_numpy(dtype=float)
    if t_original.size < 2:
        raise ValueError("Need at least two valid time samples for resampling")

    t_uniform = np.arange(t_original[0], t_original[-1], target_spacing)
    if t_uniform.size < 2:
        raise ValueError("Target spacing is too large for the time range")

    result_data: dict[str, np.ndarray] = {time_column: t_uniform}
    for column in dataframe.columns:
        if column == time_column:
            continue
        col_numeric = pd.to_numeric(dataframe[column], errors="coerce")
        if col_numeric.isna().all():
            result_data[column] = np.full(t_uniform.size, np.nan)
            continue
        col_valid = col_numeric.loc[valid_mask].to_numpy(dtype=float)
        result_data[column] = np.interp(t_uniform, t_original, col_valid)

    return pd.DataFrame(result_data)
