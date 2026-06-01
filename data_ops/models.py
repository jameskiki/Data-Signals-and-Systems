"""Shared data operation models and constants."""

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


DataFrameMap = Mapping[str, pd.DataFrame]
SIGNAL_FILTER_OPERATIONS = [
    "moving_average", "median", "exponential_smoothing", "high_pass",
    "butterworth_lowpass", "butterworth_highpass", "butterworth_bandpass",
]


@dataclass(frozen=True)
class DataSummary:
    """Computed overview, statistics, and correlations for one dataframe."""

    overview_text: str
    row_count: int
    column_count: int
    numeric_column_count: int
    datetime_column_count: int
    total_missing_count: int
    time_range_text: str
    missing_columns_text: str
    statistics_frame: pd.DataFrame
    correlation_frame: pd.DataFrame
