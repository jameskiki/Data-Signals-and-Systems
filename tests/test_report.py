"""Publish-node HTML reports: content, honesty about stale/missing data, and safety."""

import json
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from Source.analysis_app.plotting import build_time_series_plot_options, capture_time_series_view
from Source.data_ops.cycles import compute_fixed_length_cycle_analysis
from Source.data_ops.signals import apply_signal_filter
from Source.data_ops.spectral import compute_fft_spectrum, compute_spectrogram
from Source.datapreparation_app.datasets import register_dataset, rename_dataset
from Source.datapreparation_app.history_deletion import delete_history_nodes, plan_history_deletion
from Source.datapreparation_app.project_io import ProjectSnapshot, load_project, save_project
from Source.datapreparation_app.report import _edges, _key_values, _table_html, build_publish_report
from Source.shared.operation_history import record_workspace_view
from Source.shared.plot_options import PlotDescriptor
from Source.shared.plot_utils import create_plot_figure

STAMP = datetime(2026, 10, 11, tzinfo=timezone.utc)


def test_data_tables_are_collapsed_labelled_escaped_and_keep_preview_limits():
    frame = pd.DataFrame({"signal": ["<script>"] * 25})
    content = _table_html(frame, title="<Result data>")
    assert content.startswith('<details class="table-panel">')
    assert '<summary>&lt;Result data&gt; (25 rows, 1 column)</summary>' in content
    assert "<script>" not in content
    assert content.count("&lt;script&gt;") == 20
    assert "First 20 of 25 rows shown." in content
    assert 'class="table-scroll"' in content
    assert content.endswith("</details>")
    summary = _key_values({"Signal": "<measurement>"})
    assert summary.startswith('<div class="table-panel">')
    assert "<details" not in summary
    assert "&lt;measurement&gt;" in summary


def test_report_selection_excludes_result_view_and_notes_without_changing_pipeline(monkeypatch):
    from Source.datapreparation_app import report as report_module
    monkeypatch.setattr(report_module, "_figure_html", lambda figure, caption: f"<figure>{caption}</figure>")
    app, publish_id, linked = published_session()
    history = app.operation_history
    fft_id = linked[1]
    history.set_note(fft_id, "UNIQUE FFT DECISION")
    revision = app.dataset_contexts["raw__median_analysis.csv"].revision_id
    history.record("report_view", "raw__median_analysis.csv", (revision,), {
        "title": "UNIQUE ZOOM", "x_column": "time", "y_columns": ["median"],
    }, output_revision=revision)
    view_id = history.steps[-1].id
    history.set_note(view_id, "UNIQUE VIEW DECISION")
    original_steps = history.steps
    original_frame = app.data_frames["raw__median_analysis.csv"].copy()
    assert "UNIQUE ZOOM" in build_publish_report(app, publish_id, STAMP)
    history.set_report_node_enabled(publish_id, fft_id, False)
    history.set_report_node_enabled(publish_id, view_id, False)
    report = build_publish_report(app, publish_id, STAMP)
    assert "FFT Amplitude" not in report
    assert "UNIQUE FFT DECISION" not in report
    assert "UNIQUE ZOOM" not in report
    assert "UNIQUE VIEW DECISION" not in report
    assert "2 node(s) intentionally excluded" in report
    assert "Published Data" in report and "Spectrogram" in report
    assert history.steps == original_steps
    pd.testing.assert_frame_equal(app.data_frames["raw__median_analysis.csv"], original_frame)
    assert fft_id in history.artifact_tables
    history.set_report_node_enabled(publish_id, fft_id, True)
    assert "FFT Amplitude" in build_publish_report(app, publish_id, STAMP)
    history.set_report_node_enabled(publish_id, history.steps[0].id, True)
    assert "load_file" in build_publish_report(app, publish_id, STAMP)


