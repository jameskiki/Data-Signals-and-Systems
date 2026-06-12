"""Tests for Source/analysis_app/rules.py — pure logic, no Tk."""

import pytest

from Source.analysis_app.rules import (
    CYCLE_RULES,
    FREQUENCY_RULES,
    SIGNAL_FILTER_RULES,
    ParameterRule,
    get_rule,
    validate_params,
)


# ---------------------------------------------------------------------------
# Rule coverage
# ---------------------------------------------------------------------------

class TestRuleCoverage:
    def test_all_16_rule_ids_are_registered(self):
        frequency_ids = list(FREQUENCY_RULES)
        signal_filter_ids = list(SIGNAL_FILTER_RULES)
        cycle_ids = list(CYCLE_RULES)
        assert len(frequency_ids) == 5
        assert len(signal_filter_ids) == 7
        assert len(cycle_ids) == 4
        assert len(frequency_ids) + len(signal_filter_ids) + len(cycle_ids) == 16

    def test_frequency_rule_ids(self):
        assert set(FREQUENCY_RULES) == {
            "FFT Amplitude", "Welch PSD", "Transfer Estimate", "Coherence", "Spectrogram"
        }

    def test_signal_filter_rule_ids(self):
        assert set(SIGNAL_FILTER_RULES) == {
            "moving_average", "median", "exponential_smoothing", "high_pass",
            "butterworth_lowpass", "butterworth_highpass", "butterworth_bandpass",
        }

    def test_cycle_rule_ids(self):
        assert set(CYCLE_RULES) == {
            "fixed_length", "rising_edge", "zero_crossing", "peak"
        }

    def test_all_rules_are_frozen_dataclasses(self):
        all_rules = list(FREQUENCY_RULES.values()) + list(SIGNAL_FILTER_RULES.values()) + list(CYCLE_RULES.values())
        for rule in all_rules:
            assert isinstance(rule, ParameterRule)
            with pytest.raises((AttributeError, TypeError)):
                rule.method_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# get_rule
# ---------------------------------------------------------------------------

class TestGetRule:
    def test_returns_rule_for_known_domain_and_method(self):
        rule = get_rule("frequency", "FFT Amplitude")
        assert rule is not None
        assert rule.method_id == "FFT Amplitude"
        assert rule.domain == "frequency"

    def test_returns_none_for_unknown_domain(self):
        assert get_rule("unknown_domain", "FFT Amplitude") is None

    def test_returns_none_for_unknown_method(self):
        assert get_rule("frequency", "nonexistent_method") is None

    def test_returns_none_for_empty_strings(self):
        assert get_rule("", "") is None

    def test_signal_filter_lookup(self):
        rule = get_rule("signal_filter", "butterworth_lowpass")
        assert rule is not None
        assert "sample_spacing" in rule.required_positive
        assert "cutoff_hz" in rule.required_positive
        assert "filter_order" in rule.required_positive

    def test_bandpass_lookup_includes_high_cutoff(self):
        rule = get_rule("signal_filter", "butterworth_bandpass")
        assert rule is not None
        assert "cutoff_hz" in rule.required_positive
        assert "cutoff_hz_high" in rule.required_positive

    def test_cycle_lookup(self):
        rule = get_rule("cycle", "fixed_length")
        assert rule is not None
        assert "cycle_length" in rule.required_positive


# ---------------------------------------------------------------------------
# validate_params
# ---------------------------------------------------------------------------

