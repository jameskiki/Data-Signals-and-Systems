"""Parameter rules for the analysis workspace — pure Python, no Tk imports.

Each ParameterRule captures the frame visibility, widget enable/disable state,
required parameters, and hint text for one method selection. The orchestrator
(rules_orchestrator.py) reads these rules and applies them to the live workspace;
all Tk coupling stays there.

Rule coverage: 16 IDs across three domains.
  Frequency (5): FFT Amplitude, Welch PSD, Transfer Estimate, Coherence, Spectrogram
  Signal Filter (7): moving_average, median, exponential_smoothing, high_pass,
                     butterworth_lowpass, butterworth_highpass, butterworth_bandpass
  Cycle (4): fixed_length, rising_edge, zero_crossing, peak
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParameterRule:
    """Immutable descriptor for one method's UI and parameter requirements."""

    domain: str
    method_id: str
    show_frames: tuple[str, ...]
    hide_frames: tuple[str, ...]
    required_non_empty: tuple[str, ...]
    required_positive: tuple[str, ...]
    hint: str
    enable_widgets: tuple[str, ...] = field(default=())
    disable_widgets: tuple[str, ...] = field(default=())


# ---------------------------------------------------------------------------
# Frequency domain
# ---------------------------------------------------------------------------

FREQUENCY_RULES: dict[str, ParameterRule] = {
    "FFT Amplitude": ParameterRule(
        domain="frequency",
        method_id="FFT Amplitude",
        show_frames=("freq_general_frame",),
        hide_frames=("comparison_frame", "welch_specific_frame"),
        required_non_empty=(),
        required_positive=("sample_spacing",),
        hint="Set Index step size if the time axis is not in integer samples.",
        disable_widgets=("frequency_compare_combo",),
    ),
    "Welch PSD": ParameterRule(
        domain="frequency",
        method_id="Welch PSD",
        show_frames=("freq_general_frame", "welch_specific_frame"),
        hide_frames=("comparison_frame",),
        required_non_empty=(),
        required_positive=("sample_spacing", "segment_length"),
        hint="Set Welch segment length and Index step size.",
        disable_widgets=("frequency_compare_combo",),
    ),
    "Transfer Estimate": ParameterRule(
        domain="frequency",
        method_id="Transfer Estimate",
        show_frames=("comparison_frame", "freq_general_frame", "welch_specific_frame"),
        hide_frames=(),
        required_non_empty=("comparison_signal",),
        required_positive=("sample_spacing", "segment_length"),
        hint="Select a Comparison signal. Set segment length and Index step size.",
        enable_widgets=("frequency_compare_combo",),
    ),
    "Coherence": ParameterRule(
        domain="frequency",
        method_id="Coherence",
        show_frames=("comparison_frame", "freq_general_frame", "welch_specific_frame"),
        hide_frames=(),
        required_non_empty=("comparison_signal",),
        required_positive=("sample_spacing", "segment_length"),
        hint="Select a Comparison signal. Set segment length and Index step size.",
        enable_widgets=("frequency_compare_combo",),
    ),
    "Spectrogram": ParameterRule(
        domain="frequency",
        method_id="Spectrogram",
        show_frames=("freq_general_frame", "welch_specific_frame"),
        hide_frames=("comparison_frame",),
        required_non_empty=(),
        required_positive=("sample_spacing", "segment_length"),
        hint="Set segment length and Index step size for time-frequency resolution.",
        disable_widgets=("frequency_compare_combo",),
    ),
}

# ---------------------------------------------------------------------------
# Signal filter domain
# ---------------------------------------------------------------------------

_WINDOW_FRAMES = ("signal_filter_window_frame",)
_WINDOW_HIDE = ("signal_filter_alpha_frame", "signal_filter_butterworth_frame")
_ALPHA_FRAMES = ("signal_filter_alpha_frame",)
_ALPHA_HIDE = ("signal_filter_window_frame", "signal_filter_butterworth_frame")
_BUTTERWORTH_FRAMES = ("signal_filter_butterworth_frame",)
_BUTTERWORTH_HIDE = ("signal_filter_window_frame", "signal_filter_alpha_frame", "signal_filter_bandpass_frame")
_BANDPASS_FRAMES = ("signal_filter_butterworth_frame", "signal_filter_bandpass_frame")
_BANDPASS_HIDE = ("signal_filter_window_frame", "signal_filter_alpha_frame")

