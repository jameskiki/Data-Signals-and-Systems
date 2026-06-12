"""Integration-style workflow tests spanning preparation and analysis layers."""

from contextlib import contextmanager
from types import SimpleNamespace

import pandas as pd

from Source.analysis_app import handlers
from Source.datapreparation_app import actions as dataprep_actions
from Source.datapreparation_app import preparation
from Source.datapreparation_app.datasets import register_dataset


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyNotifications:
    def __init__(self):
        self.success_messages = []

    def success(self, message):
        self.success_messages.append(message)


class PrepIntegrationApp:
    """Small app façade for preparation workflow integration tests."""

    def __init__(self):
        self.data_frames = {}
        self.dataset_contexts = {}
        self.dataset_table = None
        self.notifications = DummyNotifications()
        self._prep_refresh_count = 0
        self._selected_path = None

        self.session = SimpleNamespace(
            output_dataset_name="prepared_dataset",
            selected_columns=[],
            row_range_start="",
            row_range_end="",
            split_prefix="cycle",
        )

    def _get_single_selected_file_path(self, _message=None):
        return self._selected_path

    def get_row_range_for_preparation(self):
        return self.session.row_range_start, self.session.row_range_end

    def _get_row_range_filtered_frame(self, dataframe: pd.DataFrame, _column_roles: dict[str, str]) -> pd.DataFrame:
        start_text = self.session.row_range_start
        end_text = self.session.row_range_end
        if not start_text and not end_text:
            return dataframe
        start_idx = int(start_text) if start_text else 0
        end_idx = int(end_text) if end_text else len(dataframe)
        return dataframe.iloc[start_idx:end_idx].reset_index(drop=True)

    def _refresh_dataset_preparation_views(self):
        self._prep_refresh_count += 1


class AnalysisWorkspaceStub:
    """Workspace façade for running handler functions in workflow tests."""

    def __init__(self, dataframe: pd.DataFrame, column_roles: dict[str, str]):
        self.session = SimpleNamespace(working_frame=dataframe)
        self.column_roles = dict(column_roles)
        self.notifications = DummyNotifications()

        self.active_column_var = DummyVar("sensor")
        self.filter_output_name_var = DummyVar("")
        self.filter_min_var = DummyVar("0.0")
        self.filter_max_var = DummyVar("1.0")
        self.keep_missing_var = DummyVar(False)

        self.resample_time_var = DummyVar("time_s")
        self.resample_spacing_var = DummyVar("0.05")

        self.derived_operation_var = DummyVar("delta")
        self.derived_name_var = DummyVar("sensor_delta")
        self.derived_reference_var = DummyVar("Index")
        self.derived_window_var = DummyVar("3")

        self.signal_filter_operation_var = DummyVar("moving_average")
        self.signal_filter_name_var = DummyVar("")
        self.signal_filter_window_var = DummyVar("5")
        self.signal_filter_alpha_var = DummyVar("0.2")
        self.signal_filter_cutoff_var = DummyVar("8.0")
        self.signal_filter_spacing_var = DummyVar("0.01")
        self.signal_filter_order_var = DummyVar("4")

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

    @contextmanager
    def _error_dialog(self, _title):
        failed = []
        try:
            yield failed
        except Exception as error:  # pragma: no cover
            failed.append(error)

    def _replace_working_frame(self, dataframe, role_overrides=None, focus_column=None):
        self.session.working_frame = dataframe
        self.replace_calls.append(
            {
                "dataframe": dataframe,
                "role_overrides": role_overrides,
                "focus_column": focus_column,
            }
        )

    def _render_fft_result(self, result):
        self.render_fft_calls.append(result)

    def _render_spectrogram_result(self, _result):
        return None

    def _render_cycle_result(self, _result):
        return None

    def _get_cycle_time_column(self):
        return "time_s"


