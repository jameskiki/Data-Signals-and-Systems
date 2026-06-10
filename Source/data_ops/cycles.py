"""Rudimentary cycle-analysis helpers."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.signal import find_peaks


@dataclass(frozen=True)
class CycleAnalysisResult:
    """Computed fixed-length cycle analysis for one numeric column."""

    source_column: str
    method: str
    reference_column: str
    cycle_length: int
    cycle_count: int
    dropped_rows: int
    metrics_frame: pd.DataFrame
    representative_frame: pd.DataFrame
    cycles_frame: pd.DataFrame
    cycle_ranges: list[tuple[int, int]]
    time_column: str | None = None


def compute_cycle_analysis_from_ranges(
    dataframe: pd.DataFrame,
    source_column: str,
    cycle_ranges: list[tuple[int, int]],
    method: str,
    reference_column: str,
    time_column: str | None = None,
) -> CycleAnalysisResult:
    """Compute cycle metrics from explicit half-open row ranges."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")
    if time_column is not None and time_column not in dataframe.columns:
        raise KeyError(f"Unknown time column: {time_column}")
    if not cycle_ranges:
        raise ValueError("No valid cycles available")

    numeric_series = pd.to_numeric(dataframe[source_column], errors="coerce")
    duration_values = _compute_cycle_duration_seconds(dataframe, cycle_ranges=cycle_ranges, time_column=time_column)
    normalized_ranges: list[tuple[int, int]] = []
    cycle_values: list[np.ndarray] = []
    cycle_lengths: list[int] = []
    cycle_durations: list[float] = []
    for cycle_duration, (start_index, end_index) in zip(duration_values, cycle_ranges):
        start_index = int(start_index)
        end_index = int(end_index)
        if end_index <= start_index:
            continue
        cycle_array = numeric_series.iloc[start_index:end_index].to_numpy(dtype=float)
        if cycle_array.size < 2:
            continue
        normalized_ranges.append((start_index, end_index))
        cycle_values.append(cycle_array)
        cycle_lengths.append(int(cycle_array.size))
        cycle_durations.append(cycle_duration)

    if not cycle_values:
        raise ValueError("No valid cycles available")

    representative_length = max(cycle_lengths)
    cycle_matrix = np.full((len(cycle_values), representative_length), np.nan, dtype=float)
    for cycle_index, cycle_array in enumerate(cycle_values):
        cycle_matrix[cycle_index, : cycle_array.size] = cycle_array
    cycles_frame = pd.DataFrame(cycle_matrix)
    total_used_rows = sum(cycle_lengths)
    dropped_rows = len(dataframe) - total_used_rows
    support_count = cycles_frame.notna().sum(axis=0).astype(int)

    cycle_lengths_arr = np.array(cycle_lengths)
    col_means = np.nanmean(cycle_matrix, axis=1)
    col_stds = np.where(cycle_lengths_arr > 1, np.nanstd(cycle_matrix, axis=1, ddof=1), 0.0)
    col_mins = np.nanmin(cycle_matrix, axis=1)
    col_maxs = np.nanmax(cycle_matrix, axis=1)
    col_rms = np.sqrt(np.nanmean(cycle_matrix ** 2, axis=1))

    metrics_frame = pd.DataFrame(
        {
            "cycle": np.arange(1, len(cycle_values) + 1),
            "start": [start_index for start_index, _ in normalized_ranges],
            "end": [end_index for _, end_index in normalized_ranges],
            "length": cycle_lengths,
            "duration_seconds": cycle_durations,
            "mean": col_means,
            "std": col_stds,
            "min": col_mins,
            "max": col_maxs,
            "rms": col_rms,
            "peak_to_peak": col_maxs - col_mins,
        }
    )

    representative_frame = pd.DataFrame(
        {
            "step": np.arange(representative_length),
            "mean": cycles_frame.mean(axis=0),
            "std": cycles_frame.std(axis=0),
            "min": cycles_frame.min(axis=0),
            "max": cycles_frame.max(axis=0),
            "support_count": support_count.to_numpy(),
        }
    )

    return CycleAnalysisResult(
        source_column=source_column,
        method=method,
        reference_column=reference_column,
        cycle_length=representative_length,
        cycle_count=len(cycle_values),
        dropped_rows=max(0, int(dropped_rows)),
        metrics_frame=metrics_frame,
        representative_frame=representative_frame,
        cycles_frame=cycles_frame,
        cycle_ranges=normalized_ranges,
        time_column=time_column,
    )


