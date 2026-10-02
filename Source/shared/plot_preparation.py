"""Prepare analysis results for calculation-free shared plot renderers."""

from __future__ import annotations

import numpy as np

from Source.shared.plot_options import CyclePlotData, FrequencyPlotValues, SpectrogramPlotData


def prepare_frequency_plot_values(result, *, unwrap_phase: bool = False) -> FrequencyPlotValues:
    """Convert a frequency result into display-ready values."""

    frequencies = result.frequencies[1:] if result.frequencies.size > 1 else result.frequencies
    magnitudes = result.amplitudes[1:] if result.amplitudes.size > 1 else result.amplitudes
    phase_degrees = None
    if result.phase is not None and result.phase.size > 0:
        phase_radians = result.phase[1:] if result.phase.size > 1 else result.phase
        if unwrap_phase:
            phase_radians = np.unwrap(phase_radians)
        phase_degrees = np.degrees(phase_radians)
    return FrequencyPlotValues(
        frequencies=frequencies,
        magnitudes=magnitudes,
        phase_degrees=phase_degrees,
        wrapped_phase=phase_degrees is not None and not unwrap_phase,
    )


def prepare_spectrogram_plot_data(result) -> SpectrogramPlotData:
    """Convert a spectrogram result into display-ready dB values and labels."""

    return SpectrogramPlotData(
        times=result.times,
        frequencies=result.frequencies,
        power_db=10.0 * np.log10(result.power.T + 1e-20),
        title=f"Spectrogram - {result.source_column}",
        x_label="Time [s]" if result.reference_column else "Sample",
    )


def prepare_cycle_plot_data(result, selected_indices: list[int] | None = None) -> CyclePlotData:
    """Convert a cycle-analysis result into display-ready plot values."""

    def _finite_column_means(values: np.ndarray) -> np.ndarray:
        finite_counts = np.sum(np.isfinite(values), axis=0)
        return np.divide(
            np.nansum(values, axis=0),
            finite_counts,
            out=np.full(values.shape[1], np.nan, dtype=float),
            where=finite_counts > 0,
        )

    all_cycles = result.cycles_frame.to_numpy(dtype=float)
    resolved_indices = selected_indices or list(range(len(all_cycles)))
    selected_cycles = result.cycles_frame.iloc[resolved_indices].to_numpy(dtype=float)
    representative = result.representative_frame
    metrics = result.metrics_frame

    early_mean_values = None
    late_mean_values = None
    if len(all_cycles) >= 4:
        half = max(1, len(all_cycles) // 2)
        early_mean_values = _finite_column_means(all_cycles[:half])
        late_mean_values = _finite_column_means(all_cycles[-half:])

    support_values = None
    if "support_count" in representative.columns:
        candidate_support = representative["support_count"].to_numpy(dtype=float)
        if np.nanmin(candidate_support) < np.nanmax(candidate_support):
            support_values = candidate_support

    has_durations = "duration_seconds" in metrics.columns and metrics["duration_seconds"].notna().any()
    return CyclePlotData(
        step_values=np.arange(all_cycles.shape[1], dtype=float),
        selected_cycles=selected_cycles,
        mean_values=representative["mean"].to_numpy(dtype=float),
        std_values=representative["std"].fillna(0.0).to_numpy(dtype=float),
        early_mean_values=early_mean_values,
        late_mean_values=late_mean_values,
        support_values=support_values,
        cycle_numbers=metrics["cycle"].to_numpy(dtype=float),
        metric_values={
            key: metrics[key].to_numpy(dtype=float)
            for key in ("mean", "rms", "peak_to_peak", "min", "max")
        },
        length_values=metrics["duration_seconds" if has_durations else "length"].to_numpy(dtype=float),
        length_label="Cycle duration [s]" if has_durations else "Cycle length [samples]",
        length_legend="dur [s]" if has_durations else "len",
        source_label=result.source_column,
    )
