"""Prototype provenance model and real workflow integration tests."""

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pandas as pd
import pytest

from Source.shared.operation_history import OperationHistory, record_workspace_result
from Source.datapreparation_app import actions, preparation
from Source.datapreparation_app.datasets import register_dataset
from Source.analysis_app import handlers
from Source.analysis_app.app import AnalysisWorkspace
from Source.analysis_app.state import AnalysisSession
from tests.test_analysis_handlers import DummyWorkspace


@dataclass
class _Result:
    peak: float


def test_history_branches_and_publish_reuses_revision():
    history = OperationHistory()
    source = history.record("load_demo", "source")
    parameters = {"columns": ["signal"]}
    first = history.record("prepare", "first", (source,), parameters)
    parameters["columns"].append("other")
    second = history.record("prepare", "second", (source,))
    history.record("publish", "published", (first,), output_revision=first)
    assert first != second
    assert history.steps[1].input_revisions == history.steps[2].input_revisions == (source,)
    assert json.loads(history.steps[1].parameters_json) == {"columns": ["signal"]}
    assert history.steps[-1].output_revision == first


def test_history_rejects_invalid_links_and_parameters_without_recording():
    history = OperationHistory()
    with pytest.raises(ValueError, match="input"):
        history.record("prepare", "bad", ("missing",))
    with pytest.raises(ValueError, match="output"):
        history.record("publish", "bad", output_revision="missing")
    with pytest.raises(ValueError):
        history.record("prepare", "bad", parameters={"value": float("nan")})
    assert history.steps == ()


def test_register_reload_gets_new_identity_and_marks_unknown_operation():
    app = SimpleNamespace(data_frames={}, dataset_contexts={})
    register_dataset(app, "source", pd.DataFrame({"signal": [1]}))
    old = app.dataset_contexts["source"]
    register_dataset(app, "source", pd.DataFrame({"signal": [2]}))
    new = app.dataset_contexts["source"]
    assert old.dataset_id != new.dataset_id
    assert old.revision_id != new.revision_id
    assert not app.operation_history.steps[-1].tracked


def test_demo_prepare_filter_publish_end_to_end(monkeypatch):
    app = SimpleNamespace(
        data_frames={}, dataset_contexts={}, operation_history=OperationHistory(),
        session=SimpleNamespace(output_dataset_name="prepared", selected_columns=["time_s", "signal"]),
        notifications=SimpleNamespace(success=lambda *args, **kwargs: None),
        _refresh_dataset_preparation_views=lambda: None,
        _get_row_range_filtered_frame=lambda frame, roles: frame.iloc[:20],
        get_row_range_for_preparation=lambda: ("", ""),
    )
    for module in (actions, preparation):
        monkeypatch.setattr(module, "refresh_dataset_table", lambda app: None)
        monkeypatch.setattr(module, "select_dataset_in_table", lambda app, path: None)
    monkeypatch.setattr(actions, "create_demo_dataset", lambda key: (
        SimpleNamespace(basename="demo.csv", suffix="demo", column_roles={"time_s": "time", "signal": "signal"},
                        description="demo", summary="demo"),
        pd.DataFrame({"time_s": range(30), "signal": range(30)}),
    ))
    source = actions._load_demo_dataset(app, "test", show_message=False)
    app._get_single_selected_file_path = lambda message: source
    prepared = preparation.create_prepared_dataset(app)
    assert prepared is not None
    workspace = DummyWorkspace()
    workspace.session = AnalysisSession(prepared, app.data_frames[prepared], app.data_frames[prepared])
    workspace.operation_history = app.operation_history
    workspace.history_revision = app.dataset_contexts[prepared].revision_id
    workspace.active_column_var.set("signal")
    workspace.signal_filter_window_var.set("3")
    workspace._default_frequency_summary_text = lambda: ""
    workspace.fft_summary_var = SimpleNamespace(set=lambda value: None)
    workspace.cycle_summary_var = SimpleNamespace(set=lambda value: None)
    workspace._frame_replacing = False
    for name in ("_clear_fft_results", "_clear_cycle_results", "_refresh_all_views",
                 "_set_default_output_names", "_refresh_role_widget_styles", "_refresh_live_plot"):
        setattr(workspace, name, lambda *args: None)
    workspace._replace_working_frame = lambda *args, **kwargs: AnalysisWorkspace._replace_working_frame(
        workspace, *args, **kwargs,
    )
    handlers.apply_signal_filter(workspace)
    filtered_revision = workspace.history_revision
    record_workspace_result(workspace, "FFT Amplitude", _Result(1.0), {})
    published = actions.publish_analysis_workspace_view(app, workspace)
    assert published is not None
    publish_step = app.operation_history.steps[-1]
    assert json.loads(publish_step.parameters_json)["workspace_steps"] == [
        step.id for step in app.operation_history.steps if step.operation in {"moving_average", "FFT Amplitude"}
    ]
    assert publish_step.input_revisions == (filtered_revision,)
    assert app.dataset_contexts[published].revision_id == publish_step.output_revision != filtered_revision
    assert [step.operation for step in app.operation_history.steps] == [
        "load_demo", "prepare", "moving_average", "FFT Amplitude", "publish",
    ]
    assert json.loads(app.operation_history.steps[2].parameters_json) == {
        "source_column": "signal", "output_column": "custom_smooth", "window_size": 3,
    }
    assert app.data_frames[source]["signal"].tolist() == list(range(30))
    assert len(app.data_frames[published]) == 20


