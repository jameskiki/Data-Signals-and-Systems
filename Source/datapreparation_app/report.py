"""Self-contained HTML report for one publish node and its linked workspace operations.

The renderer only reads history, registry data and saved result tables; it never touches
live GUI widgets, so the report describes recorded state rather than what a window shows.
"""

import base64
import html
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from Source.data_ops.summary import build_statistics_frame
from Source.data_ops.time_axis import reference_axis_seconds
from Source.shared.operation_history import (
    BASED_ON_KEY, BEFORE_APPEND_KEY, REPORT_VIEW_OPERATION, based_on_text, before_append_step,
)
from Source.shared.plot_utils import resolve_x_values
from .datasets import dataset_display_name
from .project_io import read_app_version

MAX_PLOT_POINTS = 5_000
MAX_TABLE_ROWS = 20
MAX_SIGNAL_LINES = 6
MAX_SPECTROGRAM_CELLS = 300


@dataclass(frozen=True)
class ReportSection:
    title: str
    body: str


def _e(value) -> str:
    return html.escape(str(value))


def _figure_html(figure: Figure, caption: str) -> str:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=100, bbox_inches="tight", metadata={"Software": None})
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f'<figure><img alt="{_e(caption)}" src="data:image/png;base64,{encoded}"><figcaption>{_e(caption)}</figcaption></figure>'


def _table_panel(content: str) -> str:
    return f'<div class="table-panel"><div class="table-scroll">{content}</div></div>'


def _table_html(frame: pd.DataFrame, max_rows: int = MAX_TABLE_ROWS, title: str = "Data table") -> str:
    shown = frame.head(max_rows)
    note = "" if len(frame) <= max_rows else f'<p class="note">First {max_rows} of {len(frame)} rows shown.</p>'
    table = shown.to_html(classes="data", float_format=lambda value: f"{value:.6g}", border=0)
    rows_label = "row" if len(frame) == 1 else "rows"
    columns_label = "column" if len(frame.columns) == 1 else "columns"
    return (
        f'<details class="table-panel"><summary>{_e(title)} '
        f'({len(frame)} {rows_label}, {len(frame.columns)} {columns_label})</summary>'
        f'<div class="table-scroll">{table}</div>{note}</details>'
    )


def _key_values(items: dict[str, object]) -> str:
    rows = []
    for key, value in items.items():
        text = json.dumps(value, default=str) if isinstance(value, (list, dict)) else str(value)
        if len(text) > 300:
            text = text[:300] + " ... (truncated)"
        rows.append(f"<tr><th>{_e(key)}</th><td>{_e(text)}</td></tr>")
    return _table_panel('<table class="kv">' + "".join(rows) + "</table>") if rows else '<p class="note">No parameters.</p>'


def _column(table: pd.DataFrame) -> np.ndarray:
    return pd.to_numeric(table.iloc[:, 0], errors="coerce").to_numpy(dtype=float)


def _stride(count: int, limit: int) -> int:
    return max(1, int(np.ceil(count / limit)))


def _spectrum_plot(tables: dict[str, pd.DataFrame], title: str) -> str:
    frequencies, amplitudes = _column(tables["frequencies"]), _column(tables["amplitudes"])
    keep = np.isfinite(frequencies) & np.isfinite(amplitudes) & (frequencies > 0)
    if not keep.any():
        return '<p class="warn">Spectrum contains no positive finite frequencies to plot.</p>'
    figure = Figure(figsize=(9, 3.2))
    axis = figure.add_subplot()
    axis.plot(frequencies[keep], amplitudes[keep], color="#0072b2", linewidth=1)
    axis.set_xscale("log")
    axis.set_xlabel("Frequency [Hz] (log scale, DC omitted)")
    axis.set_ylabel("Amplitude")
    axis.set_title(title)
    axis.grid(True, which="both", alpha=0.3)
    return _figure_html(figure, f"{title}: saved spectrum, all {int(keep.sum())} non-DC bins.")


def _edges(centers: np.ndarray, log: bool) -> np.ndarray:
    """Cell edges around bin centers; geometric midpoints keep log-axis edges positive."""
    values = np.log(centers) if log else np.asarray(centers, dtype=float)
    if values.size == 1:
        edges = np.array([values[0] - 0.5, values[0] + 0.5])
    else:
        middle = (values[:-1] + values[1:]) / 2
        first = values[0] - (values[1] - values[0]) / 2
        last = values[-1] + (values[-1] - values[-2]) / 2
        edges = np.concatenate(([first], middle, [last]))
    return np.exp(edges) if log else edges


