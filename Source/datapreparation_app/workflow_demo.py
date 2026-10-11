"""Scripted end-to-end demo: three daily files -> pipeline -> appends -> results -> HTML report.

Every step goes through the same functions the GUI uses (register/rename/record/append/publish/report),
so the saved project shows exactly what a user would get by doing the workflow by hand.
"""

import os
from dataclasses import dataclass
from types import SimpleNamespace

from Source.data_ops.cycles import compute_fixed_length_cycle_analysis
from Source.data_ops.io_ops import DATAFRAME_ROLE_ATTR
from Source.data_ops.signals import add_derived_column, apply_signal_filter
from Source.data_ops.spectral import compute_fft_spectrum, compute_spectrogram
from Source.shared.column_roles import update_projected_column_roles
from Source.shared.longterm_demo import SLOW_CYCLE_PERIOD_S, write_longterm_demo_files
from Source.shared.operation_history import REPORT_VIEW_OPERATION
from .append_workflow import execute_append, plan_append
from .data_parser import DataParser, PARSER_WARNINGS_ATTR
from .datasets import build_virtual_dataset_path, register_dataset, rename_dataset
from .project_io import ProjectSnapshot, save_project
from .report import build_publish_report


PROJECT_FILENAME = "longterm_workflow_demo.evaldata"
REPORT_FILENAME = "longterm_workflow_demo_report.html"


@dataclass(frozen=True)
class WorkflowDemo:
    data_paths: tuple[str, ...]
    project_path: str
    report_path: str


class _Workspace:
    """Minimal stand-in for an analysis workspace: a revision chain plus the step ids publish links."""

    def __init__(self, app, path: str):
        self.app, self.path = app, path
        self.history = app.operation_history
        self.frame = app.data_frames[path].copy()
        self.roles = dict(app.dataset_contexts[path].column_roles)
        self.revision = app.dataset_contexts[path].revision_id
        self.step_ids: list[str] = []

    def _remember(self, note: str = "") -> str:
        step_id = self.history.steps[-1].id
        self.step_ids.append(step_id)
        if note:
            self.history.set_note(step_id, note)
        return step_id

    def transform(self, operation: str, frame, source: str, output: str, parameters: dict, note: str = "") -> None:
        self.frame = frame
        self.roles = update_projected_column_roles(self.roles, frame, {output: self.roles.get(source, "signal")})
        self.revision = self.history.record(
            operation, self.path, (self.revision,), {"source_column": source, "output_column": output, **parameters},
        )
        self._remember(note)

    def result(self, operation: str, result, parameters: dict, note: str = "") -> str:
        self.history.record_result(operation, self.path, self.revision, result, parameters)
        return self._remember(note)

    def view(self, parameters: dict, note: str = "") -> str:
        self.history.record(REPORT_VIEW_OPERATION, self.path, (self.revision,), parameters, output_revision=self.revision)
        return self._remember(note)

    def publish(self, suffix: str, step_ids: list[str] | None = None) -> str:
        target = build_virtual_dataset_path(self.app.data_frames, self.path, suffix)
        register_dataset(
            self.app, target, self.frame.copy(), source_paths=[self.path],
            description=f"Published from analysis workspace ({os.path.basename(self.path)})",
            column_roles=self.roles, history_operation="publish", history_inputs=(self.revision,),
            history_parameters={
                "source_dataset": self.path, "columns": [str(column) for column in self.frame.columns],
                "workspace_steps": list(self.step_ids if step_ids is None else step_ids),
            },
        )
        return target


def _load(app, path: str) -> None:
    frame, separator, decimal_marker = DataParser.load_file(path)
    register_dataset(
        app, path, frame, source_paths=[path], description="Loaded source dataset",
        column_roles=frame.attrs.get(DATAFRAME_ROLE_ATTR), history_operation="load_file",
        history_parameters={
            "path": path, "separator": separator, "decimal_marker": decimal_marker,
            "warnings": frame.attrs.get(PARSER_WARNINGS_ATTR, []),
        },
    )


