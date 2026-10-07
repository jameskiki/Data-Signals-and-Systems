"""Focused tests for datapreparation_app.actions orchestration helpers."""

import os
from types import SimpleNamespace

import pandas as pd
import pytest

from Source.data_ops.io_ops import read_dataframe_parquet, write_dataframe_with_progress
from Source.datapreparation_app import actions
from Source.datapreparation_app.app import DataPreparationApp
from Source.datapreparation_app.datasets import DatasetContext
from Source.shared.plot_options import PlotStyle


class DummyNotifications:
    def __init__(self):
        self.success_messages = []
        self.warning_messages = []
        self.info_messages = []

    def success(self, message, details=None):
        self.success_messages.append(message if details is None else (message, details))

    def warning(self, message, details=None):
        self.warning_messages.append((message, details))

    def info(self, message, details=None):
        self.info_messages.append((message, details))


class DummyApp:
    def __init__(self):
        self.notifications = DummyNotifications()
        self.data_frames = {}
        self.dataset_contexts = {}
        self.session = SimpleNamespace(role_editor_column="", role_editor_value="")
        self.style_vars = SimpleNamespace(to_plot_style=lambda: PlotStyle())

        self.prep_views_refresh_count = 0
        self.selection_suppression_during_refresh = []
        self._suppress_dataset_selection_refresh = False
        self.loaded_selection = None
        self.set_role_column_calls = []
        self.set_role_value_calls = []
        self.propagated_role_updates = []

        self.split_options = None

        self.single_selected_path = None
        self.multiple_selected_paths = []
        self._analysis_workspaces = []
        self._comparison_windows = []
        self.root = object()

    def _refresh_dataset_preparation_views(self):
        self.prep_views_refresh_count += 1
        self.selection_suppression_during_refresh.append(self._suppress_dataset_selection_refresh)

    def _select_dataset_in_table_without_event_refresh(self, file_path):
        self._suppress_dataset_selection_refresh = True
        self.loaded_selection = file_path

    def _set_role_editor_column(self, value, update_var=False):
        self.set_role_column_calls.append((value, update_var))

    def _set_role_editor_value(self, value, update_var=False):
        self.set_role_value_calls.append((value, update_var))

    def _propagate_role_updates(self, dataset_path, column_roles):
        self.propagated_role_updates.append((dataset_path, dict(column_roles)))

    def _prompt_split_subframes_options(self):
        return self.split_options

    def _get_single_selected_file_path(self, _message):
        return self.single_selected_path

    def _get_multiple_selected_file_paths(self, _message):
        return self.multiple_selected_paths

    def _on_analysis_workspace_closed(self, _workspace):
        return None

    def _on_comparison_window_closed(self, _window):
        return None


def test_create_prepared_dataset_success(monkeypatch):
    app = DummyApp()
    monkeypatch.setattr(actions, "create_prepared_dataset_workflow", lambda _app: "C:/tmp/prepared.csv")

    actions.create_prepared_dataset(app)

    assert app.notifications.success_messages == ["Created dataset: prepared.csv"]


def test_create_prepared_dataset_reports_error(monkeypatch):
    app = DummyApp()
    errors = []

    def raise_error(_app):
        raise ValueError("bad config")

    monkeypatch.setattr(actions, "create_prepared_dataset_workflow", raise_error)
    monkeypatch.setattr(actions.messagebox, "showerror", lambda title, msg: errors.append((title, msg)))

    actions.create_prepared_dataset(app)

    assert errors == [("Create Dataset Error", "bad config")]
    assert app.notifications.success_messages == []


def test_split_selected_dataset_success(monkeypatch):
    app = DummyApp()
    app.split_options = {"prefix": "run", "ranges_text": "0:10\n10:20"}
    monkeypatch.setattr(actions, "split_selected_dataset_workflow", lambda *args, **kwargs: ["a", "b"]) 

    actions.split_selected_dataset(app)

    assert app.notifications.success_messages == ["Created 2 subframe dataset(s)"]