def published_session():
    app = SimpleNamespace(data_frames={}, dataset_contexts={}, _analysis_workspaces=[], _comparison_windows=[])
    time = np.arange(20_000, dtype=float)
    raw = pd.DataFrame({"time": time, "signal": np.sin(2 * np.pi * time / 100)})
    register_dataset(app, "raw.csv", raw, history_operation="load_file", column_roles={"time": "time", "signal": "signal"})
    history = app.operation_history
    revision = app.dataset_contexts["raw.csv"].revision_id
    linked = []
    smooth = apply_signal_filter(raw, "signal", "moving_average", "smooth", window_size=3)
    revision = history.record("moving_average", "raw.csv", (revision,), {"source_column": "signal", "output_column": "smooth", "window_size": 3})
    linked.append(history.steps[-1].id)
    history.record_result("FFT Amplitude", "raw.csv", revision, compute_fft_spectrum(smooth, "smooth", reference_column="time"), {})
    linked.append(history.steps[-1].id)
    final = apply_signal_filter(smooth, "smooth", "median", "median", window_size=5)
    revision = history.record("median", "raw.csv", (revision,), {"source_column": "smooth", "output_column": "median", "window_size": 5})
    linked.append(history.steps[-1].id)
    history.record_result("Spectrogram", "raw.csv", revision, compute_spectrogram(final, "median", "time", 1.0), {})
    linked.append(history.steps[-1].id)
    register_dataset(
        app, "raw__median_analysis.csv", final, history_operation="publish", history_inputs=(revision,),
        history_parameters={"source_dataset": "raw.csv", "columns": list(final.columns), "workspace_steps": linked},
        column_roles={"time": "time", "signal": "signal", "smooth": "signal", "median": "signal"},
    )
    return app, history.steps[-1].id, linked


def test_report_lists_linked_operations_results_and_flags_earlier_state():
    app, publish_id, linked = published_session()
    report = build_publish_report(app, publish_id, STAMP)
    assert report == build_publish_report(app, publish_id, STAMP)
    assert "EvalData Report: raw__median_analysis.csv" in report
    for operation in ("moving_average", "FFT Amplitude", "median", "Spectrogram"):
        assert operation in report
    assert "load_file" not in report
    assert report.count("data:image/png;base64,") == 3
    assert report.count("Computed on an earlier working state") == 1
    assert "Reduced resolution: every 4. of 20000 rows shown" in report
    assert "green = produced by the linked operations" in report
    assert "dominant_frequency" in report
    assert "not a quality approval" in report
    assert '<ul class="warn">' not in report
    tables = re.findall(r'<details class="table-panel">.*?</details>', report, re.DOTALL)
    assert any("Statistics (numeric columns, full data)" in table for table in tables)
    assert any("peaks_frame" in table for table in tables)
    assert all("<summary>" in table and "<table" in table for table in tables)


def test_report_makes_missing_and_deleted_state_visible():
    app, publish_id, linked = published_session()
    fft_id = linked[1]
    delete_history_nodes(app, fft_id, plan_history_deletion(app, fft_id))
    app.data_frames.pop("raw__median_analysis.csv")
    app.dataset_contexts.pop("raw__median_analysis.csv")
    report = build_publish_report(app, publish_id, STAMP)
    assert "1 linked operation(s) were deleted" in report
    assert "no longer loaded in this exact revision" in report
    assert "Published Data" not in report
    assert "FFT Amplitude" not in report


def test_report_escapes_names_and_rejects_non_publish_and_marks_legacy_publish():
    app, publish_id, _ = published_session()
    rename_dataset(app, "raw__median_analysis.csv", "<script>alert(1)</script>")
    report = build_publish_report(app, publish_id, STAMP)
    assert "<script>" not in report and "&lt;script&gt;" in report
    with pytest.raises(ValueError, match="publish node"):
        build_publish_report(app, app.operation_history.steps[0].id)
    revision = app.dataset_contexts["raw.csv"].revision_id
    register_dataset(app, "old.csv", app.data_frames["raw.csv"], history_operation="publish", history_inputs=(revision,))
    assert "predates operation linking" in build_publish_report(app, app.operation_history.steps[-1].id, STAMP)