SIGNAL_FILTER_RULES: dict[str, ParameterRule] = {
    "moving_average": ParameterRule(
        domain="signal_filter",
        method_id="moving_average",
        show_frames=_WINDOW_FRAMES,
        hide_frames=_WINDOW_HIDE,
        required_non_empty=(),
        required_positive=("window_size",),
        hint="Set Window size (integer ≥ 2) for centered rolling mean.",
    ),
    "median": ParameterRule(
        domain="signal_filter",
        method_id="median",
        show_frames=_WINDOW_FRAMES,
        hide_frames=_WINDOW_HIDE,
        required_non_empty=(),
        required_positive=("window_size",),
        hint="Set Window size (integer ≥ 2) for centered rolling median.",
    ),
    "exponential_smoothing": ParameterRule(
        domain="signal_filter",
        method_id="exponential_smoothing",
        show_frames=_ALPHA_FRAMES,
        hide_frames=_ALPHA_HIDE,
        required_non_empty=(),
        required_positive=("alpha",),
        hint="Set Alpha (0 < α ≤ 1) for recursive smoothing strength.",
    ),
    "high_pass": ParameterRule(
        domain="signal_filter",
        method_id="high_pass",
        show_frames=_WINDOW_FRAMES,
        hide_frames=_WINDOW_HIDE,
        required_non_empty=(),
        required_positive=("window_size",),
        hint="Set Window size (integer ≥ 2) for the low-pass trend to subtract.",
    ),
    "butterworth_lowpass": ParameterRule(
        domain="signal_filter",
        method_id="butterworth_lowpass",
        show_frames=_BUTTERWORTH_FRAMES,
        hide_frames=_BUTTERWORTH_HIDE,
        required_non_empty=(),
        required_positive=("cutoff_hz", "sample_spacing", "filter_order"),
        hint="Set Cutoff freq [Hz], Sample spacing [s], and Filter order for zero-phase LP.",
    ),
    "butterworth_highpass": ParameterRule(
        domain="signal_filter",
        method_id="butterworth_highpass",
        show_frames=_BUTTERWORTH_FRAMES,
        hide_frames=_BUTTERWORTH_HIDE,
        required_non_empty=(),
        required_positive=("cutoff_hz", "sample_spacing", "filter_order"),
        hint="Set Cutoff freq [Hz], Sample spacing [s], and Filter order for zero-phase HP.",
    ),
    "butterworth_bandpass": ParameterRule(
        domain="signal_filter",
        method_id="butterworth_bandpass",
        show_frames=_BANDPASS_FRAMES,
        hide_frames=_BANDPASS_HIDE,
        required_non_empty=(),
        required_positive=("cutoff_hz", "cutoff_hz_high", "sample_spacing", "filter_order"),
        hint="Set low and high cutoff frequencies, sample spacing, and filter order for zero-phase BP.",
    ),
}

# ---------------------------------------------------------------------------
# Cycle domain
# ---------------------------------------------------------------------------

CYCLE_RULES: dict[str, ParameterRule] = {
    "fixed_length": ParameterRule(
        domain="cycle",
        method_id="fixed_length",
        show_frames=("cycle_fixed_frame",),
        hide_frames=("cycle_edge_frame", "cycle_peak_frame", "cycle_max_frame"),
        required_non_empty=(),
        required_positive=("cycle_length",),
        hint="Set Cycle length (samples per cycle).",
    ),
    "rising_edge": ParameterRule(
        domain="cycle",
        method_id="rising_edge",
        show_frames=("cycle_edge_frame", "cycle_max_frame"),
        hide_frames=("cycle_fixed_frame", "cycle_peak_frame"),
        required_non_empty=(),
        required_positive=(),
        hint="Set Reference column and Threshold for rising-edge detection.",
    ),
    "zero_crossing": ParameterRule(
        domain="cycle",
        method_id="zero_crossing",
        show_frames=("cycle_edge_frame", "cycle_max_frame"),
        hide_frames=("cycle_fixed_frame", "cycle_peak_frame"),
        required_non_empty=(),
        required_positive=(),
        hint="Set Reference column for zero-crossing detection.",
    ),
    "peak": ParameterRule(
        domain="cycle",
        method_id="peak",
        show_frames=("cycle_peak_frame", "cycle_max_frame"),
        hide_frames=("cycle_fixed_frame", "cycle_edge_frame"),
        required_non_empty=(),
        required_positive=(),
        hint="Set Reference column and Prominence for peak-based cycle detection.",
    ),
}

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

_ALL_RULES: dict[str, dict[str, ParameterRule]] = {
    "frequency": FREQUENCY_RULES,
    "signal_filter": SIGNAL_FILTER_RULES,
    "cycle": CYCLE_RULES,
}


def get_rule(domain: str, method_id: str) -> ParameterRule | None:
    """Return the rule for (domain, method_id), or None if not registered."""
    return _ALL_RULES.get(domain, {}).get(method_id)


def validate_params(rule: ParameterRule, workspace_vars: dict[str, object]) -> list[str]:
    """Return a list of human-readable error strings for any failing parameter constraints.

    workspace_vars maps param names (as used in required_non_empty / required_positive)
    to the current string values read from the workspace.
    """
    errors: list[str] = []
    for param in rule.required_non_empty:
        value = workspace_vars.get(param)
        if value is None or str(value).strip() == "":
            errors.append(f"'{param}' is required for {rule.method_id}")
    for param in rule.required_positive:
        value = workspace_vars.get(param)
        try:
            if float(str(value or 0)) <= 0:
                errors.append(f"'{param}' must be > 0 for {rule.method_id} (got {value!r})")
        except (ValueError, TypeError):
            errors.append(f"'{param}' must be a positive number for {rule.method_id} (got {value!r})")
    if rule.method_id == "butterworth_bandpass":
        low_cutoff = workspace_vars.get("cutoff_hz")
        high_cutoff = workspace_vars.get("cutoff_hz_high")
        try:
            low_value = float(str(low_cutoff or 0))
            high_value = float(str(high_cutoff or 0))
            if low_value > 0 and high_value > 0 and low_value >= high_value:
                errors.append(
                    f"'cutoff_hz_high' must be greater than 'cutoff_hz' for {rule.method_id} "
                    f"(got low={low_cutoff!r}, high={high_cutoff!r})"
                )
        except (ValueError, TypeError):
            pass
    return errors
