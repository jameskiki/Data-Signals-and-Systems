"""Derived signal and filtering operations."""

import numpy as np
import pandas as pd
from scipy.signal import butter, hilbert, sosfiltfilt

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

    source_series = pd.to_numeric(dataframe[source_column], errors="coerce")

    if operation == "delta":
        derived_series = source_series.diff()
    elif operation == "ratio":
        if second_column not in dataframe.columns:
            raise KeyError("Select a valid denominator column")
        denominator = pd.to_numeric(dataframe[second_column], errors="coerce").replace(0, np.nan)
        derived_series = source_series / denominator
    elif operation == "rolling_mean":
        normalized_window = max(1, int(window_size))
        derived_series = source_series.rolling(window=normalized_window, min_periods=1).mean()
    elif operation == "derivative":
        reference_series = _get_reference_series(dataframe, second_column)
        derived_series = source_series.diff() / reference_series.diff().replace(0, np.nan)
    elif operation == "normalized":
        mean_value = source_series.mean()
        std_value = source_series.std(ddof=1)
        if pd.isna(std_value) or std_value == 0:
            derived_series = source_series - mean_value
        else:
            derived_series = (source_series - mean_value) / std_value
    elif operation == "detrend":
        poly_order = max(1, min(int(window_size), 3))
        valid_mask = source_series.notna()
        x_values = np.arange(len(source_series), dtype=float)
        coeffs = np.polyfit(x_values[valid_mask], source_series[valid_mask].to_numpy(dtype=float), poly_order)
        trend = np.polyval(coeffs, x_values)
        derived_series = source_series - pd.Series(trend, index=source_series.index)
    elif operation == "integrate":
        reference_series = _get_reference_series(dataframe, second_column)
        dt = reference_series.diff()
        integrand = source_series * dt
        derived_series = integrand.cumsum().fillna(0.0)
    elif operation == "rms_envelope":
        normalized_window = max(1, int(window_size))
        derived_series = (source_series ** 2).rolling(window=normalized_window, min_periods=1, center=True).mean().pow(0.5)
    elif operation == "hilbert_envelope":
        valid_mask = source_series.notna()
        values = source_series.loc[valid_mask].to_numpy(dtype=float)
        analytic = hilbert(values)
        envelope = np.abs(analytic)
        derived_series = source_series.copy()
        derived_series.loc[valid_mask] = envelope
    else:
        raise ValueError(f"Unsupported operation: {operation}")

    result = dataframe.copy()
    result[new_column.strip()] = derived_series
    return result


def apply_signal_filter(
    dataframe: pd.DataFrame,
    source_column: str,
    operation: str,
    new_column: str,
    window_size: int = 5,
    alpha: float = 0.2,
    cutoff_hz: float = 1.0,
    sample_spacing: float = 0.0,
    filter_order: int = 4,
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
    elif operation in ("butterworth_lowpass", "butterworth_highpass", "butterworth_bandpass"):
        filtered_series = _apply_butterworth(
            numeric_series, operation, cutoff_hz, sample_spacing, filter_order,
        )
    else:
        raise ValueError(f"Unsupported signal filter operation: {operation}")

    working_frame = dataframe.copy()
    working_frame[resolved_column_name] = filtered_series
    return working_frame


def _apply_butterworth(
    series: pd.Series,
    operation: str,
    cutoff_hz: float,
    sample_spacing: float,
    order: int,
) -> pd.Series:
    """Apply a zero-phase Butterworth filter to a numeric series."""

    if sample_spacing <= 0:
        raise ValueError("Sample spacing must be greater than zero for Butterworth filters")

    fs = 1.0 / sample_spacing
    nyquist = 0.5 * fs
    clamped_order = max(1, min(int(order), 10))

    btype_map = {
        "butterworth_lowpass": "low",
        "butterworth_highpass": "high",
        "butterworth_bandpass": "band",
    }
    btype = btype_map[operation]

    if btype == "band":
        if not isinstance(cutoff_hz, (list, tuple)) or len(cutoff_hz) != 2:
            raise ValueError("Band-pass requires two cutoff frequencies as [low, high]")
        wn = [float(cutoff_hz[0]) / nyquist, float(cutoff_hz[1]) / nyquist]
        if not (0 < wn[0] < wn[1] < 1):
            raise ValueError("Band-pass cutoffs must satisfy 0 < f_low < f_high < Nyquist")
    else:
        wn = float(cutoff_hz) / nyquist
        if not 0 < wn < 1:
            raise ValueError(
                f"Cutoff frequency {cutoff_hz} Hz is outside valid range (0, {nyquist}) Hz for fs={fs} Hz"
            )

    sos = butter(clamped_order, wn, btype=btype, output="sos")

    valid_mask = series.notna()
    values = series.loc[valid_mask].to_numpy(dtype=float)
    if values.size < 3 * clamped_order + 1:
        raise ValueError(
            f"Need at least {3 * clamped_order + 1} valid samples for a Butterworth filter of order {clamped_order}"
        )

    filtered_values = sosfiltfilt(sos, values)
    result = series.copy()
    result.loc[valid_mask] = filtered_values
    return result


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
