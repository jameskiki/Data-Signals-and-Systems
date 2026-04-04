"""Generate algorithm figures for Markdown and LaTeX documentation."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_ops.spectral import compute_fft_spectrum, compute_welch_psd
from evaldata_demo import INPUT_OUTPUT_DEMO, SPECTRAL_REFERENCE_DEMO, create_demo_dataset


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "images" / "algorithms"


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


def main() -> None:
    spectral_frame, input_output_frame = _build_demo_frames()
    build_fft_example(spectral_frame)
    build_welch_example(spectral_frame)
    build_fft_vs_welch_comparison(input_output_frame)
    build_leakage_example(spectral_frame)
    print(f"Wrote figures to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()