def test_report_renders_after_project_round_trip(tmp_path):
    app, publish_id, _ = published_session()
    path = str(tmp_path / "p.evaldata")
    save_project(path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    restored = load_project(path)
    reopened = SimpleNamespace(data_frames=restored.data_frames, dataset_contexts=restored.dataset_contexts,
                               operation_history=restored.history)
    report = build_publish_report(reopened, publish_id, STAMP)
    assert report.count("data:image/png;base64,") == 3
    assert not re.search(r"Saved result tables are missing", report)
    assert json.loads(restored.history.steps[-1].parameters_json)["workspace_steps"]


def test_report_cycle_section_plots_shape_and_per_cycle_trend():
    app, _, linked = published_session()
    history = app.operation_history
    revision = app.dataset_contexts["raw__median_analysis.csv"].revision_id
    frame = app.data_frames["raw__median_analysis.csv"]
    history.record_result("Cycle Analysis", "raw.csv", revision,
                          compute_fixed_length_cycle_analysis(frame, "median", 100, time_column="time"), {})
    register_dataset(
        app, "cycles.csv", frame, history_operation="publish", history_inputs=(revision,),
        history_parameters={"source_dataset": "raw.csv", "workspace_steps": linked + [history.steps[-1].id]},
    )
    report = build_publish_report(app, history.steps[-1].id, STAMP)
    assert "representative cycle across all detected cycles" in report
    assert "per-cycle metrics over the run" in report
    assert "log frequency axis, DC omitted" in report


def test_spectrogram_edges_stay_positive_on_log_axis():
    edges = _edges(np.array([0.001, 0.01, 0.1]), log=True)
    assert np.all(edges > 0) and np.allclose(edges[1:3], [np.sqrt(1e-5), np.sqrt(1e-3)])
    assert _edges(np.array([5.0]), log=False).tolist() == [4.5, 5.5]


def _plot_workspace(frame, x_column, columns, use_subplots=False, family="Time series"):
    session = SimpleNamespace(working_frame=frame, selected_x_column=x_column, selected_y_columns=columns,
                              use_subplots=use_subplots, source_path="raw.csv")
    options = build_time_series_plot_options(columns, x_column, use_subplots)
    figure = create_plot_figure(options, ["raw.csv"], {"raw.csv": frame})
    return SimpleNamespace(session=session, _plot_figure=figure, _plot_descriptor=PlotDescriptor(family, "Overlay"))


def test_capture_time_series_view_records_zoomed_datetime_range_and_full_numeric_range():
    stamps = pd.date_range("2026-01-01", periods=1000, freq="s")
    frame = pd.DataFrame({"t": stamps, "a": np.arange(1000.0), "b": np.ones(1000)})
    workspace = _plot_workspace(frame, "t", ["a"])
    workspace._plot_figure.get_axes()[0].set_xlim(mdates.date2num(stamps[100]), mdates.date2num(stamps[200]))
    workspace._plot_figure.get_axes()[0].set_yscale("log")
    view = capture_time_series_view(workspace)
    assert view["y_columns"] == ["a"] and view["y_scale"] == "log" and not view["subplots"]
    assert [pd.Timestamp(value) for value in view["x_range"]] == [stamps[100], stamps[200]]
    numeric = _plot_workspace(frame, "Index", ["a", "b"], use_subplots=True)
    assert capture_time_series_view(numeric)["x_range"] is None
    plt.close("all")
    with pytest.raises(ValueError, match="time-series plot"):
        capture_time_series_view(_plot_workspace(frame, "t", ["a"], family="Comparison"))
    plt.close("all")


def test_report_view_is_linked_drawn_from_published_data_and_flags_missing_columns():
    app, _, linked = published_session()
    revision = app.dataset_contexts["raw__median_analysis.csv"].revision_id
    workspace = SimpleNamespace(operation_history=app.operation_history, history_revision=revision,
                                session=SimpleNamespace(source_path="raw.csv"), history_step_ids=list(linked))
    assert record_workspace_view(workspace, {
        "title": "Zoom <b>", "x_column": "time", "y_columns": ["median", "gone"], "subplots": False,
        "x_range": [100.0, 600.0], "y_scale": "linear",
    })
    register_dataset(
        app, "view.csv", app.data_frames["raw__median_analysis.csv"], history_operation="publish",
        history_inputs=(revision,), history_parameters={"source_dataset": "raw.csv", "workspace_steps": workspace.history_step_ids},
    )
    report = build_publish_report(app, app.operation_history.steps[-1].id, STAMP)
    assert "View #" in report and "Zoom &lt;b&gt;" in report and "Zoom <b>" not in report
    assert "501 of 20000 published rows in range" in report
    assert "Not in the published data: gone." in report
    assert "report view" in report and report.count("data:image/png;base64,") == 4
    from Source.datapreparation_app.history_view import history_category
    assert history_category(app.operation_history.steps[-2], app.operation_history) == "snapshot"
