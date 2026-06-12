"""Tests for analysis_app.handlers orchestration behavior."""

from contextlib import contextmanager
from types import SimpleNamespace

import pandas as pd

from Source.analysis_app.actions import FrameUpdate
from Source.analysis_app import handlers


class DummyVar:
    """Minimal stand-in for tk variable objects used by handlers."""

    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyNotifications:
    """Collect success messages emitted by handlers."""

    def __init__(self):
        self.success_messages = []
        self.warning_messages = []

    def success(self, message):
        self.success_messages.append(message)

    def warning(self, message, details=None):
        self.warning_messages.append((message, details))


class DummyWorkspace:
    """Workspace facade exposing only members expected by handlers."""

    def __init__(self):
        self.session = SimpleNamespace(working_frame=pd.DataFrame({"time_s": [0.0, 1.0], "sensor": [1.0, 2.0]}))
        self.column_roles = {"sensor": "pressure", "time_s": "time"}
        self.notifications = DummyNotifications()

        self.active_column_var = DummyVar("sensor")
        self.filter_output_name_var = DummyVar("")
        self.filter_min_var = DummyVar("0")
        self.filter_max_var = DummyVar("2")
        self.keep_missing_var = DummyVar(False)

        self.signal_filter_operation_var = DummyVar("moving_average")
        self.signal_filter_name_var = DummyVar("custom_smooth")
        self.signal_filter_window_var = DummyVar("5")
        self.signal_filter_alpha_var = DummyVar("0.3")
        self.signal_filter_cutoff_var = DummyVar("10.0")
        self.signal_filter_cutoff_high_var = DummyVar("20.0")
        self.signal_filter_spacing_var = DummyVar("0.1")
        self.signal_filter_order_var = DummyVar("4")

        self.resample_time_var = DummyVar("time_s")
        self.resample_spacing_var = DummyVar("0.25")

        self.derived_operation_var = DummyVar("delta")
        self.derived_name_var = DummyVar("sensor_delta")
        self.derived_reference_var = DummyVar("Index")
        self.derived_window_var = DummyVar("3")

        self.fft_reference_var = DummyVar("Index")
        self.frequency_analysis_var = DummyVar("FFT Amplitude")
        self.fft_sample_spacing_var = DummyVar("0.01")
        self.fft_window_var = DummyVar("hann")
        self.fft_detrend_var = DummyVar(True)
        self.welch_segment_length_var = DummyVar("128")
        self.welch_overlap_fraction_var = DummyVar("0.5")
        self.frequency_compare_var = DummyVar("sensor")

        self.cycle_length_var = DummyVar("10")
        self.cycle_max_cycles_var = DummyVar("")
        self.cycle_mode_var = DummyVar("fixed_length")
        self.cycle_reference_var = DummyVar("Index")
        self.cycle_threshold_var = DummyVar("0.0")
        self.cycle_prominence_var = DummyVar("0.2")

        self.replace_calls = []
        self.render_fft_calls = []
        self.render_spectrogram_calls = []
        self.render_cycle_calls = []

    @contextmanager
    def _error_dialog(self, _title):
        failed = []
        try:
            yield failed
        except Exception as error:  # pragma: no cover - mirrors production behavior
            failed.append(error)

    def _replace_working_frame(self, dataframe, role_overrides=None, focus_column=None):
        self.replace_calls.append(
            {
                "dataframe": dataframe,
                "role_overrides": role_overrides,
                "focus_column": focus_column,
            }
        )

    def _render_fft_result(self, result):
        self.render_fft_calls.append(result)

    def _render_spectrogram_result(self, result):
        self.render_spectrogram_calls.append(result)

    def _render_cycle_result(self, result):
        self.render_cycle_calls.append(result)

    def _get_cycle_time_column(self):
        return "time_s"