def detect_rising_edge_cycle_ranges(
    dataframe: pd.DataFrame,
    reference_column: str,
    threshold: float,
    min_cycle_length: int,
    max_cycles: int | None = None,
) -> list[tuple[int, int]]:
    """Detect cycles using rising threshold crossings on a reference signal."""

    if reference_column not in dataframe.columns:
        raise KeyError(f"Unknown reference column: {reference_column}")
    if min_cycle_length <= 1:
        raise ValueError("Minimum cycle length must be greater than 1")
    if max_cycles is not None and max_cycles <= 0:
        raise ValueError("Maximum cycle count must be positive")

    reference_values = pd.to_numeric(dataframe[reference_column], errors="coerce").to_numpy(dtype=float)
    above = reference_values >= float(threshold)
    rising_edges = np.flatnonzero(above & ~np.concatenate(([False], above[:-1])))
    if rising_edges.size < 2:
        raise ValueError("Need at least two rising-edge crossings to define cycles")

    cycle_ranges: list[tuple[int, int]] = []
    for start_index, end_index in zip(rising_edges[:-1], rising_edges[1:]):
        if int(end_index) - int(start_index) < min_cycle_length:
            continue
        cycle_ranges.append((int(start_index), int(end_index)))
        if max_cycles is not None and len(cycle_ranges) >= max_cycles:
            break

    if not cycle_ranges:
        raise ValueError("No cycles matched the selected rising-edge threshold and minimum length")
    return cycle_ranges


def detect_zero_crossing_cycle_ranges(
    dataframe: pd.DataFrame,
    reference_column: str,
    direction: str = "rising",
    min_cycle_length: int = 2,
    max_cycles: int | None = None,
) -> list[tuple[int, int]]:
    """Detect cycles at zero-crossing points of a reference signal."""

    if reference_column not in dataframe.columns:
        raise KeyError(f"Unknown reference column: {reference_column}")
    if min_cycle_length <= 1:
        raise ValueError("Minimum cycle length must be greater than 1")

    reference_series = pd.to_numeric(dataframe[reference_column], errors="coerce")
    values = reference_series.to_numpy(dtype=float)
    sign_changes = np.diff(np.sign(values))

    if direction == "rising":
        crossings = np.flatnonzero(sign_changes > 0)
    elif direction == "falling":
        crossings = np.flatnonzero(sign_changes < 0)
    else:
        crossings = np.flatnonzero(sign_changes != 0)

    if crossings.size < 2:
        raise ValueError(f"Need at least two {direction} zero crossings to define cycles")

    cycle_ranges: list[tuple[int, int]] = []
    for start_index, end_index in zip(crossings[:-1], crossings[1:]):
        if int(end_index) - int(start_index) < min_cycle_length:
            continue
        cycle_ranges.append((int(start_index), int(end_index)))
        if max_cycles is not None and len(cycle_ranges) >= max_cycles:
            break

    if not cycle_ranges:
        raise ValueError("No cycles matched the selected zero-crossing criteria and minimum length")
    return cycle_ranges


def detect_peak_cycle_ranges(
    dataframe: pd.DataFrame,
    reference_column: str,
    min_cycle_length: int = 2,
    prominence: float = 0.0,
    max_cycles: int | None = None,
) -> list[tuple[int, int]]:
    """Detect cycles between successive peaks of a reference signal."""

    if reference_column not in dataframe.columns:
        raise KeyError(f"Unknown reference column: {reference_column}")
    if min_cycle_length <= 1:
        raise ValueError("Minimum cycle length must be greater than 1")

    reference_series = pd.to_numeric(dataframe[reference_column], errors="coerce")
    values = reference_series.to_numpy(dtype=float)
    peak_kwargs: dict = {"distance": min_cycle_length}
    if prominence > 0:
        peak_kwargs["prominence"] = float(prominence)

    peaks, _ = find_peaks(values, **peak_kwargs)
    if peaks.size < 2:
        raise ValueError("Need at least two peaks to define cycles")

    cycle_ranges: list[tuple[int, int]] = []
    for start_index, end_index in zip(peaks[:-1], peaks[1:]):
        cycle_ranges.append((int(start_index), int(end_index)))
        if max_cycles is not None and len(cycle_ranges) >= max_cycles:
            break

    if not cycle_ranges:
        raise ValueError("No cycles matched the selected peak detection criteria")
    return cycle_ranges


