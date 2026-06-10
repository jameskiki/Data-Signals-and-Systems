"""Column filtering and row-subsetting helpers."""

import pandas as pd


def resolve_filtered_column_name(source_column: str, new_column: str) -> str:
    """Return the user-provided name or a default filtered-column suffix."""

    trimmed_name = new_column.strip()
    if trimmed_name:
        return trimmed_name
    if source_column.endswith("_filt"):
        return source_column
    return f"{source_column}_filt"


def apply_simple_filter(
    dataframe: pd.DataFrame,
    source_column: str,
    new_column: str,
    minimum_value: str = "",
    maximum_value: str = "",
    keep_missing: bool = False,
) -> pd.DataFrame:
    """Create a filtered copy of one column while keeping the full dataframe intact."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")
    resolved_column_name = resolve_filtered_column_name(source_column, new_column)

    series = dataframe[source_column]
    mask = _build_filter_mask(series, minimum_value, maximum_value, keep_missing)

    working_frame = dataframe.copy()
    working_frame[resolved_column_name] = series.where(mask)
    return working_frame


def subset_dataframe_rows(
    dataframe: pd.DataFrame,
    source_column: str,
    minimum_value: str = "",
    maximum_value: str = "",
    keep_missing: bool = False,
) -> pd.DataFrame:
    """Return a row subset based on one column range condition."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")

    series = dataframe[source_column]
    mask = _build_filter_mask(series, minimum_value, maximum_value, keep_missing)
    return dataframe.loc[mask].reset_index(drop=True)


def _build_range_mask(series: pd.Series, minimum_value: str, maximum_value: str) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return _build_datetime_range_mask(series, minimum_value, maximum_value)
    if pd.api.types.is_numeric_dtype(series):
        return _build_numeric_range_mask(series, minimum_value, maximum_value)
    return _build_text_range_mask(series, minimum_value, maximum_value)


def _build_filter_mask(
    series: pd.Series,
    minimum_value: str,
    maximum_value: str,
    keep_missing: bool,
) -> pd.Series:
    mask = pd.Series(True, index=series.index)
    if not (minimum_value.strip() or maximum_value.strip()):
        raise ValueError("Provide at least a minimum or maximum value")

    range_mask = _build_range_mask(series, minimum_value, maximum_value)
    if keep_missing:
        range_mask = range_mask | series.isna()
    mask &= range_mask

    return mask


def _build_numeric_range_mask(series: pd.Series, minimum_value: str, maximum_value: str) -> pd.Series:
    numeric_series = pd.to_numeric(series, errors="coerce")
    mask = pd.Series(True, index=series.index)
    if minimum_value.strip():
        mask &= numeric_series >= float(minimum_value)
    if maximum_value.strip():
        mask &= numeric_series <= float(maximum_value)
    return mask.fillna(False)


def _build_datetime_range_mask(series: pd.Series, minimum_value: str, maximum_value: str) -> pd.Series:
    datetime_series = pd.to_datetime(series, errors="coerce")
    mask = pd.Series(True, index=series.index)
    if minimum_value.strip():
        mask &= datetime_series >= pd.to_datetime(minimum_value)
    if maximum_value.strip():
        mask &= datetime_series <= pd.to_datetime(maximum_value)
    return mask.fillna(False)


def _build_text_range_mask(series: pd.Series, minimum_value: str, maximum_value: str) -> pd.Series:
    text_series = series.astype(str)
    mask = pd.Series(True, index=series.index)
    if minimum_value.strip():
        mask &= text_series >= minimum_value.strip()
    if maximum_value.strip():
        mask &= text_series <= maximum_value.strip()
    return mask.fillna(False)