def test_apply_filter_warns_without_active_column(monkeypatch):
    workspace = DummyWorkspace()
    workspace.active_column_var.set("")

    handlers.apply_filter(workspace)

    assert len(workspace.notifications.warning_messages) == 1
    assert "active analysis column" in workspace.notifications.warning_messages[0][0]
    assert workspace.replace_calls == []


def test_apply_filter_replaces_frame_with_role_override(monkeypatch):
    workspace = DummyWorkspace()
    updated = workspace.session.working_frame.assign(sensor_filt=[1.0, 1.5])

    monkeypatch.setattr(
        handlers,
        "build_simple_filter_update",
        lambda *args, **kwargs: FrameUpdate(updated),
    )

    handlers.apply_filter(workspace)

    assert len(workspace.replace_calls) == 1
    call = workspace.replace_calls[0]
    assert call["focus_column"] == "sensor_filt"
    assert call["role_overrides"] == {"sensor_filt": "pressure"}
    assert "Created sensor_filt from sensor using simple filtering" in workspace.notifications.success_messages


def test_apply_signal_filter_parses_ui_values_and_clears_name(monkeypatch):
    workspace = DummyWorkspace()
    captured = {}

    def fake_update(*args, **kwargs):
        captured.update(kwargs)
        return FrameUpdate(workspace.session.working_frame.assign(custom_smooth=[1.0, 2.0]))

    monkeypatch.setattr(handlers, "build_signal_filter_update", fake_update)

    handlers.apply_signal_filter(workspace)

    assert captured["window_size"] == 5
    assert captured["alpha"] == 0.3
    assert captured["cutoff_hz"] == 10.0
    assert captured["sample_spacing"] == 0.1
    assert captured["filter_order"] == 4
    assert workspace.signal_filter_name_var.get() == ""