class TestValidateParams:
    def _fft_rule(self) -> ParameterRule:
        return get_rule("frequency", "FFT Amplitude")

    def _butterworth_rule(self) -> ParameterRule:
        return get_rule("signal_filter", "butterworth_lowpass")

    def _transfer_rule(self) -> ParameterRule:
        return get_rule("frequency", "Transfer Estimate")

    def _fixed_length_rule(self) -> ParameterRule:
        return get_rule("cycle", "fixed_length")

    # --- required_positive ---

    def test_passes_when_all_required_positive_are_positive(self):
        rule = self._butterworth_rule()
        errors = validate_params(rule, {"cutoff_hz": "10.0", "sample_spacing": "0.01", "filter_order": "4"})
        assert errors == []

    def test_fails_when_required_positive_is_zero(self):
        rule = self._butterworth_rule()
        errors = validate_params(rule, {"cutoff_hz": "10.0", "sample_spacing": "0.0", "filter_order": "4"})
        assert len(errors) == 1
        assert "sample_spacing" in errors[0]

    def test_fails_when_required_positive_is_negative(self):
        rule = self._butterworth_rule()
        errors = validate_params(rule, {"cutoff_hz": "-5.0", "sample_spacing": "0.01", "filter_order": "4"})
        assert len(errors) == 1
        assert "cutoff_hz" in errors[0]

    def test_fails_when_required_positive_is_empty_string(self):
        rule = self._butterworth_rule()
        errors = validate_params(rule, {"cutoff_hz": "", "sample_spacing": "0.01", "filter_order": "4"})
        assert any("cutoff_hz" in e for e in errors)

    def test_fails_when_required_positive_is_non_numeric(self):
        rule = self._butterworth_rule()
        errors = validate_params(rule, {"cutoff_hz": "abc", "sample_spacing": "0.01", "filter_order": "4"})
        assert any("cutoff_hz" in e for e in errors)

    def test_bandpass_requires_high_cutoff(self):
        rule = get_rule("signal_filter", "butterworth_bandpass")
        errors = validate_params(
            rule,
            {"cutoff_hz": "10.0", "cutoff_hz_high": "0.0", "sample_spacing": "0.01", "filter_order": "4"},
        )
        assert len(errors) == 1
        assert any("cutoff_hz_high" in e for e in errors)

    def test_bandpass_rejects_high_cutoff_below_low_cutoff(self):
        rule = get_rule("signal_filter", "butterworth_bandpass")
        errors = validate_params(
            rule,
            {"cutoff_hz": "20.0", "cutoff_hz_high": "10.0", "sample_spacing": "0.01", "filter_order": "4"},
        )
        assert any("must be greater than 'cutoff_hz'" in e for e in errors)

    def test_multiple_failures_reported(self):
        rule = self._butterworth_rule()
        errors = validate_params(rule, {"cutoff_hz": "0.0", "sample_spacing": "0.0", "filter_order": "0"})
        assert len(errors) == 3

    def test_fft_sample_spacing_zero_is_blocked(self):
        rule = self._fft_rule()
        errors = validate_params(rule, {"sample_spacing": "0.0", "segment_length": "256", "comparison_signal": ""})
        assert any("sample_spacing" in e for e in errors)

    def test_fft_positive_sample_spacing_passes(self):
        rule = self._fft_rule()
        errors = validate_params(rule, {"sample_spacing": "0.01", "segment_length": "256", "comparison_signal": ""})
        assert errors == []

    def test_cycle_fixed_length_zero_blocked(self):
        rule = self._fixed_length_rule()
        errors = validate_params(rule, {"cycle_length": "0"})
        assert len(errors) == 1
        assert "cycle_length" in errors[0]

    def test_cycle_fixed_length_positive_passes(self):
        rule = self._fixed_length_rule()
        errors = validate_params(rule, {"cycle_length": "100"})
        assert errors == []

    # --- required_non_empty ---

    def test_transfer_estimate_fails_when_comparison_signal_empty(self):
        rule = self._transfer_rule()
        errors = validate_params(rule, {
            "sample_spacing": "0.01",
            "segment_length": "256",
            "comparison_signal": "",
        })
        assert any("comparison_signal" in e for e in errors)

    def test_transfer_estimate_passes_when_comparison_signal_provided(self):
        rule = self._transfer_rule()
        errors = validate_params(rule, {
            "sample_spacing": "0.01",
            "segment_length": "256",
            "comparison_signal": "sensor_b",
        })
        assert errors == []

    def test_missing_key_treated_as_empty(self):
        rule = self._transfer_rule()
        # comparison_signal not in dict at all
        errors = validate_params(rule, {"sample_spacing": "0.01", "segment_length": "256"})
        assert any("comparison_signal" in e for e in errors)

    # --- edge cases ---

    def test_empty_rule_returns_no_errors(self):
        rule = get_rule("cycle", "rising_edge")
        assert validate_params(rule, {}) == []

    def test_extra_keys_in_workspace_vars_are_ignored(self):
        rule = self._fixed_length_rule()
        errors = validate_params(rule, {"cycle_length": "50", "irrelevant_key": "anything"})
        assert errors == []