def test_split_selected_dataset_reports_error(monkeypatch):
    app = DummyApp()
    app.split_options = {"prefix": "run", "ranges_text": "0:10"}
    errors = []

    def raise_error(*args, **kwargs):
        raise RuntimeError("split failed")

    monkeypatch.setattr(actions, "split_selected_dataset_workflow", raise_error)
    monkeypatch.setattr(actions.messagebox, "showerror", lambda title, msg: errors.append((title, msg)))

    actions.split_selected_dataset(app)

    assert errors == [("Split Error", "split failed")]


def test_load_comparison_demo_set_loads_all_three_datasets(monkeypatch):
    app = DummyApp()
    refresh_calls = []
    selected_paths = []
    monkeypatch.setattr(actions, "refresh_dataset_table", lambda _app: refresh_calls.append(True))
    monkeypatch.setattr(actions, "select_dataset_in_table", lambda _app, path: selected_paths.append(path))

    loaded_paths = actions.load_comparison_demo_set(app)

    assert len(loaded_paths) == 3
    assert set(loaded_paths) == set(app.data_frames)
    assert all(path in app.dataset_contexts for path in loaded_paths)
    assert selected_paths == [loaded_paths[-1]]
    assert len(refresh_calls) == 1
    assert app.prep_views_refresh_count == 1
    assert app.notifications.success_messages[0][0] == "Comparison Validation Set Loaded"