def test_apply_signal_filter_bandpass_passes_cutoff_pair(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("butterworth_bandpass")
    workspace.signal_filter_cutoff_var.set("5.0")
    workspace.signal_filter_cutoff_high_var.set("20.0")
    workspace.signal_filter_spacing_var.set("0.1")
    workspace.signal_filter_order_var.set("4")
    captured = {}

    def fake_update(*args, **kwargs):
        captured.update(kwargs)
        return FrameUpdate(workspace.session.working_frame.assign(bandpass=[1.0, 2.0]))

    monkeypatch.setattr(handlers, "build_signal_filter_update", fake_update)

    handlers.apply_signal_filter(workspace)

    assert captured["cutoff_hz"] == [5.0, 20.0]
    assert workspace.signal_filter_name_var.get() == ""


def test_apply_resample_warns_for_index_time_column(monkeypatch):
    workspace = DummyWorkspace()
    workspace.resample_time_var.set("Index")

    handlers.apply_resample(workspace)

    assert len(workspace.notifications.warning_messages) == 1
    assert "time column" in workspace.notifications.warning_messages[0][0]
    assert workspace.replace_calls == []


def test_apply_resample_replaces_working_frame(monkeypatch):
    workspace = DummyWorkspace()
    resampled = workspace.session.working_frame.copy()

    monkeypatch.setattr(handlers, "resample_to_uniform", lambda *args, **kwargs: resampled)

    handlers.apply_resample(workspace)

    assert len(workspace.replace_calls) == 1
    assert any("Resampled to uniform grid" in msg for msg in workspace.notifications.success_messages)


def test_apply_derived_signal_converts_time_role_to_signal(monkeypatch):
    workspace = DummyWorkspace()
    workspace.active_column_var.set("time_s")
    workspace.derived_name_var.set("time_delta")
    updated = workspace.session.working_frame.assign(time_delta=[0.0, 1.0])

    monkeypatch.setattr(
        handlers,
        "build_derived_signal_update",
        lambda *args, **kwargs: FrameUpdate(updated),
    )

    handlers.apply_derived_signal(workspace)

    call = workspace.replace_calls[0]
    assert call["role_overrides"] == {"time_delta": "signal"}
    assert workspace.derived_name_var.get() == ""


def test_compute_fft_fft_branch_renders_result(monkeypatch):
    workspace = DummyWorkspace()
    fft_result = SimpleNamespace(analysis_name="FFT Amplitude", window="hann")
    monkeypatch.setattr(handlers, "compute_fft_spectrum", lambda **kwargs: fft_result)

    handlers.compute_fft(workspace)

    assert workspace.render_fft_calls == [fft_result]
    assert len(workspace.notifications.success_messages) == 1
    assert "Computed FFT Amplitude" in workspace.notifications.success_messages[0]


def test_compute_fft_spectrogram_branch_renders_spectrogram(monkeypatch):
    workspace = DummyWorkspace()
    workspace.frequency_analysis_var.set("Spectrogram")
    spectrogram_result = SimpleNamespace(segment_length=128, sampling_frequency=100.0)
    monkeypatch.setattr(handlers, "compute_spectrogram", lambda **kwargs: spectrogram_result)

    handlers.compute_fft(workspace)

    assert workspace.render_spectrogram_calls == [spectrogram_result]
    assert workspace.render_fft_calls == []
    assert "Spectrogram" in workspace.notifications.success_messages[0]


def test_compute_cycle_analysis_fixed_length_renders_result(monkeypatch):
    workspace = DummyWorkspace()
    cycle_result = SimpleNamespace(cycle_count=3, cycle_length=10)
    monkeypatch.setattr(handlers, "compute_fixed_length_cycle_analysis", lambda *args, **kwargs: cycle_result)

    handlers.compute_cycle_analysis(workspace)

    assert workspace.render_cycle_calls == [cycle_result]
    assert "Analyzed 3 cycles" in workspace.notifications.success_messages[0]


# ---------------------------------------------------------------------------
# Preflight blocking — signal filter
# ---------------------------------------------------------------------------

def test_apply_signal_filter_butterworth_blocked_when_sample_spacing_zero(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("butterworth_lowpass")
    workspace.signal_filter_spacing_var.set("0.0")
    workspace.signal_filter_cutoff_var.set("10.0")
    workspace.signal_filter_order_var.set("4")
    handlers.apply_signal_filter(workspace)

    assert len(workspace.notifications.warning_messages) == 1
    warning_message, warning_details = workspace.notifications.warning_messages[0]
    assert "Signal Filter" in warning_message
    assert warning_details is not None
    assert "sample_spacing" in warning_details
    assert workspace.replace_calls == []


def test_apply_signal_filter_butterworth_blocked_when_cutoff_zero(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("butterworth_highpass")
    workspace.signal_filter_spacing_var.set("0.01")
    workspace.signal_filter_cutoff_var.set("0.0")
    workspace.signal_filter_order_var.set("4")
    handlers.apply_signal_filter(workspace)

    assert any(
        details is not None and "cutoff_hz" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.replace_calls == []


def test_apply_signal_filter_bandpass_blocked_when_high_cutoff_zero(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("butterworth_bandpass")
    workspace.signal_filter_spacing_var.set("0.01")
    workspace.signal_filter_cutoff_var.set("5.0")
    workspace.signal_filter_cutoff_high_var.set("0.0")
    workspace.signal_filter_order_var.set("4")
    handlers.apply_signal_filter(workspace)

    assert any(
        details is not None and "cutoff_hz_high" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.replace_calls == []


def test_apply_signal_filter_bandpass_blocked_when_high_cutoff_below_low_cutoff(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("butterworth_bandpass")
    workspace.signal_filter_spacing_var.set("0.01")
    workspace.signal_filter_cutoff_var.set("20.0")
    workspace.signal_filter_cutoff_high_var.set("10.0")
    workspace.signal_filter_order_var.set("4")
    handlers.apply_signal_filter(workspace)

    assert any(
        details is not None and "must be greater than 'cutoff_hz'" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.replace_calls == []


def test_apply_signal_filter_moving_average_blocked_when_window_zero(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("moving_average")
    workspace.signal_filter_window_var.set("0")
    handlers.apply_signal_filter(workspace)

    assert any(
        details is not None and "window_size" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.replace_calls == []


def test_apply_signal_filter_exp_smoothing_blocked_when_alpha_zero(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("exponential_smoothing")
    workspace.signal_filter_alpha_var.set("0.0")
    handlers.apply_signal_filter(workspace)

    assert any(
        details is not None and "alpha" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.replace_calls == []


def test_apply_signal_filter_butterworth_proceeds_with_valid_params(monkeypatch):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set("butterworth_lowpass")
    workspace.signal_filter_spacing_var.set("0.01")
    workspace.signal_filter_cutoff_var.set("10.0")
    workspace.signal_filter_order_var.set("4")
    monkeypatch.setattr(
        handlers,
        "build_signal_filter_update",
        lambda *args, **kwargs: FrameUpdate(workspace.session.working_frame),
    )

    handlers.apply_signal_filter(workspace)

    assert len(workspace.replace_calls) == 1


# ---------------------------------------------------------------------------
# Preflight blocking — frequency analysis
# ---------------------------------------------------------------------------

def test_compute_fft_blocked_when_sample_spacing_zero(monkeypatch):
    workspace = DummyWorkspace()
    workspace.fft_sample_spacing_var.set("0.0")
    handlers.compute_fft(workspace)

    assert any(
        details is not None and "sample_spacing" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.render_fft_calls == []


def test_compute_fft_transfer_blocked_when_comparison_missing(monkeypatch):
    workspace = DummyWorkspace()
    workspace.frequency_analysis_var.set("Transfer Estimate")
    workspace.frequency_compare_var.set("")
    workspace.fft_sample_spacing_var.set("0.01")
    workspace.welch_segment_length_var.set("256")
    handlers.compute_fft(workspace)

    assert any(
        details is not None and "comparison_signal" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.render_fft_calls == []


def test_compute_fft_coherence_blocked_when_comparison_missing(monkeypatch):
    workspace = DummyWorkspace()
    workspace.frequency_analysis_var.set("Coherence")
    workspace.frequency_compare_var.set("")
    workspace.fft_sample_spacing_var.set("0.01")
    workspace.welch_segment_length_var.set("256")
    handlers.compute_fft(workspace)

    assert any(
        details is not None and "comparison_signal" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.render_fft_calls == []


# ---------------------------------------------------------------------------
# Preflight blocking — cycle analysis
# ---------------------------------------------------------------------------

def test_compute_cycle_analysis_blocked_when_cycle_length_zero(monkeypatch):
    workspace = DummyWorkspace()
    workspace.cycle_mode_var.set("fixed_length")
    workspace.cycle_length_var.set("0")
    handlers.compute_cycle_analysis(workspace)

    assert any(
        details is not None and "cycle_length" in details
        for _message, details in workspace.notifications.warning_messages
    )
    assert workspace.render_cycle_calls == []


def test_compute_cycle_analysis_rising_edge_not_blocked_by_preflight(monkeypatch):
    workspace = DummyWorkspace()
    workspace.cycle_mode_var.set("rising_edge")
    workspace.cycle_reference_var.set("Index")
    workspace.cycle_threshold_var.set("0.0")
    workspace.cycle_length_var.set("0")
    cycle_result = SimpleNamespace(cycle_count=2, cycle_length=0)
    monkeypatch.setattr(handlers, "detect_rising_edge_cycle_ranges", lambda *args, **kwargs: [])
    monkeypatch.setattr(handlers, "compute_cycle_analysis_from_ranges", lambda *args, **kwargs: cycle_result)

    handlers.compute_cycle_analysis(workspace)

    # rising_edge has no required_positive params so preflight does not block
    assert workspace.render_cycle_calls == [cycle_result]
