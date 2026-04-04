"""Rudimentary cycle-analysis helpers."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


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


def compute_cycle_analysis_from_ranges(
    dataframe: pd.DataFrame,
    source_column: str,
    cycle_ranges: list[tuple[int, int]],
    method: str,
    reference_column: str,
) -> CycleAnalysisResult:
    """Compute cycle metrics from explicit half-open row ranges."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")
    if not cycle_ranges:
        raise ValueError("No valid cycles available")

    numeric_series = pd.to_numeric(dataframe[source_column], errors="coerce")
    normalized_ranges: list[tuple[int, int]] = []
    cycle_values: list[np.ndarray] = []
    cycle_lengths: list[int] = []
    for start_index, end_index in cycle_ranges:
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

    if not cycle_values:
        raise ValueError("No valid cycles available")

    aligned_length = min(cycle_lengths)
    cycle_matrix = np.vstack([cycle_array[:aligned_length] for cycle_array in cycle_values])
    cycles_frame = pd.DataFrame(cycle_matrix)
    total_used_rows = sum(cycle_lengths)
    dropped_rows = len(dataframe) - total_used_rows

    metrics_frame = pd.DataFrame(
        {
            "cycle": np.arange(1, len(cycle_values) + 1),
            "start": [start_index for start_index, _ in normalized_ranges],
            "end": [end_index for _, end_index in normalized_ranges],
            "length": cycle_lengths,
            "mean": [float(np.nanmean(cycle_array)) for cycle_array in cycle_values],
            "std": [float(np.nanstd(cycle_array, ddof=1)) if cycle_array.size > 1 else 0.0 for cycle_array in cycle_values],
            "min": [float(np.nanmin(cycle_array)) for cycle_array in cycle_values],
            "max": [float(np.nanmax(cycle_array)) for cycle_array in cycle_values],
            "rms": [float(np.sqrt(np.nanmean(cycle_array**2))) for cycle_array in cycle_values],
            "peak_to_peak": [float(np.nanmax(cycle_array) - np.nanmin(cycle_array)) for cycle_array in cycle_values],
        }
    )

    representative_frame = pd.DataFrame(
        {
            "step": np.arange(aligned_length),
            "mean": cycles_frame.mean(axis=0),
            "std": cycles_frame.std(axis=0),
            "min": cycles_frame.min(axis=0),
            "max": cycles_frame.max(axis=0),
        }
    )

    return CycleAnalysisResult(
        source_column=source_column,
        method=method,
        reference_column=reference_column,
        cycle_length=aligned_length,
        cycle_count=len(cycle_values),
        dropped_rows=max(0, int(dropped_rows)),
        metrics_frame=metrics_frame,
        representative_frame=representative_frame,
        cycles_frame=cycles_frame,
        cycle_ranges=normalized_ranges,
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

    reference_series = pd.to_numeric(dataframe[reference_column], errors="coerce")
    above_threshold = reference_series >= float(threshold)
    rising_edges = np.flatnonzero(above_threshold.to_numpy() & ~above_threshold.shift(1, fill_value=False).to_numpy())
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


def compute_fixed_length_cycle_analysis(
    dataframe: pd.DataFrame,
    source_column: str,
    cycle_length: int,
    max_cycles: int | None = None,
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
    )