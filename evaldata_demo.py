"""Deterministic demo datasets for validating analysis features."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DemoDatasetSpec:
    """Metadata for one deterministic demo dataset."""

    key: str
    menu_label: str
    basename: str
    suffix: str
    description: str
    summary: str
    column_roles: dict[str, str]


SPECTRAL_REFERENCE_DEMO = DemoDatasetSpec(
    key="spectral_reference",
    menu_label="Spectral Reference Signal",
    basename="demo_reference_signal.csv",
    suffix="synthetic_reference",
    description="Synthetic reference dataset with known DC, sinusoidal, periodic, and noise components.",
    summary=(
        "Components: DC=2.5, sinusoids at 1.0 Hz, 7.5 Hz, 18.0 Hz, low-frequency drift at 0.15 Hz, "
        "periodic impact train at 2.0 Hz, damped structural ringing at 42 Hz, and seeded broadband noise."
    ),
    column_roles={
        "time_s": "time",
        "clean_signal": "signal",
        "measured_signal": "output",
        "response_signal": "output",
        "dc_component": "signal",
        "low_frequency_drift": "signal",
        "structural_ringing": "signal",
        "impact_marker": "metadata",
        "cycle_phase_deg": "metadata",
        "temperature_c": "metadata",
    },
)

INPUT_OUTPUT_DEMO = DemoDatasetSpec(
    key="input_output_reference",
    menu_label="Input-Output Validation Signal",
    basename="demo_input_output_signal.csv",
    suffix="synthetic_io_reference",
    description="Synthetic input-output dataset for later transfer, coherence, and systems validation.",
    summary=(
        "Channels: actuator input with 2.0 Hz, 12.0 Hz, and 28.0 Hz content; system output with delay, "
        "low-pass behavior, added 12 Hz resonance, and seeded measurement noise."
    ),
    column_roles={
        "time_s": "time",
        "actuator_input": "input",
        "delayed_input": "input",
        "system_output": "output",
        "output_residual": "signal",
        "resonance_component": "signal",
    },
)

DEMO_DATASET_SPECS = (SPECTRAL_REFERENCE_DEMO, INPUT_OUTPUT_DEMO)
DEMO_DATASET_SPEC_BY_KEY = {spec.key: spec for spec in DEMO_DATASET_SPECS}


def build_demo_menu_description_lines(spec: DemoDatasetSpec) -> list[str]:
    """Return short menu-friendly description lines for one demo dataset."""

    if spec.key == SPECTRAL_REFERENCE_DEMO.key:
        return [
            "500 Hz, 20 s deterministic signal",
            "Peaks: 1.0, 7.5, 18.0 Hz",
            "Extras: drift 0.15 Hz, ringing 42 Hz, impacts 2.0 Hz",
            "Test with FFT, Welch PSD, filtering, and cycles",
        ]

    if spec.key == INPUT_OUTPUT_DEMO.key:
        return [
            "400 Hz, 25 s input-output dataset",
            "Input: 2.0, 12.0, 28.0 Hz content",
            "Output: delayed, low-pass, 12 Hz resonance",
            "Test with FFT, Welch PSD, filtering, and derived signals",
        ]

    return [spec.description, spec.summary]


def create_demo_signal_dataset() -> pd.DataFrame:
    """Create a deterministic multi-channel signal dataset for UI and analysis checks."""

    sample_rate_hz = 500.0
    duration_s = 20.0
    sample_spacing_s = 1.0 / sample_rate_hz
    row_count = int(duration_s * sample_rate_hz)

    time_s = np.arange(row_count, dtype=float) * sample_spacing_s
    rng = np.random.default_rng(42)

    dc_component = np.full(row_count, 2.5, dtype=float)
    base_1_hz = 3.0 * np.sin(2.0 * np.pi * 1.0 * time_s)
    harmonic_7_5_hz = 1.2 * np.sin(2.0 * np.pi * 7.5 * time_s + 0.35)
    harmonic_18_hz = 0.6 * np.cos(2.0 * np.pi * 18.0 * time_s - 0.6)
    low_frequency_drift = 0.35 * np.sin(2.0 * np.pi * 0.15 * time_s)

    impact_period_s = 0.5
    impact_duration_s = 0.02
    impact_train = ((time_s % impact_period_s) < impact_duration_s).astype(float)

    structural_ringing = np.zeros(row_count, dtype=float)
    decay_duration_s = 0.22
    decay_samples = int(decay_duration_s * sample_rate_hz)
    decay_time = np.arange(decay_samples, dtype=float) * sample_spacing_s
    decay_kernel = 1.4 * np.exp(-12.0 * decay_time) * np.sin(2.0 * np.pi * 42.0 * decay_time)
    impact_indices = np.flatnonzero(impact_train > 0.0)
    for impact_index in impact_indices:
        end_index = min(row_count, impact_index + decay_samples)
        kernel_length = end_index - impact_index
        structural_ringing[impact_index:end_index] += decay_kernel[:kernel_length]

    broadband_noise = 0.08 * rng.standard_normal(row_count)
    sensor_noise = 0.03 * rng.standard_normal(row_count)

    clean_signal = dc_component + base_1_hz + harmonic_7_5_hz + harmonic_18_hz
    measured_signal = clean_signal + low_frequency_drift + structural_ringing + broadband_noise
    response_signal = 0.8 * clean_signal + 0.45 * structural_ringing + sensor_noise
    cycle_phase_deg = (time_s * 2.0 * 360.0) % 360.0
    temperature_c = 23.0 + 0.25 * np.sin(2.0 * np.pi * 0.03 * time_s)

    return pd.DataFrame(
        {
            "time_s": time_s,
            "clean_signal": clean_signal,
            "measured_signal": measured_signal,
            "response_signal": response_signal,
            "dc_component": dc_component,
            "low_frequency_drift": low_frequency_drift,
            "structural_ringing": structural_ringing,
            "impact_marker": impact_train,
            "cycle_phase_deg": cycle_phase_deg,
            "temperature_c": temperature_c,
        }
    )


def create_input_output_demo_dataset() -> pd.DataFrame:
    """Create a deterministic input-output dataset for future systems validation."""

    sample_rate_hz = 400.0
    duration_s = 25.0
    sample_spacing_s = 1.0 / sample_rate_hz
    row_count = int(duration_s * sample_rate_hz)

    time_s = np.arange(row_count, dtype=float) * sample_spacing_s
    rng = np.random.default_rng(84)

    actuator_input = (
        0.8 * np.sin(2.0 * np.pi * 2.0 * time_s)
        + 1.0 * np.sin(2.0 * np.pi * 12.0 * time_s + 0.2)
        + 0.45 * np.cos(2.0 * np.pi * 28.0 * time_s - 0.4)
    )
    actuator_input += 0.06 * rng.standard_normal(row_count)

    delayed_input = np.roll(actuator_input, 6)
    delayed_input[:6] = 0.0
    smoothed_output = np.zeros(row_count, dtype=float)
    for index in range(1, row_count):
        smoothed_output[index] = 0.92 * smoothed_output[index - 1] + 0.08 * delayed_input[index]

    resonance = 0.35 * np.sin(2.0 * np.pi * 12.0 * time_s + 0.9)
    output_noise = 0.03 * rng.standard_normal(row_count)
    system_output = 1.4 + 1.35 * smoothed_output + resonance + output_noise
    output_residual = system_output - delayed_input

    return pd.DataFrame(
        {
            "time_s": time_s,
            "actuator_input": actuator_input,
            "delayed_input": delayed_input,
            "system_output": system_output,
            "output_residual": output_residual,
            "resonance_component": resonance,
        }
    )


def create_demo_dataset(demo_key: str) -> tuple[DemoDatasetSpec, pd.DataFrame]:
    """Create one deterministic demo dataset by key."""

    spec = DEMO_DATASET_SPEC_BY_KEY.get(demo_key)
    if spec is None:
        raise KeyError(f"Unknown demo dataset key: {demo_key}")
    if demo_key == SPECTRAL_REFERENCE_DEMO.key:
        return spec, create_demo_signal_dataset()
    if demo_key == INPUT_OUTPUT_DEMO.key:
        return spec, create_input_output_demo_dataset()
    raise KeyError(f"Unsupported demo dataset key: {demo_key}")


def describe_demo_frequency_expectations(
    dataframe: pd.DataFrame,
    active_column: str,
    analysis_name: str,
    comparison_column: str | None = None,
) -> str:
    """Return expected spectral content notes for known demo columns."""

    columns = set(map(str, dataframe.columns))
    normalized_column = active_column.strip()
    normalized_analysis = analysis_name.strip() or "FFT Amplitude"
    normalized_comparison = (comparison_column or "").strip()

    if {"clean_signal", "measured_signal", "response_signal", "structural_ringing"}.issubset(columns):
        if normalized_column == "clean_signal":
            return (
                f"Expected for {normalized_analysis}: strong peaks near 1.0 Hz, 7.5 Hz, and 18.0 Hz, plus a visible DC term "
                "only when detrending is disabled."
            )
        if normalized_column == "measured_signal":
            return (
                f"Expected for {normalized_analysis}: the clean peaks near 1.0 Hz, 7.5 Hz, and 18.0 Hz remain dominant, with added "
                "low-frequency energy near 0.15 Hz and broader content around 42 Hz from structural ringing."
            )
        if normalized_column == "response_signal":
            return (
                f"Expected for {normalized_analysis}: similar harmonic peaks to clean_signal, but lower amplitude and stronger 42 Hz "
                "ringing contribution."
            )
        if normalized_column == "structural_ringing":
            return f"Expected for {normalized_analysis}: dominant energy concentrated near 42 Hz with broader side content from the decaying impacts."

    if {"actuator_input", "system_output", "delayed_input", "resonance_component"}.issubset(columns):
        if normalized_analysis == "Transfer Estimate":
            if normalized_column == "system_output" and normalized_comparison in {"actuator_input", "delayed_input"}:
                return (
                    "Expected for Transfer Estimate: strongest magnitude around 12.0 Hz because of the added resonance, with reduced "
                    "high-frequency magnitude toward 28.0 Hz due to the low-pass behavior."
                )
            return "Expected for Transfer Estimate: use actuator_input or delayed_input as the comparison channel and system_output as the active column."
        if normalized_analysis == "Coherence":
            if normalized_column == "system_output" and normalized_comparison in {"actuator_input", "delayed_input"}:
                return (
                    "Expected for Coherence: high coherence near 2.0 Hz, 12.0 Hz, and 28.0 Hz, with the strongest agreement around 12.0 Hz and "
                    "lower coherence away from the driven frequencies."
                )
            return "Expected for Coherence: compare system_output against actuator_input or delayed_input to verify the driven frequencies."
        if normalized_column in {"actuator_input", "delayed_input"}:
            return (
                f"Expected for {normalized_analysis}: clear peaks near 2.0 Hz, 12.0 Hz, and 28.0 Hz. This is the reference channel for later "
                "input-output checks."
            )
        if normalized_column == "system_output":
            return (
                f"Expected for {normalized_analysis}: peaks remain near 2.0 Hz, 12.0 Hz, and 28.0 Hz, but high-frequency content is more "
                "attenuated and the 12.0 Hz region is relatively emphasized by the added resonance."
            )
        if normalized_column == "resonance_component":
            return f"Expected for {normalized_analysis}: a narrow dominant peak centered near 12.0 Hz."

    return "No built-in validation note is available for the current dataset/column."