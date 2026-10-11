"""Resolution-independent conversion of reference axes to seconds."""

import pandas as pd


def reference_axis_seconds(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        timestamps = pd.to_datetime(series, errors="coerce")
        epoch = pd.Timestamp("1970-01-01", tz=timestamps.dt.tz)
        return (timestamps - epoch).dt.total_seconds()
    return pd.to_numeric(series, errors="coerce")