def test_load_files_suppresses_selection_refresh_until_preview_refresh_finishes(monkeypatch):
    app = DummyApp()
    app.LOG_FILE_TYPES = []
    app.create_loading_dialog = lambda *args: (
        object(),
        *[SimpleNamespace(set=lambda _value: None) for _ in range(4)],
    )
    app.close_loading_dialog = lambda _dialog: None

    class ImmediateThread:
        def __init__(self, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(actions.filedialog, "askopenfilenames", lambda **_kwargs: ["C:/tmp/run.csv"])
    monkeypatch.setattr(
        actions.DataParser,
        "load_file",
        lambda _path, progress_callback=None: (pd.DataFrame({"signal": [1.0, 2.0]}), ",", "."),
    )
    monkeypatch.setattr(actions.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(actions, "refresh_dataset_table", lambda _app: None)
    monkeypatch.setattr(actions, "analyze_selected_dataframes", lambda *_args: "")

    actions.load_files(app)

    assert app.loaded_selection == "C:/tmp/run.csv"
    assert app.selection_suppression_during_refresh == [True]
    assert app._suppress_dataset_selection_refresh is False
    assert app.prep_views_refresh_count == 1


def test_dataset_selection_event_skips_already_refreshed_path():
    app = DataPreparationApp.__new__(DataPreparationApp)
    app._suppress_dataset_selection_refresh = False
    app._last_refreshed_dataset_path = "C:/tmp/run.csv"
    app._get_single_selected_file_path = lambda: "C:/tmp/run.csv"
    resets = []
    refreshes = []
    app._reset_row_range = lambda: resets.append(True)
    app._refresh_dataset_preparation_views = lambda: refreshes.append(True)

    DataPreparationApp._handle_dataset_combo_changed(app)

    assert resets == []
    assert refreshes == []


def test_export_clean_data_warns_without_datasets(monkeypatch):
    app = DummyApp()

    actions.export_clean_data(app)

    assert app.notifications.warning_messages == [("No data loaded", None)]


def test_export_clean_data_success(monkeypatch):
    app = DummyApp()
    app.data_frames = {
        "C:/tmp/a.csv": pd.DataFrame({"x": [1, 2]}),
        "C:/tmp/b.csv": pd.DataFrame({"x": [3, 4]}),
    }
    app.multiple_selected_paths = ["C:/tmp/b.csv"]

    monkeypatch.setattr(actions, "DatasetExportFormatDialog", lambda *args: SimpleNamespace(result="csv"))
    monkeypatch.setattr(actions.filedialog, "askdirectory", lambda title: "C:/out")
    monkeypatch.setattr(actions.simpledialog, "askstring", lambda *args, **kwargs: "custom")
    export_calls = []
    monkeypatch.setattr(
        actions,
        "export_clean_dataframes",
        lambda frames, out_dir, filename_prefix, **kwargs: export_calls.append((frames, out_dir, filename_prefix)) or 1,
    )

    actions.export_clean_data(app)

    assert list(export_calls[0][0]) == ["C:/tmp/b.csv"]
    assert export_calls[0][1:] == ("C:/out", "custom")
    assert app.notifications.success_messages == ["Exported 1 selected file(s)"]


def test_export_clean_data_rejects_invalid_prefix(monkeypatch):
    app = DummyApp()
    app.data_frames = {"C:/tmp/a.csv": pd.DataFrame({"x": [1, 2]})}
    app.multiple_selected_paths = ["C:/tmp/a.csv"]

    monkeypatch.setattr(actions, "DatasetExportFormatDialog", lambda *args: SimpleNamespace(result="csv"))
    directory_prompts = []
    monkeypatch.setattr(actions.filedialog, "askdirectory", lambda title: directory_prompts.append(title) or "C:/out")
    monkeypatch.setattr(actions.simpledialog, "askstring", lambda *args, **kwargs: "bad/name")

    actions.export_clean_data(app)

    assert app.notifications.warning_messages == [
        ('The filename prefix cannot contain < > : " / \\ | ? * or control characters.', None)
    ]
    assert directory_prompts == []


def test_export_clean_data_parquet_preserves_assigned_roles(tmp_path, monkeypatch):
    app = DummyApp()
    app.data_frames = {"run.csv": pd.DataFrame({"signal": [1.0, None, 3.0]})}
    app.dataset_contexts = {"run.csv": DatasetContext(column_roles={"signal": "metadata"})}
    app.multiple_selected_paths = ["run.csv"]
    monkeypatch.setattr(actions, "DatasetExportFormatDialog", lambda *args: SimpleNamespace(result="parquet"))
    monkeypatch.setattr(actions.simpledialog, "askstring", lambda *args, **kwargs: "clean")
    monkeypatch.setattr(actions.filedialog, "askdirectory", lambda **kwargs: str(tmp_path))

    actions.export_clean_data(app)

    restored = read_dataframe_parquet(str(tmp_path / "clean_run.parquet"))
    assert restored["signal"].tolist() == [1.0, 3.0]
    assert restored.attrs["evaldata_column_roles"] == {"signal": "metadata"}
    assert app.notifications.success_messages == ["Exported 1 selected file(s)"]


def test_export_clean_data_format_cancel_stops_export(monkeypatch):
    app = DummyApp()
    app.data_frames = {"run.csv": pd.DataFrame({"signal": [1.0]})}
    app.multiple_selected_paths = ["run.csv"]
    monkeypatch.setattr(actions, "DatasetExportFormatDialog", lambda *args: SimpleNamespace(result=None))
    monkeypatch.setattr(
        actions.simpledialog, "askstring",
        lambda *args, **kwargs: pytest.fail("Cancelled format choice must stop the workflow"),
    )
    actions.export_clean_data(app)
    assert app.notifications.success_messages == []


def test_export_clean_data_reports_write_failure(monkeypatch):
    app = DummyApp()
    app.data_frames = {"run.csv": pd.DataFrame({"signal": [1.0]})}
    app.multiple_selected_paths = ["run.csv"]
    monkeypatch.setattr(actions, "DatasetExportFormatDialog", lambda *args: SimpleNamespace(result="parquet"))
    monkeypatch.setattr(actions.simpledialog, "askstring", lambda *args, **kwargs: "clean")
    monkeypatch.setattr(actions.filedialog, "askdirectory", lambda **kwargs: "output")

    def fail_export(*args, **kwargs):
        raise OSError("Disk full")

    monkeypatch.setattr(actions, "export_clean_dataframes", fail_export)
    errors = []
    monkeypatch.setattr(actions.messagebox, "showerror", lambda *args: errors.append(args))
    actions.export_clean_data(app)
    assert errors == [("Export Error", "Disk full")]
    assert app.notifications.success_messages == []


def _configure_immediate_dataset_workflow(app, monkeypatch):
    app.create_loading_dialog = lambda *args, **kwargs: (
        object(), *[SimpleNamespace(set=lambda _value: None) for _ in range(4)],
    )
    app.close_loading_dialog = lambda _dialog: None

    class ImmediateThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(actions.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(actions, "refresh_dataset_table", lambda _app: None)
    monkeypatch.setattr(actions, "select_dataset_in_table", lambda _app, _path: None)


@pytest.mark.parametrize("extension", [".csv", ".parquet"])
def test_merge_save_wires_format_and_roles(tmp_path, monkeypatch, extension):
    app = DummyApp()
    app.data_frames = {
        "a.csv": pd.DataFrame({"signal": [1.5]}),
        "b.csv": pd.DataFrame({"signal": [2.5]}),
    }
    app.dataset_contexts = {
        path: DatasetContext(column_roles={"signal": "metadata"})
        for path in app.data_frames
    }
    app.multiple_selected_paths = list(app.data_frames)
    _configure_immediate_dataset_workflow(app, monkeypatch)
    path = str(tmp_path / ("merged" + extension))
    monkeypatch.setattr(actions, "ask_dataset_save_path", lambda *_: path)

    actions.merge_selected_files(app)

    restored, _, _ = actions.DataParser.load_file(path)
    assert restored["signal"].tolist() == [1.5, 2.5]
    assert app.dataset_contexts[path].column_roles == {"signal": "metadata"}
    if extension == ".parquet":
        assert restored.attrs["evaldata_column_roles"] == {"signal": "metadata"}
    assert len(app.notifications.success_messages) == 1


def test_load_files_restores_parquet_roles_with_csv_in_same_batch(tmp_path, monkeypatch):
    app = DummyApp()
    app.LOG_FILE_TYPES = []
    _configure_immediate_dataset_workflow(app, monkeypatch)
    parquet_path = str(tmp_path / "binary.parquet")
    csv_path = str(tmp_path / "text.csv")
    frame = pd.DataFrame({"signal": [1.5, 2.5]})
    write_dataframe_with_progress(frame, parquet_path, column_roles={"signal": "metadata"})
    write_dataframe_with_progress(frame, csv_path)
    monkeypatch.setattr(actions.filedialog, "askopenfilenames", lambda **_: [parquet_path, csv_path])

    actions.load_files(app)

    assert app.dataset_contexts[parquet_path].column_roles == {"signal": "metadata"}
    assert app.dataset_contexts[csv_path].column_roles == {"signal": "signal"}
    assert set(app.data_frames) == {parquet_path, csv_path}
    assert "Parquet" in app.notifications.info_messages[0][1]


def test_unload_selected_files_removes_context_and_data(monkeypatch):
    app = DummyApp()
    app.multiple_selected_paths = ["C:/tmp/a.csv", "C:/tmp/b.csv"]
    app.data_frames = {
        "C:/tmp/a.csv": pd.DataFrame({"x": [1]}),
        "C:/tmp/b.csv": pd.DataFrame({"x": [2]}),
    }
    app.dataset_contexts = {
        "C:/tmp/a.csv": DatasetContext(source_paths=["C:/tmp/a.csv"]),
        "C:/tmp/b.csv": DatasetContext(source_paths=["C:/tmp/b.csv"]),
    }
    refresh_calls = []
    monkeypatch.setattr(actions, "refresh_dataset_table", lambda _app: refresh_calls.append(True))

    actions.unload_selected_files(app)

    assert app.data_frames == {}
    assert app.dataset_contexts == {}
    assert len(refresh_calls) == 1
    assert app.prep_views_refresh_count == 1
    assert app.notifications.success_messages == ["Unloaded 2 file(s)"]


def test_apply_selected_column_role_updates_context_and_resets_editor(monkeypatch):
    app = DummyApp()
    app.single_selected_path = "C:/tmp/a.csv"
    app.session.role_editor_column = "sensor"
    app.session.role_editor_value = "signal"
    app.data_frames = {"C:/tmp/a.csv": pd.DataFrame({"old": [0.0], "sensor": [1.0]})}
    app.dataset_contexts = {"C:/tmp/a.csv": DatasetContext(column_roles={"old": "time"})}

    actions.apply_selected_column_role(app)

    assert app.dataset_contexts["C:/tmp/a.csv"].column_roles["sensor"] == "signal"
    assert app.propagated_role_updates == [
        ("C:/tmp/a.csv", {"old": "time", "sensor": "signal"})
    ]
    assert app.set_role_column_calls == [("", True)]
    assert app.set_role_value_calls == [("", True)]
    assert app.prep_views_refresh_count == 1
    assert app.notifications.success_messages == ["Role 'signal' applied to column 'sensor'"]


def test_apply_time_role_reclassifies_previous_numeric_time_as_signal():
    app = DummyApp()
    app.single_selected_path = "C:/tmp/a.csv"
    app.session.role_editor_column = "new_time"
    app.session.role_editor_value = "time"
    app.data_frames = {
        "C:/tmp/a.csv": pd.DataFrame({"old_time": [0.0], "new_time": [1.0]})
    }
    app.dataset_contexts = {
        "C:/tmp/a.csv": DatasetContext(column_roles={"old_time": "time", "new_time": "signal"})
    }

    actions.apply_selected_column_role(app)

    assert app.dataset_contexts["C:/tmp/a.csv"].column_roles == {
        "old_time": "signal",
        "new_time": "time",
    }


def test_apply_time_role_reclassifies_previous_text_time_as_metadata():
    app = DummyApp()
    app.single_selected_path = "C:/tmp/a.csv"
    app.session.role_editor_column = "new_time"
    app.session.role_editor_value = "time"
    app.data_frames = {
        "C:/tmp/a.csv": pd.DataFrame({"old_time": ["start"], "new_time": [1.0]})
    }
    app.dataset_contexts = {
        "C:/tmp/a.csv": DatasetContext(column_roles={"old_time": "time", "new_time": "signal"})
    }

    actions.apply_selected_column_role(app)

    assert app.dataset_contexts["C:/tmp/a.csv"].column_roles == {
        "old_time": "metadata",
        "new_time": "time",
    }


def test_apply_selected_column_role_warns_when_selection_missing(monkeypatch):
    app = DummyApp()
    app.single_selected_path = "C:/tmp/a.csv"
    app.session.role_editor_column = ""
    app.session.role_editor_value = ""
    app.dataset_contexts = {"C:/tmp/a.csv": DatasetContext(column_roles={})}
    actions.apply_selected_column_role(app)

    assert app.notifications.warning_messages == [("Select a column and a role first", None)]


def test_open_analysis_workspace_appends_workspace(monkeypatch):
    app = DummyApp()
    app.single_selected_path = "C:/tmp/a.csv"
    app.data_frames = {"C:/tmp/a.csv": pd.DataFrame({"x": [1]})}
    app.dataset_contexts = {
        "C:/tmp/a.csv": DatasetContext(
            source_paths=["C:/tmp/a.csv"],
            description="demo dataset",
            column_roles={"x": "signal"},
        )
    }

    created = []

    class FakeWorkspace:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

    monkeypatch.setitem(__import__("sys").modules, "Source.analysis_app.app", SimpleNamespace(AnalysisWorkspace=FakeWorkspace))

    actions.open_analysis_workspace(app)

    assert len(app._analysis_workspaces) == 1
    assert created[0]["column_roles"] == {"x": "signal"}
    assert created[0]["dataset_description"] == "demo dataset"
    assert callable(created[0]["on_publish_current_view"])


def test_open_analysis_workspace_for_path_warns_when_dataset_missing(monkeypatch):
    app = DummyApp()

    result = actions.open_analysis_workspace_for_path(app, "C:/tmp/missing.csv")

    assert result is None
    assert app.notifications.warning_messages == [("The selected dataset is not available in the current session", None)]


def test_publish_analysis_workspace_view_registers_dataset(monkeypatch):
    app = DummyApp()
    app.data_frames = {"C:/tmp/source.csv": pd.DataFrame({"time_s": [0.0, 1.0], "sensor": [1.0, 2.0]})}
    app.dataset_contexts = {
        "C:/tmp/source.csv": DatasetContext(
            source_paths=["C:/tmp/source.csv"],
            description="source dataset",
            column_roles={"time_s": "time", "sensor": "signal"},
        )
    }
    refresh_calls = []
    select_calls = []
    monkeypatch.setattr(actions, "refresh_dataset_table", lambda _app: refresh_calls.append(True))
    monkeypatch.setattr(actions, "select_dataset_in_table", lambda _app, path: select_calls.append(path))

    workspace = SimpleNamespace(
        session=SimpleNamespace(
            source_path="C:/tmp/source.csv",
            working_frame=pd.DataFrame({"time_s": [0.0, 1.0], "sensor_filt": [0.5, 1.5]}),
        ),
        active_column_var=SimpleNamespace(get=lambda: "sensor_filt"),
        column_roles={"time_s": "time", "sensor_filt": "signal"},
    )

    published_path = actions.publish_analysis_workspace_view(app, workspace)

    assert published_path is not None
    assert published_path.endswith("source__sensor_filt_analysis.csv")
    assert published_path in app.data_frames
    assert app.dataset_contexts[published_path].source_paths == ["C:/tmp/source.csv"]
    assert app.dataset_contexts[published_path].column_roles == {"time_s": "time", "sensor_filt": "signal"}
    assert refresh_calls == [True]
    assert select_calls == [published_path]
    assert app.prep_views_refresh_count == 1
    assert app.notifications.success_messages == [f"Published dataset: {os.path.basename(published_path)}"]
    workspace.session.working_frame.loc[0, "sensor_filt"] = 99.0
    assert app.data_frames[published_path].loc[0, "sensor_filt"] == 0.5


def test_publish_analysis_workspace_view_still_works_when_source_unloaded(monkeypatch):
    app = DummyApp()
    refresh_calls = []
    select_calls = []
    monkeypatch.setattr(actions, "refresh_dataset_table", lambda _app: refresh_calls.append(True))
    monkeypatch.setattr(actions, "select_dataset_in_table", lambda _app, path: select_calls.append(path))

    workspace = SimpleNamespace(
        session=SimpleNamespace(
            source_path="C:/tmp/source.csv",
            working_frame=pd.DataFrame({"sensor": [1.0, 2.0]}),
        ),
        active_column_var=SimpleNamespace(get=lambda: ""),
        column_roles={"sensor": "signal"},
    )

    published_path = actions.publish_analysis_workspace_view(app, workspace)

    assert published_path is not None
    assert published_path.endswith("source__analysis_view.csv")
    assert app.dataset_contexts[published_path].source_paths == ["C:/tmp/source.csv"]
    assert refresh_calls == [True]
    assert select_calls == [published_path]


def test_open_comparison_window_warns_when_fewer_than_two_datasets_selected(monkeypatch):
    app = DummyApp()
    app.multiple_selected_paths = ["C:/tmp/a.csv"]

    actions.open_comparison_window(app)

    assert app.notifications.warning_messages == [("Select at least two datasets to compare", None)]


def test_open_comparison_window_launches_window(monkeypatch):
    app = DummyApp()
    app.multiple_selected_paths = ["C:/tmp/a.csv", "C:/tmp/b.csv"]
    app.data_frames = {
        "C:/tmp/a.csv": pd.DataFrame({"time_s": [0.0], "sensor": [1.0]}),
        "C:/tmp/b.csv": pd.DataFrame({"time_s": [0.0], "sensor": [2.0]}),
    }
    created = []

    class FakeComparisonWindow:
        def __init__(self, *args, **kwargs):
            created.append((args, kwargs))

    monkeypatch.setattr(actions, "ComparisonWindow", FakeComparisonWindow)

    actions.open_comparison_window(app)

    assert len(created) == 1
    assert created[0][0][1] == ["C:/tmp/a.csv", "C:/tmp/b.csv"]
    assert len(app._comparison_windows) == 1
    assert callable(created[0][1]["on_open_dataset"])
