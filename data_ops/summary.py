"""Read-only dataframe summary helpers."""

import numpy as np
import pandas as pd

from display_format import format_display_value

from .models import DataSummary


def summarize_dataframe(dataframe: pd.DataFrame) -> DataSummary:
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

    return DataSummary(
        overview_text="\n".join(info_lines),
        row_count=row_count,
        column_count=col_count,
        numeric_column_count=len(numeric_columns),
        datetime_column_count=len(datetime_columns),
        total_missing_count=total_missing,
        time_range_text=time_range_text,
        missing_columns_text=missing_columns_text,
        statistics_frame=build_statistics_frame(dataframe),
        correlation_frame=build_correlation_frame(dataframe),
    )


def build_statistics_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Build engineering-oriented summary statistics for numeric columns."""

    numeric_frame = dataframe.select_dtypes(include="number")
    stats_columns = ["count", "missing", "min", "max", "mean", "std", "rms", "peak_to_peak"]
    if numeric_frame.empty:
        return pd.DataFrame(columns=stats_columns)

    statistics_rows: list[dict[str, float | int | str]] = []
    for column in numeric_frame.columns:
        numeric_series = pd.to_numeric(numeric_frame[column], errors="coerce")
        clean_series = numeric_series.dropna()
        if clean_series.empty:
            statistics_rows.append(
                {
                    "column": column,
                    "count": 0,
                    "missing": int(numeric_series.isna().sum()),
                    "min": np.nan,
                    "max": np.nan,
                    "mean": np.nan,
                    "std": np.nan,
                    "rms": np.nan,
                    "peak_to_peak": np.nan,
                }
            )
            continue

        values = clean_series.to_numpy(dtype=float, copy=False)
        statistics_rows.append(
            {
                "column": column,
                "count": int(clean_series.count()),
                "missing": int(numeric_series.isna().sum()),
                "min": float(clean_series.min()),
                "max": float(clean_series.max()),
                "mean": float(clean_series.mean()),
                "std": float(clean_series.std(ddof=1)) if len(clean_series) > 1 else 0.0,
                "rms": float(np.sqrt(np.mean(np.square(values)))),
                "peak_to_peak": float(clean_series.max() - clean_series.min()),
            }
        )

    return pd.DataFrame(statistics_rows).set_index("column")


def build_correlation_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return the correlation matrix for numeric columns when available."""

    numeric_frame = dataframe.select_dtypes(include="number")
    if numeric_frame.shape[1] < 2:
        return pd.DataFrame()
    return numeric_frame.corr(numeric_only=True)
