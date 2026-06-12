"""Tests for analysis_app.refresh sample-spacing defaults."""

from types import SimpleNamespace

import numpy as np
import pandas as pd

from Source.analysis_app.refresh import (
    _apply_default_analysis_lengths,
    _apply_default_sample_spacing,
    infer_cycle_length_samples,
    infer_sample_spacing,
    infer_welch_segment_length,
)


class DummyVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class DummyWorkspace:
    def __init__(
        self,
        frame: pd.DataFrame,
        signal_spacing_value: str,
        fft_spacing_value: str = "",
        resample_time_value: str = "time_s",
        resample_spacing_value: str = "",
    ) -> None:
        self.session = SimpleNamespace(working_frame=frame)
        self.column_roles = {"time_s": "time", "sensor": "signal"}
        self.signal_filter_spacing_var = DummyVar(signal_spacing_value)
        self.fft_sample_spacing_var = DummyVar(fft_spacing_value)
        self.resample_time_var = DummyVar(resample_time_value)
        self.resample_spacing_var = DummyVar(resample_spacing_value)
        self.active_column_var = DummyVar("sensor")
        self.welch_segment_length_var = DummyVar("256")
        self.cycle_length_var = DummyVar("100")
        self._inferred_fields: set[str] = set()
        self._user_edited_fields: set[str] = set()

    def _set_inferred_field_value(self, field_name: str, variable: DummyVar, value: str) -> None:
        variable.set(value)
        self._inferred_fields.add(field_name)
        self._user_edited_fields.discard(field_name)


def test_infer_sample_spacing_numeric_column() -> None:
    frame = pd.DataFrame({"time_s": [0.0, 0.1, 0.2, 0.3], "sensor": [1.0, 2.0, 3.0, 4.0]})

    spacing = infer_sample_spacing(frame, "time_s")

    assert spacing == 0.1


def test_infer_sample_spacing_datetime_column_seconds() -> None:
    frame = pd.DataFrame(
        {
            "time_s": pd.to_datetime([
                "2026-01-01 00:00:00.000",
                "2026-01-01 00:00:00.500",
                "2026-01-01 00:00:01.000",
            ]),
            "sensor": [1.0, 2.0, 3.0],
        }
    )

    spacing = infer_sample_spacing(frame, "time_s")

    assert spacing == 0.5


def test_infer_sample_spacing_returns_none_for_non_varying_axis() -> None:
    frame = pd.DataFrame({"time_s": [1.0, 1.0, 1.0], "sensor": [1.0, 2.0, 3.0]})

    spacing = infer_sample_spacing(frame, "time_s")

    assert spacing is None


def test_apply_default_sample_spacing_sets_when_invalid() -> None:
    frame = pd.DataFrame({"time_s": [0.0, 0.02, 0.04], "sensor": [1.0, 2.0, 3.0]})
    workspace = DummyWorkspace(frame, signal_spacing_value="0.0")

    _apply_default_sample_spacing(workspace, ["time_s", "sensor"])

    assert workspace.signal_filter_spacing_var.get() == "0.02"
    assert "signal_filter_spacing" in workspace._inferred_fields


def test_apply_default_sample_spacing_keeps_valid_user_value() -> None:
    frame = pd.DataFrame({"time_s": [0.0, 0.02, 0.04], "sensor": [1.0, 2.0, 3.0]})
    workspace = DummyWorkspace(frame, signal_spacing_value="0.5")

    _apply_default_sample_spacing(workspace, ["time_s", "sensor"])

    assert workspace.signal_filter_spacing_var.get() == "0.5"


def test_apply_default_sample_spacing_sets_fft_spacing_on_first_open() -> None:
    # Fresh workspace has never been user-set, so inference should overwrite the "1.0" default.
    frame = pd.DataFrame({"time_s": [0.0, 0.02, 0.04], "sensor": [1.0, 2.0, 3.0]})
    workspace = DummyWorkspace(frame, signal_spacing_value="0.02", fft_spacing_value="1.0")

    _apply_default_sample_spacing(workspace, ["time_s", "sensor"])

    assert workspace.fft_sample_spacing_var.get() == "0.02"
    assert "fft_sample_spacing" in workspace._inferred_fields