def build_workflow_demo_app(data_paths: tuple[str, ...]):
    """Run the scripted workflow on the three daily files and return (app-like state, final publish step id)."""
    day1, day2, day3 = data_paths
    app = SimpleNamespace(data_frames={}, dataset_contexts={})
    _load(app, day1)
    rename_dataset(app, day1, "Long-term run - day 1 (raw)")
    history = app.operation_history

    # Stage 1: explore day 1 and decide on the pipeline.
    explore = _Workspace(app, day1)
    explore.result(
        "FFT Amplitude", compute_fft_spectrum(explore.frame, "measurement", reference_column="timestamp"), {},
        note="Raw day-1 FFT: clear 1 h reference cycle, a slow component near the 12 h limit of one day, "
        "and a broadband noise floor. Decision: smooth (60 s) before any cycle work, then remove the drift.",
    )
    explore.transform(
        "moving_average", apply_signal_filter(explore.frame, "measurement", "moving_average", "measurement_smooth",
                                              window_size=60),
        "measurement", "measurement_smooth", {"window_size": 60},
        note="60 s window: well below the 1 h cycle, removes sensor noise.",
    )
    explore.transform(
        "derived_detrend", add_derived_column(explore.frame, "detrend", "measurement_smooth", "measurement_detrended",
                                              window_size=1),
        "measurement_smooth", "measurement_detrended", {"reference_column": None, "window_size": 1},
        note="Linear detrend so cycles at the start and end of the run are comparable.",
    )
    explore.result(
        "cycle_analysis", compute_fixed_length_cycle_analysis(explore.frame, "measurement_detrended", 3600,
                                                              time_column="timestamp"),
        {"method": "fixed_length", "cycle_length": 3600},
        note="Day-1 cycles are stable (1 h); pipeline accepted for the full run.",
    )
    pipeline = explore.publish("pipeline")
    rename_dataset(app, pipeline, "Long-term run - processed")

    # Stage 2: the next deliveries are appended in front of the pipeline, which is recomputed in place.
    for incoming in (day2, day3):
        _load(app, incoming)
        raw_path, _ = execute_append(app, plan_append(app, pipeline, incoming))
    rename_dataset(app, raw_path, "Long-term run - raw (days 1-3)")

    # Stage 3: final evidence on all three days, then publish the reporting dataset.
    final = _Workspace(app, pipeline)
    final.result(
        "Spectrogram", compute_spectrogram(final.frame, "measurement_detrended", reference_column="timestamp",
                                           segment_length=4096), {"segment_length": 4096},
        note="Broadband burst on day 3 around 12:00 - not part of the normal cycle.",
    )
    final.result(
        "cycle_analysis", compute_fixed_length_cycle_analysis(final.frame, "measurement_detrended", 3600,
                                                              time_column="timestamp"),
        {"method": "fixed_length", "cycle_length": 3600},
    )
    final.result(
        "Cycle Analysis (12-hour measurement)",
        compute_fixed_length_cycle_analysis(
            final.frame, "measurement_detrended", SLOW_CYCLE_PERIOD_S, time_column="timestamp",
        ),
        {"method": "fixed_length", "cycle_length": SLOW_CYCLE_PERIOD_S},
        note="Six 12-hour cycles of the smoothed, detrended measurement across all three days. "
        "This focuses the cycle comparison on the slow component, but does not isolate it: "
        "the hourly oscillation and the day-3 anomaly remain in the signal.",
    )
    final.view({
        "title": "Three-day overview", "x_column": "timestamp",
        "y_columns": ["measurement_smooth", "measurement_detrended", "temperature_c"],
        "subplots": True, "x_range": None, "y_scale": "linear",
    })
    final.view({
        "title": "Day 3 anomaly (zoom)", "x_column": "timestamp", "y_columns": ["measurement", "measurement_smooth"],
        "subplots": False, "x_range": ["2026-10-03T11:30:00", "2026-10-03T12:40:00"], "y_scale": "linear",
    }, note="10 min step of about +2.5 starting 12:00 on day 3; flagged for follow-up.")
    report_dataset = final.publish("report")
    rename_dataset(app, report_dataset, "Long-term run - report")
    publish_id = next(step.id for step in reversed(history.steps) if step.operation == "publish")
    return app, publish_id


def create_workflow_demo_project(output_dir: str) -> WorkflowDemo:
    project_path = os.path.join(output_dir, PROJECT_FILENAME)
    report_path = os.path.join(output_dir, REPORT_FILENAME)
    existing = [path for path in (project_path, report_path) if os.path.exists(path)]
    if existing:
        raise FileExistsError("Demo project already exists; choose another folder:\n" + "\n".join(existing))
    data_paths = write_longterm_demo_files(output_dir)
    app, publish_id = build_workflow_demo_app(data_paths)
    save_project(project_path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(build_publish_report(app, publish_id))
    return WorkflowDemo(data_paths, project_path, report_path)
