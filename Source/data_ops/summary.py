"""Read-only dataframe summary helpers."""

import numpy as np
import pandas as pd

from Source.shared.display_format import format_display_value

from .models import DataSummary


def summarize_dataframe(dataframe: pd.DataFrame, include_details: bool = True) -> DataSummary:
    """Return overview text, engineering statistics, and correlations for one dataframe."""

    row_count, col_count = dataframe.shape
    missing_by_col = dataframe.isna().sum()
    total_missing = int(missing_by_col.sum())
    numeric_columns = list(dataframe.select_dtypes(include="number").columns)
    datetime_columns = [
        column for column in dataframe.columns if pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]

    info_lines = [f"{row_count} rows | {col_count} cols | {len(numeric_columns)} num | {len(datetime_columns)} dt | {total_missing} missing"]

    time_range_text = ""
    if datetime_columns:
        time_ranges: list[str] = []
        for column in datetime_columns:
            valid_values = dataframe[column].dropna()
            if valid_values.empty:
                time_ranges.append(f"{column}:n/a")
            else:
                time_ranges.append(
                    f"{column}:{format_display_value(valid_values.min())}->{format_display_value(valid_values.max())}"
                )
        time_range_text = " | ".join(time_ranges)
        info_lines.append("Time " + time_range_text)

    missing_columns = [f"{column}:{int(missing_by_col[column])}" for column in dataframe.columns if missing_by_col[column] > 0]
    missing_columns_text = ""
    if missing_columns:
        missing_columns_text = ", ".join(missing_columns)
        info_lines.append("Missing " + missing_columns_text)

    statistics_frame = build_statistics_frame(dataframe) if include_details else pd.DataFrame()
    correlation_frame = build_correlation_frame(dataframe) if include_details else pd.DataFrame()

    return DataSummary(
        overview_text="\n".join(info_lines),
        row_count=row_count,
        column_count=col_count,
        numeric_column_count=len(numeric_columns),
        datetime_column_count=len(datetime_columns),
        total_missing_count=total_missing,
        time_range_text=time_range_text,
        missing_columns_text=missing_columns_text,
        statistics_frame=statistics_frame,
        correlation_frame=correlation_frame,
    )


def build_statistics_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Build engineering-oriented summary statistics for numeric columns."""

    numeric_frame = dataframe.select_dtypes(include="number")
    stats_columns = ["count", "missing", "min", "max", "mean", "std", "rms", "peak_to_peak"]
    if numeric_frame.empty:
        return pd.DataFrame(columns=stats_columns)

    clean_frame = numeric_frame.apply(pd.to_numeric, errors="coerce")
    missing_counts = clean_frame.isna().sum()
    desc = clean_frame.describe()  # single pass: count, mean, std, min, 25%, 50%, 75%, max
    rms_values = np.sqrt((clean_frame ** 2).mean())  # vectorised; .mean() skips NaN

    statistics_rows: list[dict[str, float | int | str]] = []
    for column in clean_frame.columns:
        col_desc = desc[column]
        n = int(col_desc["count"])
        if n == 0:
            statistics_rows.append(
                {
                    "column": column,
                    "count": 0,
                    "missing": int(missing_counts[column]),
                    "min": np.nan,
                    "max": np.nan,
                    "mean": np.nan,
                    "std": np.nan,
                    "rms": np.nan,
                    "peak_to_peak": np.nan,
                }
            )
            continue

        col_min = float(col_desc["min"])
        col_max = float(col_desc["max"])
        statistics_rows.append(
            {
                "column": column,
                "count": n,
                "missing": int(missing_counts[column]),
                "min": col_min,
                "max": col_max,
                "mean": float(col_desc["mean"]),
                "std": float(col_desc["std"]) if n > 1 else 0.0,
                "rms": float(rms_values[column]),
                "peak_to_peak": col_max - col_min,
            }
        )

    return pd.DataFrame(statistics_rows).set_index("column")


def build_correlation_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return the correlation matrix for numeric columns when available."""

    numeric_frame = dataframe.select_dtypes(include="number")
    if numeric_frame.shape[1] < 2:
        return pd.DataFrame()
    return numeric_frame.corr(numeric_only=True)