def test_apply_default_sample_spacing_keeps_fft_spacing_when_user_set() -> None:
    # Simulate user edit: field is in _user_edited_fields so _is_user_set returns True.
    frame = pd.DataFrame({"time_s": [0.0, 0.02, 0.04], "sensor": [1.0, 2.0, 3.0]})
    workspace = DummyWorkspace(frame, signal_spacing_value="0.02", fft_spacing_value="0.5")
    workspace._user_edited_fields.add("fft_sample_spacing")

    _apply_default_sample_spacing(workspace, ["time_s", "sensor"])

    assert workspace.fft_sample_spacing_var.get() == "0.5"


def test_apply_default_sample_spacing_sets_resample_spacing_for_selected_time_column() -> None:
    # Fresh workspace: resample_spacing not yet user-set, so inference should fill it.
    frame = pd.DataFrame({"time_s": [0.0, 0.02, 0.04], "sensor": [1.0, 2.0, 3.0]})
    workspace = DummyWorkspace(
        frame,
        signal_spacing_value="0.02",
        fft_spacing_value="0.02",
        resample_time_value="time_s",
        resample_spacing_value="1.0",
    )

    _apply_default_sample_spacing(workspace, ["time_s", "sensor"])

    assert workspace.resample_spacing_var.get() == "0.02"
    assert "resample_spacing" in workspace._inferred_fields


def test_apply_default_sample_spacing_keeps_resample_spacing_when_user_set() -> None:
    frame = pd.DataFrame({"time_s": [0.0, 0.02, 0.04], "sensor": [1.0, 2.0, 3.0]})
    workspace = DummyWorkspace(
        frame,
        signal_spacing_value="0.02",
        fft_spacing_value="0.02",
        resample_time_value="time_s",
        resample_spacing_value="0.5",
    )
    workspace._user_edited_fields.add("resample_spacing")

    _apply_default_sample_spacing(workspace, ["time_s", "sensor"])

    assert workspace.resample_spacing_var.get() == "0.5"


def test_apply_default_sample_spacing_skips_resample_when_time_is_index() -> None:
    frame = pd.DataFrame({"time_s": [0.0, 0.02, 0.04], "sensor": [1.0, 2.0, 3.0]})
    workspace = DummyWorkspace(
        frame,
        signal_spacing_value="0.02",
        fft_spacing_value="0.02",
        resample_time_value="Index",
        resample_spacing_value="0.0",
    )

    _apply_default_sample_spacing(workspace, ["time_s", "sensor"])

    assert workspace.resample_spacing_var.get() == "0.0"


def test_infer_welch_segment_length_prefers_power_of_two_under_target() -> None:
    assert infer_welch_segment_length(1000) == 256
    assert infer_welch_segment_length(200) == 128
    assert infer_welch_segment_length(12) == 8


def test_infer_cycle_length_samples_detects_known_period() -> None:
    sample_count = 400
    period_samples = 20
    x = np.arange(sample_count)
    y = np.sin(2 * np.pi * x / period_samples)

    inferred = infer_cycle_length_samples(pd.Series(y))

    assert inferred is not None
    assert abs(inferred - period_samples) <= 1


def test_apply_default_analysis_lengths_sets_welch_and_cycle_when_defaulted() -> None:
    sample_count = 400
    period_samples = 20
    x = np.arange(sample_count)
    frame = pd.DataFrame({"time_s": x * 0.01, "sensor": np.sin(2 * np.pi * x / period_samples)})
    workspace = DummyWorkspace(frame, signal_spacing_value="0.01", fft_spacing_value="0.01")

    _apply_default_analysis_lengths(workspace, ["sensor"])

    assert workspace.welch_segment_length_var.get() == "256"
    inferred_cycle = int(workspace.cycle_length_var.get())
    assert abs(inferred_cycle - period_samples) <= 1
    assert "welch_segment_length" in workspace._inferred_fields
    assert "cycle_length" in workspace._inferred_fields


def test_apply_default_analysis_lengths_preserves_user_values() -> None:
    sample_count = 400
    period_samples = 20
    x = np.arange(sample_count)
    frame = pd.DataFrame({"time_s": x * 0.01, "sensor": np.sin(2 * np.pi * x / period_samples)})
    workspace = DummyWorkspace(frame, signal_spacing_value="0.01", fft_spacing_value="0.01")
    workspace.welch_segment_length_var.set("64")
    workspace.cycle_length_var.set("50")

    _apply_default_analysis_lengths(workspace, ["sensor"])

    assert workspace.welch_segment_length_var.get() == "64"
    assert workspace.cycle_length_var.get() == "50"