def test_prepare_dataset_then_apply_filter_workflow():
    app = PrepIntegrationApp()
    source_path = "C:/tmp/source.csv"
    source_frame = pd.DataFrame(
        {
            "time_s": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
            "sensor": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 0.8, 0.6, 0.4, 0.2],
            "meta": [1] * 10,
        }
    )
    register_dataset(
        app,
        source_path,
        source_frame,
        source_paths=[source_path],
        description="source",
        column_roles={"time_s": "time", "sensor": "signal", "meta": "metadata"},
    )

    app._selected_path = source_path
    app.session.output_dataset_name = "integration_slice"
    app.session.selected_columns = ["time_s", "sensor"]
    app.session.row_range_start = "2"
    app.session.row_range_end = "8"

    prepared_path = preparation.create_prepared_dataset(app)

    assert prepared_path is not None
    assert prepared_path in app.data_frames
    assert list(app.data_frames[prepared_path].columns) == ["time_s", "sensor"]
    assert len(app.data_frames[prepared_path]) == 6
    assert app.dataset_contexts[prepared_path].column_roles == {"time_s": "time", "sensor": "signal"}

    workspace = AnalysisWorkspaceStub(app.data_frames[prepared_path], app.dataset_contexts[prepared_path].column_roles)
    workspace.active_column_var.set("sensor")
    workspace.filter_min_var.set("0.25")
    workspace.filter_max_var.set("0.75")

    handlers.apply_filter(workspace)

    assert len(workspace.replace_calls) == 1
    assert "sensor_filt" in workspace.replace_calls[0]["dataframe"].columns
    assert workspace.replace_calls[0]["role_overrides"] == {"sensor_filt": "signal"}


def test_demo_load_prepare_then_fft_workflow(monkeypatch):
    app = PrepIntegrationApp()

    demo_path = dataprep_actions._load_demo_dataset(app, "spectral_reference", show_message=False)
    app._selected_path = demo_path
    app.session.output_dataset_name = "demo_subset"
    app.session.selected_columns = ["time_s", "measured_signal"]

    prepared_path = preparation.create_prepared_dataset(app)
    prepared_frame = app.data_frames[prepared_path]
    prepared_roles = app.dataset_contexts[prepared_path].column_roles

    workspace = AnalysisWorkspaceStub(prepared_frame, prepared_roles)
    workspace.active_column_var.set("measured_signal")
    fft_result = SimpleNamespace(analysis_name="FFT Amplitude", window="hann")
    monkeypatch.setattr(handlers, "compute_fft_spectrum", lambda **kwargs: fft_result)

    handlers.compute_fft(workspace)

    assert workspace.render_fft_calls == [fft_result]
    assert len(workspace.notifications.success_messages) == 1
    assert "Computed FFT Amplitude" in workspace.notifications.success_messages[0]


def test_split_dataset_then_resample_workflow():
    app = PrepIntegrationApp()
    source_path = "C:/tmp/cycles.csv"
    source_frame = pd.DataFrame(
        {
            "time_s": [i * 0.1 for i in range(20)],
            "sensor": [float(i % 5) for i in range(20)],
        }
    )
    register_dataset(
        app,
        source_path,
        source_frame,
        source_paths=[source_path],
        description="cycles",
        column_roles={"time_s": "time", "sensor": "signal"},
    )

    app._selected_path = source_path
    created_paths = preparation.split_selected_dataset(app, raw_ranges_text="0:10\n10:20", prefix="seg")

    assert len(created_paths) == 2
    first_split = created_paths[0]
    assert len(app.data_frames[first_split]) == 10

    workspace = AnalysisWorkspaceStub(app.data_frames[first_split], app.dataset_contexts[first_split].column_roles)
    workspace.resample_time_var.set("time_s")
    workspace.resample_spacing_var.set("0.05")

    handlers.apply_resample(workspace)

    assert len(workspace.replace_calls) == 1
    assert any("Resampled to uniform grid" in msg for msg in workspace.notifications.success_messages)