def _spectrogram_plot(tables: dict[str, pd.DataFrame], title: str) -> str:
    times, frequencies = _column(tables["times"]), _column(tables["frequencies"])
    # Saved spectrogram power is (time, frequency), matching the app's plot preparation.
    power = tables["power"].to_numpy(dtype=float).T
    positive = frequencies > 0
    frequencies, power = frequencies[positive], power[positive]
    if not frequencies.size:
        return '<p class="note">No positive frequency bins to plot.</p>'
    count = power.shape[0]
    rows = np.unique(np.geomspace(1, count, MAX_SPECTROGRAM_CELLS).astype(int) - 1) if count > MAX_SPECTROGRAM_CELLS else np.arange(count)
    column_step = _stride(power.shape[1], MAX_SPECTROGRAM_CELLS)
    reduced = power[rows, ::column_step]
    shown_frequencies, shown_times = frequencies[rows], times[::column_step]
    figure = Figure(figsize=(9, 3.6))
    axis = figure.add_subplot()
    mesh = axis.pcolormesh(
        _edges(shown_times, log=False), _edges(shown_frequencies, log=True),
        10 * np.log10(np.maximum(reduced, 1e-300)), shading="flat", cmap="viridis",
    )
    axis.set_yscale("log")
    figure.colorbar(mesh, ax=axis, label="Power [dB]")
    axis.set_xlabel("Time [s]")
    axis.set_ylabel("Frequency [Hz]")
    axis.set_title(title)
    notes = []
    if rows.size < count:
        notes.append(f"{rows.size} of {count} frequency bins shown (log-spaced selection, not averaged)")
    if column_step > 1:
        notes.append(f"every {column_step}. time bin shown")
    note = f" Reduced resolution: {'; '.join(notes)}." if notes else ""
    return _figure_html(figure, f"{title}: saved spectrogram, log frequency axis, DC omitted.{note}")


def _cycle_plots(tables: dict[str, pd.DataFrame], title: str) -> str:
    parts = []
    shape = tables.get("representative_frame")
    if shape is not None and "mean" in shape.columns:
        x_values = shape["step"].to_numpy(dtype=float) if "step" in shape.columns else np.arange(len(shape), dtype=float)
        figure = Figure(figsize=(9, 3.2))
        axis = figure.add_subplot()
        if {"min", "max"} <= set(shape.columns):
            axis.fill_between(x_values, shape["min"], shape["max"], color="#0072b2", alpha=0.12, label="min/max")
        if "std" in shape.columns:
            axis.fill_between(
                x_values, shape["mean"] - shape["std"], shape["mean"] + shape["std"],
                color="#0072b2", alpha=0.3, label="mean +/- 1 std",
            )
        axis.plot(x_values, shape["mean"], color="#0072b2", linewidth=1.2, label="mean")
        axis.set_xlabel("Sample in cycle")
        axis.set_title(f"{title}: representative cycle")
        axis.legend(loc="best", fontsize="small")
        axis.grid(True, alpha=0.3)
        parts.append(_figure_html(figure, f"{title}: representative cycle across all detected cycles."))
    metrics = tables.get("metrics_frame")
    trend_columns = [column for column in ("mean", "peak_to_peak", "rms") if metrics is not None and column in metrics.columns]
    if trend_columns and len(metrics) > 1:
        x_values = metrics["cycle"].to_numpy() if "cycle" in metrics.columns else np.arange(1, len(metrics) + 1)
        figure = Figure(figsize=(9, 1.4 * len(trend_columns) + 0.6))
        axes = figure.subplots(len(trend_columns), 1, sharex=True, squeeze=False)[:, 0]
        for axis, column in zip(axes, trend_columns):
            axis.plot(x_values, metrics[column], marker="o", markersize=3, linewidth=0.8, color="#0072b2")
            axis.set_ylabel(column, rotation=0, ha="right", va="center", fontsize="small")
            axis.grid(True, alpha=0.3)
        axes[-1].set_xlabel("Cycle number")
        parts.append(_figure_html(figure, f"{title}: per-cycle metrics over the run."))
    return "".join(parts)