def compute_fixed_length_cycle_analysis(
    dataframe: pd.DataFrame,
    source_column: str,
    cycle_length: int,
    max_cycles: int | None = None,
    time_column: str | None = None,
) -> CycleAnalysisResult:
    """Split one signal into equal-length cycles and compute basic metrics."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")
    if cycle_length <= 1:
        raise ValueError("Cycle length must be greater than 1")
    if max_cycles is not None and max_cycles <= 0:
        raise ValueError("Maximum cycle count must be positive")

    total_rows = len(dataframe)
    available_cycles = total_rows // cycle_length
    if available_cycles < 1:
        raise ValueError(
            f"Need at least {cycle_length} rows to build one cycle from {source_column}; got {total_rows}"
        )

    cycle_count = available_cycles if max_cycles is None else min(available_cycles, max_cycles)
    cycle_ranges = [(cycle_index * cycle_length, (cycle_index + 1) * cycle_length) for cycle_index in range(cycle_count)]
    return compute_cycle_analysis_from_ranges(
        dataframe,
        source_column=source_column,
        cycle_ranges=cycle_ranges,
        method="fixed_length",
        reference_column="Index",
        time_column=time_column,
    )


def rebuild_cycle_analysis_result(
    dataframe: pd.DataFrame,
    base_result: CycleAnalysisResult,
    kept_cycle_indices: list[int],
) -> CycleAnalysisResult:
    """Rebuild a cycle-analysis result from a kept subset of detected cycles."""

    if not kept_cycle_indices:
        raise ValueError("At least one cycle must remain selected")

    normalized_indices = sorted({int(index) for index in kept_cycle_indices})
    if normalized_indices[0] < 0 or normalized_indices[-1] >= len(base_result.cycle_ranges):
        raise IndexError("Cycle index out of range")

    kept_ranges = [base_result.cycle_ranges[index] for index in normalized_indices]
    return compute_cycle_analysis_from_ranges(
        dataframe,
        source_column=base_result.source_column,
        cycle_ranges=kept_ranges,
        method=base_result.method,
        reference_column=base_result.reference_column,
        time_column=base_result.time_column,
    )


def _compute_cycle_duration_seconds(
    dataframe: pd.DataFrame,
    cycle_ranges: list[tuple[int, int]],
    time_column: str | None,
) -> list[float]:
    if time_column is None:
        return [float("nan")] * len(cycle_ranges)

    time_series = dataframe[time_column]
    if pd.api.types.is_datetime64_any_dtype(time_series):
        time_values = pd.to_datetime(time_series, errors="coerce")
        return [_duration_from_datetimes(time_values, start_index, end_index) for start_index, end_index in cycle_ranges]

    numeric_time = pd.to_numeric(time_series, errors="coerce")
    return [_duration_from_numeric(numeric_time, start_index, end_index) for start_index, end_index in cycle_ranges]


def _duration_from_numeric(time_values: pd.Series, start_index: int, end_index: int) -> float:
    if end_index - start_index < 2:
        return float("nan")

    start_value = time_values.iloc[start_index]
    end_value = time_values.iloc[end_index - 1]
    if pd.isna(start_value) or pd.isna(end_value):
        return float("nan")
    return float(end_value - start_value)


def _duration_from_datetimes(time_values: pd.Series, start_index: int, end_index: int) -> float:
    if end_index - start_index < 2:
        return float("nan")

    start_value = time_values.iloc[start_index]
    end_value = time_values.iloc[end_index - 1]
    if pd.isna(start_value) or pd.isna(end_value):
        return float("nan")
    return float((end_value - start_value).total_seconds())