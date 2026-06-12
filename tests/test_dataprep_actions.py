"""Focused tests for datapreparation_app.actions orchestration helpers."""

from types import SimpleNamespace

import pandas as pd

from Source.datapreparation_app import actions
from Source.datapreparation_app.datasets import DatasetContext


class DummyNotifications:
    def __init__(self):
        self.success_messages = []
        self.warning_messages = []
        self.info_messages = []

    def success(self, message):
        self.success_messages.append(message)

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

        self.prep_views_refresh_count = 0
        self.set_role_column_calls = []
        self.set_role_value_calls = []

        self.split_options = None

        self.single_selected_path = None
        self.multiple_selected_paths = []
        self._analysis_workspaces = []
        self.root = object()

    def _refresh_dataset_preparation_views(self):
        self.prep_views_refresh_count += 1

    def _set_role_editor_column(self, value, update_var=False):
        self.set_role_column_calls.append((value, update_var))

    def _set_role_editor_value(self, value, update_var=False):
        self.set_role_value_calls.append((value, update_var))

    def _prompt_split_subframes_options(self):
        return self.split_options

    def _get_single_selected_file_path(self, _message):
        return self.single_selected_path

    def _get_multiple_selected_file_paths(self, _message):
        return self.multiple_selected_paths

    def _on_analysis_workspace_closed(self, _workspace):
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


def test_export_clean_data_warns_without_datasets(monkeypatch):
    app = DummyApp()

    actions.export_clean_data(app)

    assert app.notifications.warning_messages == [("No data loaded", None)]


def test_export_clean_data_success(monkeypatch):
    app = DummyApp()
    app.data_frames = {"C:/tmp/a.csv": pd.DataFrame({"x": [1, 2]})}

    monkeypatch.setattr(actions.filedialog, "askdirectory", lambda title: "C:/out")
    monkeypatch.setattr(actions, "export_clean_dataframes", lambda frames, out_dir: 1)

    actions.export_clean_data(app)

    assert app.notifications.success_messages == ["Exported 1 files"]


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
    app.dataset_contexts = {"C:/tmp/a.csv": DatasetContext(column_roles={"old": "time"})}

    actions.apply_selected_column_role(app)

    assert app.dataset_contexts["C:/tmp/a.csv"].column_roles["sensor"] == "signal"
    assert app.set_role_column_calls == [("", True)]
    assert app.set_role_value_calls == [("", True)]
    assert app.prep_views_refresh_count == 1
    assert app.notifications.success_messages == ["Role 'signal' applied to column 'sensor'"]


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