def _dataset_plot(frame: pd.DataFrame, roles: dict[str, str], preferred: list[str]) -> str:
    time_columns = [column for column, role in roles.items() if role == "time" and column in frame.columns]
    numeric = [
        column for column in frame.columns
        if column not in time_columns and pd.api.types.is_numeric_dtype(frame[column])
        and not pd.api.types.is_bool_dtype(frame[column])
    ]
    signals = [column for column in numeric if roles.get(column) == "signal"] or numeric
    ordered = [column for column in preferred if column in signals]
    signals = list(dict.fromkeys(ordered + signals))
    omitted = signals[MAX_SIGNAL_LINES:]
    signals = signals[:MAX_SIGNAL_LINES]
    if not signals:
        return '<p class="note">No numeric signal columns to plot.</p>'
    step = _stride(len(frame), MAX_PLOT_POINTS)
    if time_columns:
        x_values = reference_axis_seconds(frame[time_columns[0]]).to_numpy(dtype=float)
        finite = x_values[np.isfinite(x_values)]
        if finite.size:
            x_values = x_values - finite[0]
        x_label = f"{time_columns[0]} [s from start]"
    else:
        x_values = np.arange(len(frame), dtype=float)
        x_label = "Row"
    figure = Figure(figsize=(9, 1.5 * len(signals) + 0.6))
    axes = figure.subplots(len(signals), 1, sharex=True, squeeze=False)[:, 0]
    for axis, column in zip(axes, signals):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
        color = "#00745a" if column in ordered else "#0072b2"
        axis.plot(x_values[::step], values[::step], linewidth=0.8, color=color)
        axis.set_ylabel(str(column), rotation=0, ha="right", va="center", fontsize="small")
        axis.grid(True, alpha=0.3)
    axes[-1].set_xlabel(x_label)
    notes = []
    if ordered:
        notes.append("green = produced by the linked operations")
    if step > 1:
        notes.append(f"Reduced resolution: every {step}. of {len(frame)} rows shown")
    if omitted:
        notes.append("not plotted: " + ", ".join(map(str, omitted)))
    return _figure_html(figure, "Published signals (one panel per column). " + "; ".join(notes))


def _basis_note(step) -> str:
    return (
        f'<p class="note"><b>Evidence {_e(based_on_text(step))}</b>: computed before later rows were appended; '
        "it does not include them.</p>"
    )


def _note_html(history, step) -> str:
    note = history.notes.get(step.id)
    return f'<p class="decision"><b>Decision note:</b> {_e(note)}</p>' if note else ""


def _result_body(step, tables: dict[str, pd.DataFrame] | None, published_input: str) -> str:
    parameters = json.loads(step.parameters_json)
    table_names = parameters.pop("result_tables", [])
    parameters.pop(BEFORE_APPEND_KEY, None)
    parameters.pop(BASED_ON_KEY, None)
    parts = []
    if before_append_step(step):
        parts.append(_basis_note(step))
    elif step.output_revision != published_input:
        parts.append(
            '<p class="warn">Computed on an earlier working state. Later operations changed the data, '
            "so this result does not describe the published dataset.</p>"
        )
    parts.append(_key_values(parameters))
    if tables is None:
        parts.append(f'<p class="warn">Saved result tables are missing ({_e(", ".join(table_names) or "none recorded")}).</p>')
        return "".join(parts)
    if {"frequencies", "amplitudes"} <= tables.keys():
        parts.append(_spectrum_plot(tables, step.operation))
    elif {"times", "frequencies", "power"} <= tables.keys():
        parts.append(_spectrogram_plot(tables, step.operation))
    elif "representative_frame" in tables:
        parts.append(_cycle_plots(tables, step.operation))
    for name, table in tables.items():
        if name in {"frequencies", "amplitudes", "phase", "times", "power"}:
            continue
        if name == "cycles_frame":
            parts.append(f"<p class=\"note\">Table <code>{_e(name)}</code>: {table.shape[0]} x {table.shape[1]} (not shown).</p>")
            continue
        parts.append(_table_html(table, title=name))
    return "".join(parts)


VIEW_COLORS = ("#0072b2", "#e69f00", "#009e73", "#cc79a7", "#56b4e9", "#d55e00")


def _view_rows(x: pd.Series, x_range) -> np.ndarray:
    if not x_range:
        return np.arange(len(x))
    if pd.api.types.is_datetime64_any_dtype(x):
        low, high = (pd.Timestamp(value) for value in x_range)
        if x.dt.tz is None and low.tzinfo is not None:
            low, high = low.tz_convert(None), high.tz_convert(None)
        elif x.dt.tz is not None and low.tzinfo is None:
            low, high = low.tz_localize("UTC"), high.tz_localize("UTC")
    else:
        x = pd.to_numeric(x, errors="coerce")
        low, high = (float(value) for value in x_range)
    return np.flatnonzero(((x >= low) & (x <= high)).to_numpy())