# ---------------------------------------------------------------------------
# Frame visibility fields
# ---------------------------------------------------------------------------

class TestFrameVisibilityFields:
    def test_butterworth_shows_butterworth_frame(self):
        rule = get_rule("signal_filter", "butterworth_lowpass")
        assert "signal_filter_butterworth_frame" in rule.show_frames
        assert "signal_filter_window_frame" in rule.hide_frames
        assert "signal_filter_alpha_frame" in rule.hide_frames

    def test_bandpass_shows_bandpass_frame(self):
        rule = get_rule("signal_filter", "butterworth_bandpass")
        assert "signal_filter_butterworth_frame" in rule.show_frames
        assert "signal_filter_bandpass_frame" in rule.show_frames
        assert "signal_filter_bandpass_frame" not in rule.hide_frames

    def test_exponential_smoothing_shows_alpha_frame(self):
        rule = get_rule("signal_filter", "exponential_smoothing")
        assert "signal_filter_alpha_frame" in rule.show_frames
        assert "signal_filter_window_frame" in rule.hide_frames
        assert "signal_filter_butterworth_frame" in rule.hide_frames

    def test_moving_average_shows_window_frame(self):
        rule = get_rule("signal_filter", "moving_average")
        assert "signal_filter_window_frame" in rule.show_frames
        assert "signal_filter_alpha_frame" in rule.hide_frames
        assert "signal_filter_butterworth_frame" in rule.hide_frames

    def test_fft_hides_comparison_and_welch_frames(self):
        rule = get_rule("frequency", "FFT Amplitude")
        assert "comparison_frame" in rule.hide_frames
        assert "welch_specific_frame" in rule.hide_frames
        assert "freq_general_frame" in rule.show_frames

    def test_transfer_estimate_shows_comparison_frame(self):
        rule = get_rule("frequency", "Transfer Estimate")
        assert "comparison_frame" in rule.show_frames
        assert "welch_specific_frame" in rule.show_frames

    def test_transfer_estimate_enables_comparison_combo(self):
        rule = get_rule("frequency", "Transfer Estimate")
        assert "frequency_compare_combo" in rule.enable_widgets

    def test_fft_disables_comparison_combo(self):
        rule = get_rule("frequency", "FFT Amplitude")
        assert "frequency_compare_combo" in rule.disable_widgets

    def test_cycle_fixed_length_shows_fixed_frame(self):
        rule = get_rule("cycle", "fixed_length")
        assert "cycle_fixed_frame" in rule.show_frames
        assert "cycle_edge_frame" in rule.hide_frames
        assert "cycle_peak_frame" in rule.hide_frames
        assert "cycle_max_frame" in rule.hide_frames

    def test_cycle_rising_edge_shows_edge_and_max_frames(self):
        rule = get_rule("cycle", "rising_edge")
        assert "cycle_edge_frame" in rule.show_frames
        assert "cycle_max_frame" in rule.show_frames
        assert "cycle_fixed_frame" in rule.hide_frames
        assert "cycle_peak_frame" in rule.hide_frames

    def test_cycle_peak_shows_peak_and_max_frames(self):
        rule = get_rule("cycle", "peak")
        assert "cycle_peak_frame" in rule.show_frames
        assert "cycle_max_frame" in rule.show_frames
        assert "cycle_fixed_frame" in rule.hide_frames
        assert "cycle_edge_frame" in rule.hide_frames