def test_failed_filter_does_not_record_history():
    workspace = DummyWorkspace()
    workspace.operation_history = OperationHistory()
    workspace.signal_filter_window_var.set("invalid")
    handlers.apply_signal_filter(workspace)
    assert workspace.operation_history.steps == ()
    assert not workspace.replace_calls


@pytest.mark.parametrize("operation,parameter,value", [
    ("moving_average", "window_size", 5), ("median", "window_size", 5),
    ("high_pass", "window_size", 5), ("exponential_smoothing", "alpha", 0.3),
])
def test_signal_filter_records_effective_parameter(operation, parameter, value):
    workspace = DummyWorkspace()
    workspace.signal_filter_operation_var.set(operation)
    handlers.apply_signal_filter(workspace)
    call = workspace.replace_calls[0]
    assert call["history_operation"] == operation
    assert call["history_parameters"][parameter] == value


def test_other_transform_handlers_record_parameters():
    workspace = DummyWorkspace()
    handlers.apply_filter(workspace)
    assert workspace.replace_calls[-1]["history_operation"] == "simple_filter"
    assert workspace.replace_calls[-1]["history_parameters"]["minimum"] == "0"
    handlers.apply_resample(workspace)
    assert workspace.replace_calls[-1]["history_parameters"] == {
        "time_column": "time_s", "target_spacing": 0.25,
    }
    handlers.apply_derived_signal(workspace)
    assert workspace.replace_calls[-1]["history_operation"] == "derived_delta"


def test_split_records_parent_and_exact_ranges(monkeypatch):
    app = SimpleNamespace(data_frames={}, dataset_contexts={}, session=SimpleNamespace(split_prefix="part"),
                          _refresh_dataset_preparation_views=lambda: None)
    register_dataset(app, "source", pd.DataFrame({"signal": range(10)}), history_operation="load_demo")
    source_revision = app.dataset_contexts["source"].revision_id
    app._get_single_selected_file_path = lambda message: "source"
    monkeypatch.setattr(preparation, "refresh_dataset_table", lambda app: None)
    monkeypatch.setattr(preparation, "select_dataset_in_table", lambda app, path: None)
    preparation.split_selected_dataset(app, "0:4\n4:10")
    steps = app.operation_history.steps[1:]
    assert all(step.input_revisions == (source_revision,) for step in steps)
    assert [json.loads(step.parameters_json) for step in steps] == [
        {"start": 0, "end": 4, "end_exclusive": True},
        {"start": 4, "end": 10, "end_exclusive": True},
    ]


def _history_workspace():
    workspace = AnalysisWorkspace.__new__(AnalysisWorkspace)
    frame = pd.DataFrame({"signal": [1, 2]})
    workspace.session = AnalysisSession("source", frame, frame)
    workspace.column_roles = {"signal": "signal"}
    workspace.operation_history = OperationHistory()
    source = workspace.operation_history.record("load_demo", "source")
    workspace.history_revision = source
    workspace.original_history_revision = source
    workspace.fft_summary_var = SimpleNamespace(set=lambda value: None)
    workspace.cycle_summary_var = SimpleNamespace(set=lambda value: None)
    workspace._default_frequency_summary_text = lambda: ""
    for name in ("filter_output_name_var", "signal_filter_name_var", "derived_name_var", "active_column_var"):
        setattr(workspace, name, SimpleNamespace(set=lambda value: None))
    for name in ("_update_frequency_diagnostics", "_clear_fft_results", "_clear_cycle_results",
                 "_refresh_all_views", "_set_default_output_names", "_refresh_role_widget_styles",
                 "_refresh_live_plot"):
        setattr(workspace, name, lambda *args: None)
    return workspace


def test_untracked_working_change_keeps_explicit_revision_link():
    workspace = _history_workspace()
    source = workspace.history_revision
    frame = workspace.session.working_frame
    workspace._replace_working_frame(frame.iloc[:1])
    step = workspace.operation_history.steps[-1]
    assert not step.tracked
    assert step.input_revisions == (source,)
    assert step.output_revision == workspace.history_revision


def test_reset_records_original_revision_and_previous_working_revision():
    workspace = _history_workspace()
    source = workspace.history_revision
    workspace.notifications = SimpleNamespace(success=lambda message: None)
    workspace._replace_working_frame(workspace.session.working_frame.iloc[:1])
    previous = workspace.history_revision
    workspace._reset_working_data()
    step = workspace.operation_history.steps[-1]
    assert step.operation == "reset"
    assert step.input_revisions == (previous,)
    assert json.loads(step.parameters_json) == {"original_revision": source}
    pd.testing.assert_frame_equal(workspace.session.working_frame, workspace.session.original_frame)


def test_kept_cycles_records_ranges_even_when_result_is_cleared(monkeypatch):
    from Source.analysis_app import app as analysis_module

    workspace = _history_workspace()
    workspace._latest_cycle_result = SimpleNamespace(cycle_ranges=[(0, 1)], source_column="signal", cycle_count=1)
    messages = []
    workspace.notifications = SimpleNamespace(success=messages.append)
    workspace._clear_cycle_results = lambda message: setattr(workspace, "_latest_cycle_result", None)
    monkeypatch.setattr(analysis_module.messagebox, "askyesno", lambda *args: True)
    workspace._apply_kept_cycles_to_working_data()
    step = workspace.operation_history.steps[-1]
    assert step.operation == "apply_kept_cycles"
    assert json.loads(step.parameters_json) == {"ranges": [[0, 1]], "end_exclusive": True}
    assert len(workspace.session.working_frame) == 1
    assert messages == ["Applied kept cycles: 1 cycles, 1 rows retained"]
