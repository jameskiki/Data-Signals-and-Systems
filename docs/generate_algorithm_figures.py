"""Generate algorithm figures for Markdown and LaTeX documentation."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "images" / "algorithms"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_ops.filtering import apply_simple_filter
from data_ops.cycles import compute_cycle_analysis_from_ranges, detect_rising_edge_cycle_ranges
from data_ops.signals import apply_signal_filter
from data_ops.signals import add_derived_column
from data_ops.spectral import compute_fft_spectrum, compute_welch_psd
from data_ops.summary import summarize_dataframe
from main_window.demo import INPUT_OUTPUT_DEMO, SPECTRAL_REFERENCE_DEMO, create_demo_dataset


def _build_demo_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    _, spectral_frame = create_demo_dataset(SPECTRAL_REFERENCE_DEMO.key)
    _, input_output_frame = create_demo_dataset(INPUT_OUTPUT_DEMO.key)
    return spectral_frame, input_output_frame


def _save_figure(figure: plt.Figure, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / name, dpi=180, bbox_inches="tight")
    plt.close(figure)


def build_fft_example(frame: pd.DataFrame) -> None:
    result = compute_fft_spectrum(
        frame,
        source_column="clean_signal",
        reference_column="time_s",
        window="hann",
        detrend=True,
    )

    figure, axes = plt.subplots(2, 1, figsize=(8, 6), height_ratios=[1, 1.2])
    axes[0].plot(frame["time_s"], frame["clean_signal"], color="#0d47a1", linewidth=1.4)
    axes[0].set_title("Spectral reference demo: clean signal")
    axes[0].set_xlabel("Time [s]")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(result.frequencies, result.amplitudes, color="#1b5e20", linewidth=1.5)
    axes[1].set_title("FFT amplitude spectrum of the spectral reference demo")
    axes[1].set_xlabel("Frequency [Hz]")
    axes[1].set_ylabel("Amplitude")
    axes[1].set_xlim(0, 60)
    axes[1].grid(True, alpha=0.25)

    for _, peak in result.peaks_frame.head(3).iterrows():
        axes[1].axvline(float(peak["frequency_hz"]), color="#a16207", linestyle="--", linewidth=1.0, alpha=0.75)

    _save_figure(figure, "fft_clean_signal.png")


def build_welch_example(frame: pd.DataFrame) -> None:
    result = compute_welch_psd(
        frame,
        source_column="measured_signal",
        reference_column="time_s",
        window="hann",
        detrend=True,
        segment_length=256,
        overlap_fraction=0.5,
    )

    figure, axes = plt.subplots(2, 1, figsize=(8, 6), height_ratios=[1, 1.2])
    axes[0].plot(frame["time_s"], frame["measured_signal"], color="#6a1b9a", linewidth=1.0)
    axes[0].set_title("Spectral reference demo: measured signal")
    axes[0].set_xlabel("Time [s]")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(result.frequencies, result.amplitudes, color="#ad1457", linewidth=1.5)
    axes[1].set_title("Welch PSD of the spectral reference demo")
    axes[1].set_xlabel("Frequency [Hz]")
    axes[1].set_ylabel("PSD")
    axes[1].set_xlim(0, 60)
    axes[1].grid(True, alpha=0.25)

    _save_figure(figure, "welch_noisy_signal.png")


def build_fft_vs_welch_comparison(frame: pd.DataFrame) -> None:
    fft_result = compute_fft_spectrum(
        frame,
        source_column="system_output",
        reference_column="time_s",
        window="hann",
        detrend=True,
    )
    welch_result = compute_welch_psd(
        frame,
        source_column="system_output",
        reference_column="time_s",
        window="hann",
        detrend=True,
        segment_length=256,
        overlap_fraction=0.5,
    )

    figure, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    axes[0].plot(fft_result.frequencies, fft_result.amplitudes, color="#1565c0", linewidth=1.3)
    axes[0].set_title("Input-output demo: FFT amplitude of system output")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(welch_result.frequencies, welch_result.amplitudes, color="#2e7d32", linewidth=1.3)
    axes[1].set_title("Input-output demo: Welch PSD of the same system output")
    axes[1].set_xlabel("Frequency [Hz]")
    axes[1].set_ylabel("PSD")
    axes[1].grid(True, alpha=0.25)
    axes[1].set_xlim(0, 60)

    _save_figure(figure, "fft_vs_welch_comparison.png")


def build_leakage_example(frame: pd.DataFrame) -> None:
    leakage_frame = frame.loc[frame["time_s"] < 1.0, ["time_s", "clean_signal"]].copy()
    rectangular_result = compute_fft_spectrum(
        leakage_frame,
        source_column="clean_signal",
        reference_column="time_s",
        window="rectangular",
        detrend=True,
    )
    hann_result = compute_fft_spectrum(
        leakage_frame,
        source_column="clean_signal",
        reference_column="time_s",
        window="hann",
        detrend=True,
    )

    figure, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    axes[0].plot(rectangular_result.frequencies, rectangular_result.amplitudes, color="#c62828", linewidth=1.3)
    axes[0].set_title("Short demo excerpt with rectangular window")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(hann_result.frequencies, hann_result.amplitudes, color="#ef6c00", linewidth=1.3)
    axes[1].set_title("Same demo excerpt with Hann window")
    axes[1].set_xlabel("Frequency [Hz]")
    axes[1].set_ylabel("Amplitude")
    axes[1].grid(True, alpha=0.25)
    axes[1].set_xlim(0, 40)

    _save_figure(figure, "window_leakage_comparison.png")


def build_filter_smoothing_example(frame: pd.DataFrame) -> None:
    smoothed_frame = apply_signal_filter(
        frame,
        source_column="measured_signal",
        operation="moving_average",
        new_column="measured_signal_ma",
        window_size=21,
    )
    smoothed_frame = apply_signal_filter(
        smoothed_frame,
        source_column="measured_signal",
        operation="median",
        new_column="measured_signal_med",
        window_size=21,
    )
    smoothed_frame = apply_signal_filter(
        smoothed_frame,
        source_column="measured_signal",
        operation="exponential_smoothing",
        new_column="measured_signal_exp",
        alpha=0.15,
    )

    excerpt = smoothed_frame.loc[smoothed_frame["time_s"] <= 4.0].copy()
    figure, axis = plt.subplots(figsize=(8, 4.4))
    axis.plot(excerpt["time_s"], excerpt["measured_signal"], color="#9ca3af", linewidth=0.9, label="measured")
    axis.plot(excerpt["time_s"], excerpt["measured_signal_ma"], color="#2563eb", linewidth=1.3, label="moving average")
    axis.plot(excerpt["time_s"], excerpt["measured_signal_med"], color="#15803d", linewidth=1.2, label="median")
    axis.plot(excerpt["time_s"], excerpt["measured_signal_exp"], color="#b45309", linewidth=1.2, label="exp. smoothing")
    axis.set_title("Spectral demo: smoothing filters on measured_signal")
    axis.set_xlabel("Time [s]")
    axis.set_ylabel("Amplitude")
    axis.grid(True, alpha=0.25)
    axis.legend(frameon=False, ncol=2, fontsize=8)

    _save_figure(figure, "filter_smoothing_comparison.png")


def build_high_pass_example(frame: pd.DataFrame) -> None:
    filtered_frame = apply_signal_filter(
        frame,
        source_column="measured_signal",
        operation="high_pass",
        new_column="measured_signal_hp",
        window_size=101,
    )

    excerpt = filtered_frame.loc[filtered_frame["time_s"] <= 4.0].copy()
    figure, axes = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True)
    axes[0].plot(excerpt["time_s"], excerpt["measured_signal"], color="#6b7280", linewidth=0.9, label="measured")
    axes[0].plot(excerpt["time_s"], excerpt["measured_signal_hp"], color="#dc2626", linewidth=1.1, label="high-pass")
    axes[0].set_title("Spectral demo: high-pass filtering of measured_signal")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(frameon=False, fontsize=8)

    axes[1].plot(excerpt["time_s"], excerpt["measured_signal_hp"], color="#dc2626", linewidth=1.1, label="high-pass")
    axes[1].plot(excerpt["time_s"], excerpt["structural_ringing"], color="#1d4ed8", linewidth=1.0, label="structural_ringing")
    axes[1].set_title("High-pass result versus known ringing component")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Amplitude")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(frameon=False, fontsize=8)

    _save_figure(figure, "high_pass_ringing_comparison.png")


def build_simple_filter_example(frame: pd.DataFrame) -> None:
    filtered_frame = apply_simple_filter(
        frame,
        source_column="structural_ringing",
        new_column="ringing_events",
        minimum_value="0.2",
        maximum_value="",
        keep_missing=False,
    )

    excerpt = filtered_frame.loc[filtered_frame["time_s"] <= 4.0].copy()
    figure, axis = plt.subplots(figsize=(8, 4.0))
    axis.plot(excerpt["time_s"], excerpt["structural_ringing"], color="#6b7280", linewidth=0.9, label="structural_ringing")
    axis.plot(excerpt["time_s"], excerpt["ringing_events"], color="#7c3aed", linewidth=1.3, label="simple filter output")
    axis.set_title("Spectral demo: simple filter keeps only larger ringing excursions")
    axis.set_xlabel("Time [s]")
    axis.set_ylabel("Amplitude")
    axis.grid(True, alpha=0.25)
    axis.legend(frameon=False, fontsize=8)

    _save_figure(figure, "simple_filter_mask_example.png")


def build_derived_delta_derivative_example(frame: pd.DataFrame) -> None:
    derived_frame = add_derived_column(frame, "delta", "measured_signal", "measured_signal_delta")
    derived_frame = add_derived_column(
        derived_frame,
        "derivative",
        "measured_signal",
        "measured_signal_d_dt",
        second_column="time_s",
    )

    excerpt = derived_frame.loc[derived_frame["time_s"] <= 2.0].copy()
    figure, axes = plt.subplots(3, 1, figsize=(8, 6.4), sharex=True)
    axes[0].plot(excerpt["time_s"], excerpt["measured_signal"], color="#1f2937", linewidth=1.0)
    axes[0].set_title("Spectral demo: measured_signal")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(excerpt["time_s"], excerpt["measured_signal_delta"], color="#2563eb", linewidth=1.0)
    axes[1].set_title("First difference")
    axes[1].set_ylabel("Delta")
    axes[1].grid(True, alpha=0.25)

    axes[2].plot(excerpt["time_s"], excerpt["measured_signal_d_dt"], color="#dc2626", linewidth=1.0)
    axes[2].set_title("Derivative using time_s")
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("d/dt")
    axes[2].grid(True, alpha=0.25)

    _save_figure(figure, "derived_delta_derivative_example.png")


def build_derived_normalized_example(frame: pd.DataFrame) -> None:
    derived_frame = add_derived_column(frame, "normalized", "system_output", "system_output_norm")
    excerpt = derived_frame.loc[derived_frame["time_s"] <= 4.0].copy()

    figure, axes = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True)
    axes[0].plot(excerpt["time_s"], excerpt["system_output"], color="#1d4ed8", linewidth=1.0)
    axes[0].set_title("Input-output demo: raw system_output")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(excerpt["time_s"], excerpt["system_output_norm"], color="#15803d", linewidth=1.0)
    axes[1].set_title("Normalized system_output")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("z-score")
    axes[1].grid(True, alpha=0.25)

    _save_figure(figure, "derived_normalized_example.png")


def build_cycle_detection_example(frame: pd.DataFrame) -> None:
    cycle_ranges = detect_rising_edge_cycle_ranges(
        frame,
        reference_column="impact_marker",
        threshold=0.5,
        min_cycle_length=200,
        max_cycles=6,
    )
    excerpt = frame.loc[frame["time_s"] <= 3.0].copy()

    figure, axes = plt.subplots(2, 1, figsize=(8, 5.8), sharex=True)
    axes[0].plot(excerpt["time_s"], excerpt["measured_signal"], color="#1f2937", linewidth=1.0)
    axes[0].set_title("Cycle boundary detection on the spectral demo")
    axes[0].set_ylabel("measured_signal")
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(excerpt["time_s"], excerpt["impact_marker"], color="#7c3aed", linewidth=1.0)
    axes[1].set_title("impact_marker with detected rising edges")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Marker")
    axes[1].grid(True, alpha=0.25)

    for start_index, _end_index in cycle_ranges:
        start_time = float(frame.iloc[start_index]["time_s"])
        if start_time <= float(excerpt["time_s"].max()):
            for axis in axes:
                axis.axvline(start_time, color="#b45309", linestyle="--", linewidth=0.9, alpha=0.7)

    _save_figure(figure, "cycle_detection_example.png")


def build_cycle_representative_example(frame: pd.DataFrame) -> None:
    cycle_ranges = detect_rising_edge_cycle_ranges(
        frame,
        reference_column="impact_marker",
        threshold=0.5,
        min_cycle_length=200,
        max_cycles=8,
    )
    result = compute_cycle_analysis_from_ranges(
        frame,
        source_column="measured_signal",
        cycle_ranges=cycle_ranges,
        method="rising_edge",
        reference_column="impact_marker",
    )

    representative = result.representative_frame
    figure, axis = plt.subplots(figsize=(8, 4.4))
    step = representative["step"].to_numpy()
    mean_values = representative["mean"].to_numpy()
    std_values = representative["std"].fillna(0.0).to_numpy()
    axis.plot(step, mean_values, color="#dc2626", linewidth=1.4, label="mean cycle")
    axis.fill_between(step, mean_values - std_values, mean_values + std_values, color="#fecaca", alpha=0.7, label="mean ± std")
    axis.plot(step, representative["min"], color="#9ca3af", linewidth=0.8, linestyle="--", label="min / max")
    axis.plot(step, representative["max"], color="#9ca3af", linewidth=0.8, linestyle="--")
    axis.set_title("Representative cycle from detected spectral-demo impacts")
    axis.set_xlabel("Aligned sample index")
    axis.set_ylabel("Amplitude")
    axis.grid(True, alpha=0.25)
    axis.legend(frameon=False, fontsize=8)

    _save_figure(figure, "cycle_representative_example.png")


def build_statistics_metric_example(frame: pd.DataFrame) -> None:
    stats_frame = summarize_dataframe(frame[["clean_signal", "measured_signal", "response_signal", "structural_ringing"]]).statistics_frame
    selected = stats_frame.loc[:, ["mean", "std", "rms", "peak_to_peak"]]
    columns = list(selected.index)
    x = np.arange(len(columns))
    width = 0.18

    figure, axis = plt.subplots(figsize=(8, 4.6))
    for offset, metric in enumerate(selected.columns):
        axis.bar(x + (offset - 1.5) * width, selected[metric].to_numpy(), width=width, label=metric)
    axis.set_title("Engineering statistics on selected spectral-demo channels")
    axis.set_xticks(x)
    axis.set_xticklabels(columns, rotation=15, ha="right")
    axis.set_ylabel("Value")
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend(frameon=False, ncol=2, fontsize=8)

    _save_figure(figure, "statistics_metric_comparison.png")


def build_correlation_heatmap_example(frame: pd.DataFrame) -> None:
    correlation = summarize_dataframe(frame[["clean_signal", "measured_signal", "response_signal", "structural_ringing"]]).correlation_frame
    labels = list(correlation.columns)

    figure, axis = plt.subplots(figsize=(6.2, 5.4))
    image = axis.imshow(correlation.to_numpy(), vmin=-1.0, vmax=1.0, cmap="coolwarm")
    axis.set_title("Correlation matrix on selected spectral-demo channels")
    axis.set_xticks(np.arange(len(labels)))
    axis.set_yticks(np.arange(len(labels)))
    axis.set_xticklabels(labels, rotation=25, ha="right")
    axis.set_yticklabels(labels)

    for row_index in range(len(labels)):
        for column_index in range(len(labels)):
            value = float(correlation.iloc[row_index, column_index])
            axis.text(column_index, row_index, f"{value:.2f}", ha="center", va="center", color="#111827", fontsize=8)

    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04, label="Pearson r")
    _save_figure(figure, "correlation_heatmap_example.png")


def main() -> None:
    spectral_frame, input_output_frame = _build_demo_frames()
    build_fft_example(spectral_frame)
    build_welch_example(spectral_frame)
    build_fft_vs_welch_comparison(input_output_frame)
    build_leakage_example(spectral_frame)
    build_filter_smoothing_example(spectral_frame)
    build_high_pass_example(spectral_frame)
    build_simple_filter_example(spectral_frame)
    build_derived_delta_derivative_example(spectral_frame)
    build_derived_normalized_example(input_output_frame)
    build_cycle_detection_example(spectral_frame)
    build_cycle_representative_example(spectral_frame)
    build_statistics_metric_example(spectral_frame)
    build_correlation_heatmap_example(spectral_frame)
    print(f"Wrote figures to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()