"""Read-only dataframe summary helpers."""

import numpy as np
import pandas as pd

from .models import DataSummary


def summarize_dataframe(dataframe: pd.DataFrame, include_details: bool = True) -> DataSummary:
    """Return structured summary data, engineering statistics, and correlations for one dataframe."""

    row_count, col_count = dataframe.shape
    missing_by_col = pd.Series({
        column: int(dataframe[column].isna().sum()) for column in dataframe.columns
    }, dtype="int64")
    total_missing = int(missing_by_col.sum())
    numeric_columns = list(dataframe.select_dtypes(include="number").columns)
    datetime_columns = [
        column for column in dataframe.columns if pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ]

    time_ranges: list[tuple[str, object | None, object | None]] = []
    if datetime_columns:
        for column in datetime_columns:
            values = dataframe[column]
            if values.notna().sum() == 0:
                time_ranges.append((str(column), None, None))
            else:
                time_ranges.append((str(column), values.min(), values.max()))

    missing_columns = tuple(
        (str(column), int(missing_by_col[column]))
        for column in dataframe.columns
        if missing_by_col[column] > 0
    )

    statistics_frame = build_statistics_frame(dataframe) if include_details else pd.DataFrame()
    correlation_frame = build_correlation_frame(dataframe) if include_details else pd.DataFrame()

    return DataSummary(
        row_count=row_count,
        column_count=col_count,
        numeric_column_count=len(numeric_columns),
        datetime_column_count=len(datetime_columns),
        total_missing_count=total_missing,
        time_ranges=tuple(time_ranges),
        missing_by_column=missing_columns,
        statistics_frame=statistics_frame,
        correlation_frame=correlation_frame,
    )


def build_statistics_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Build engineering-oriented summary statistics for numeric columns."""

    numeric_frame = dataframe.select_dtypes(include="number")
    stats_columns = ["count", "missing", "min", "max", "mean", "std", "rms", "peak_to_peak"]
    if numeric_frame.empty:
        return pd.DataFrame(columns=stats_columns)

    statistics_rows: list[dict[str, float | int | str]] = []
    for column in numeric_frame.columns:
        values = pd.to_numeric(numeric_frame[column], errors="coerce")
        n = int(values.count())
        missing = len(values) - n
        if n == 0:
            statistics_rows.append(
                {
                    "column": column,
                    "count": 0,
                    "missing": missing,
                    "min": np.nan,
                    "max": np.nan,
                    "mean": np.nan,
                    "std": np.nan,
                    "rms": np.nan,
                    "peak_to_peak": np.nan,
                }
            )
            continue

        col_min = float(values.min())
        col_max = float(values.max())
        statistics_rows.append(
            {
                "column": column,
                "count": n,
                "missing": missing,
                "min": col_min,
                "max": col_max,
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)) if n > 1 else 0.0,
                "rms": float(np.sqrt((values ** 2).mean())),
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