def _view_body(step, frame: pd.DataFrame, published_input: str) -> str:
    """Re-render a recorded time-series view from the published data."""
    view = json.loads(step.parameters_json)
    title = view.get("title") or "Time series"
    parts = []
    if before_append_step(step):
        parts.append(
            f'<p class="note">Recorded {_e(based_on_text(step))} (before later rows were appended); drawn from the '
            "current published data with the recorded settings, so the range may not cover the appended rows.</p>"
        )
    elif step.output_revision != published_input:
        parts.append(
            '<p class="note">Recorded on an earlier working state; drawn from the published data '
            "with the recorded settings.</p>"
        )
    x_range = view.get("x_range")
    parts.append(_key_values({
        "Columns": ", ".join(map(str, view.get("y_columns", []))),
        "X axis": view.get("x_column", "Index"),
        "X range": " to ".join(map(str, x_range)) if x_range else "full",
        "Layout": "subplots" if view.get("subplots") else "overlay",
        "Y scale": view.get("y_scale", "linear"),
    }))
    requested = list(view.get("y_columns", []))
    columns = [column for column in requested if column in frame.columns]
    if len(columns) < len(requested):
        missing = ", ".join(str(column) for column in requested if column not in frame.columns)
        parts.append(f'<p class="warn">Not in the published data: {_e(missing)}.</p>')
    if not columns:
        return "".join(parts)
    x_column = view.get("x_column") or "Index"
    if x_column != "Index" and x_column not in frame.columns:
        parts.append(f'<p class="warn">X column {_e(x_column)} is not in the published data; drawn against the row index.</p>')
        x_range = None
    x_values, x_label = resolve_x_values(frame, x_column)
    x = (x_values.to_series() if isinstance(x_values, pd.Index) else x_values).reset_index(drop=True)
    rows = _view_rows(x, x_range)
    if rows.size == 0:
        parts.append('<p class="warn">No published rows fall inside the recorded X range.</p>')
        return "".join(parts)
    in_range = rows.size
    stride = _stride(in_range, MAX_PLOT_POINTS)
    rows = rows[::stride]
    x_shown = x.iloc[rows] if pd.api.types.is_datetime64_any_dtype(x) else pd.to_numeric(x.iloc[rows], errors="coerce")
    subplots = bool(view.get("subplots")) and len(columns) > 1
    figure = Figure(figsize=(9, 1.6 * len(columns) + 0.8) if subplots else (9, 3.6))
    axes = figure.subplots(len(columns) if subplots else 1, 1, sharex=True, squeeze=False)[:, 0]
    log_scale = view.get("y_scale") == "log"
    non_positive = False
    for index, column in enumerate(columns):
        axis = axes[index] if subplots else axes[0]
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)[rows]
        non_positive = non_positive or bool(np.any(values <= 0))
        axis.plot(x_shown, values, color=VIEW_COLORS[index % len(VIEW_COLORS)], linewidth=0.9, label=str(column))
        if subplots:
            axis.set_ylabel(str(column), rotation=0, ha="right", va="center", fontsize="small")
    for axis in axes:
        axis.grid(True, alpha=0.3)
        if log_scale:
            axis.set_yscale("log")
    if not subplots:
        axes[0].legend(loc="best", fontsize="small")
    axes[0].set_title(title)
    axes[-1].set_xlabel(x_label)
    if pd.api.types.is_datetime64_any_dtype(x):
        figure.autofmt_xdate()
    notes = [f"{in_range} of {len(frame)} published rows in range"]
    if stride > 1:
        notes.append(f"reduced resolution: every {stride}. row shown")
    if log_scale and non_positive:
        notes.append("values <= 0 are not shown on the log axis")
    parts.append(_figure_html(figure, f"{title}: " + "; ".join(notes) + "."))
    return "".join(parts)


def build_publish_report(app, publish_step_id: str, generated_at: datetime | None = None) -> str:
    history = app.operation_history
    steps = history.steps
    numbers = {step.id: index + 1 for index, step in enumerate(steps)}
    publish = next((step for step in steps if step.id == publish_step_id), None)
    if publish is None or publish.operation != "publish":
        raise ValueError("Select a publish node to generate a report.")
    parameters = json.loads(publish.parameters_json)
    linked_ids = parameters.get("workspace_steps")
    warnings: list[str] = []
    if not isinstance(linked_ids, list):
        linked_ids = []
        warnings.append("This publish predates operation linking; no workspace operations are recorded for it.")
    linked = [step for step in steps if step.id in linked_ids]
    if len(linked) != len(linked_ids):
        warnings.append(f"{len(linked_ids) - len(linked)} linked operation(s) were deleted from the history and are not shown.")
    if before_append_step(publish):
        warnings.append(
            "This publish was created before rows were appended upstream; its dataset still holds only the earlier data."
        )
    context = app.dataset_contexts.get(publish.label)
    name = dataset_display_name(publish.label, context)
    frame = app.data_frames.get(publish.label)
    data_available = context is not None and frame is not None and context.revision_id == publish.output_revision
    if not data_available:
        warnings.append("The published dataset is no longer loaded in this exact revision; data sections are omitted.")
    published_input = publish.input_revisions[0] if publish.input_revisions else ""
    candidates = history.report_candidates(publish_step_id)
    enabled_ids = {
        step.id for step in candidates if history.report_node_enabled(publish_step_id, step.id)
    }
    overrides = history.report_selection.get(publish_step_id, {})
    linked = [
        step for step in candidates
        if step.id in enabled_ids and (step.id in linked_ids or overrides.get(step.id) is True)
    ]
    if any(not step.tracked for step in linked):
        warnings.append("Some workspace operations were untracked; their parameters are unknown.")

    sections: list[ReportSection] = []
    source = parameters.get("source_dataset")
    overview = {
        "Published dataset": name,
        "Registry path": publish.label,
        "Published from": dataset_display_name(source, app.dataset_contexts.get(source)) if source else "unknown",
        "Published (UTC)": publish.timestamp,
        "Publish node": f"#{numbers[publish.id]}",
        "Output revision": publish.output_revision,
    }
    sections.append(ReportSection("Overview", _key_values(overview)))
    excluded_count = sum(not enabled for enabled in overrides.values())
    if excluded_count:
        sections.append(ReportSection(
            "Report Selection",
            f'<p class="note">{excluded_count} node(s) intentionally excluded from this report. '
            "Pipeline calculations and saved results are unchanged. Published data summaries always remain included.</p>",
        ))

    operation_rows = []
    for step in linked:
        kind = "result snapshot" if step.id in history.artifact_tables else ("untracked" if not step.tracked else "operation")
        if step.operation == REPORT_VIEW_OPERATION:
            kind = "report view"
        shown = {key: value for key, value in json.loads(step.parameters_json).items() if key != "result_tables"}
        text = json.dumps(shown, default=str)
        if len(text) > 200 or kind in {"result snapshot", "report view"}:
            text = {"result snapshot": "see result section", "report view": "see view section"}.get(kind, text[:200] + " ...")
        operation_rows.append(
            f"<tr><td>{numbers[step.id]}</td><td>{_e(step.operation)}</td><td>{_e(kind)}</td>"
            f"<td>{_e(step.timestamp)}</td><td><code>{_e(text)}</code></td>"
            f"<td>{_e(history.notes.get(step.id, ''))}</td></tr>"
        )
    sections.append(ReportSection(
        "Workspace Operations (in pipeline order)",
        _table_panel('<table class="data"><tr><th>#</th><th>Operation</th><th>Kind</th><th>UTC</th><th>Parameters</th>'
        "<th>Decision note</th></tr>"
        + "".join(operation_rows) + "</table>") if operation_rows else '<p class="note">No linked operations.</p>',
    ))

    lineage = history.lineage(publish.output_revision)
    trail = [
        step for step in lineage
        if (step.id in enabled_ids or step.id == publish.id)
        and (step.id in history.notes or before_append_step(step))
    ]
    trail_rows = "".join(
        f"<tr><td>{numbers[step.id]}</td><td>{_e(step.operation)}</td>"
        f"<td>{_e(dataset_display_name(step.label, app.dataset_contexts.get(step.label)))}</td>"
        f"<td>{_e(based_on_text(step) or 'current data of that node')}</td>"
        f"<td>{_e(history.notes.get(step.id, '-'))}</td></tr>"
        for step in trail
    )
    sections.append(ReportSection(
        "Decision Trail",
        '<p class="note">Annotated steps and results in the lineage of this dataset (from loading onward), '
        "including evidence computed on earlier data before appends.</p>"
        + (
            _table_panel('<table class="data"><tr><th>#</th><th>Step</th><th>Dataset</th><th>Based on</th><th>Decision note</th></tr>'
            + trail_rows + "</table>") if trail_rows else '<p class="note">No decision notes recorded.</p>'
        ),
    ))

    if data_available:
        statistics = build_statistics_frame(frame)
        roles = context.column_roles
        body = (
            f"<p>{len(frame)} rows, {len(frame.columns)} columns.</p>"
            + _key_values({str(column): roles.get(column, "-") for column in frame.columns})
            + (_table_html(statistics, max_rows=50, title="Statistics (numeric columns, full data)")
               if not statistics.empty else '<p class="note">No numeric columns.</p>')
            + _dataset_plot(frame, roles, [
                json.loads(step.parameters_json).get("output_column")
                for step in reversed(steps) if step.id in linked_ids
            ])
        )
        sections.append(ReportSection("Published Data", body))

    linked_ids_set = {step.id for step in linked}
    evidence = [
        step for step in lineage
        if step.id in enabled_ids and step.id not in linked_ids_set
        and (step.operation == REPORT_VIEW_OPERATION or step.id in history.artifact_tables
             or "result_tables" in json.loads(step.parameters_json))
    ]
    for step in linked + evidence:
        prefix = _note_html(history, step)
        if step.operation == REPORT_VIEW_OPERATION:
            title = json.loads(step.parameters_json).get("title") or "Time series"
            sections.append(ReportSection(
                f"View #{numbers[step.id]}: {title}",
                prefix + (_view_body(step, frame, published_input) if data_available
                else '<p class="warn">Published data unavailable; this view cannot be drawn.</p>'),
            ))
        elif step.id in history.artifact_tables or "result_tables" in json.loads(step.parameters_json):
            label = "Result" if step.id in linked_ids_set else "Evidence"
            sections.append(ReportSection(
                f"{label} #{numbers[step.id]}: {step.operation} ({dataset_display_name(step.label, app.dataset_contexts.get(step.label))})",
                prefix + _result_body(step, history.artifact_tables.get(step.id), published_input),
            ))

    try:
        version = read_app_version()
    except OSError:
        version = "unknown"
    stamp = (generated_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    warning_html = "".join(f'<li>{_e(text)}</li>' for text in warnings)
    body = "".join(f"<section><h2>{_e(section.title)}</h2>{section.body}</section>" for section in sections)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>EvalData Report - {_e(name)}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 2em auto; max-width: 1050px; color: #111827; }}
h1 {{ border-bottom: 3px solid #00745a; padding-bottom: .3em; overflow-wrap: anywhere; }}
h2 {{ color: #00745a; margin-top: 1.8em; }}
.table-panel {{ background: #f0f5fa; border-left: 4px solid #8daec7; border-radius: 6px;
    margin: .8em 0; padding: .5em .8em; }}
.table-scroll {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; margin: .2em 0; font-size: .9em; }}
th, td {{ border: 0; border-bottom: 1px solid #dce6ef; padding: 7px 10px; text-align: left;
    vertical-align: top; overflow-wrap: anywhere; }}
th {{ background: #e5edf5; color: #334155; font-weight: 600; }}
tr:last-child > th, tr:last-child > td {{ border-bottom: 0; }}
tbody tr:nth-child(even) td {{ background: #f7f9fc; }}
summary {{ cursor: pointer; color: #334155; font-weight: 600; padding: .25em 0; }}
summary:focus-visible {{ outline: 2px solid #0072b2; outline-offset: 3px; }}
details[open] > summary {{ margin-bottom: .5em; }}
.warn {{ background: #fff0cf; border-left: 4px solid #8a5700; padding: .4em .8em; }}
.note {{ color: #4b5563; font-size: .9em; }}
.decision {{ background: #e8f1fb; border-left: 4px solid #0072b2; padding: .4em .8em; }}
figure {{ margin: 1em 0; }} img {{ max-width: 100%; }} figcaption {{ color: #4b5563; font-size: .85em; }}
code {{ font-size: .85em; word-break: break-all; }}
</style></head><body>
<h1>EvalData Report: {_e(name)}</h1>
<p class="note">Generated {_e(stamp)} by EvalData {_e(version)} (prototype). Describes recorded history and saved results only;
it contains no automatic interpretation and is not a quality approval.</p>
{f'<ul class="warn">{warning_html}</ul>' if warnings else ''}
{body}
</body></html>
"""
