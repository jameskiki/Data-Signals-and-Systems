"""Reusable Tk rendering helpers for the analysis workspace."""

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont, ttk

import pandas as pd
from shared.column_roles import get_column_role, get_column_role_cell_colors, get_column_role_colors, get_column_role_label
from shared.dataframe_preview import render_dataframe_preview as render_shared_dataframe_preview
from shared.display_format import format_display_value

from .state import (
    CORRELATION_DIAGONAL_COLOR,
    CORRELATION_HEADER_COLOR,
    CORRELATION_NEGATIVE_THRESHOLD,
    CORRELATION_POSITIVE_THRESHOLD,
    CORRELATION_STRONG_NEGATIVE_COLOR,
    CORRELATION_STRONG_POSITIVE_COLOR,
    STATISTICS_COLUMNS,
    STATISTICS_COLUMN_LABELS,
)


@dataclass(frozen=True)
class TreeColumnSpec:
    """Column definition for build_data_tree."""

    key: str
    label: str
    width: int
    min_width: int
    anchor: str = "e"
    stretch: bool = False


def build_data_tree(
    container: ttk.Frame,
    columns: list[TreeColumnSpec],
    *,
    selectmode: str = "browse",
    clear: bool = True,
) -> ttk.Treeview:
    """Create a headed Treeview with vertical scrollbar inside *container*.

    Returns the tree ready for row insertion.
    """

    if clear:
        _clear_container(container)

    column_keys = [col.key for col in columns]
    tree = ttk.Treeview(container, columns=column_keys, show="headings", selectmode=selectmode)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    for col in columns:
        tree.heading(col.key, text=col.label)
        tree.column(col.key, width=col.width, minwidth=col.min_width, anchor=col.anchor, stretch=col.stretch)

    scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.config(yscrollcommand=scrollbar.set)

    return tree


def render_dataframe_preview(
    container: ttk.Frame,
    dataframe: pd.DataFrame,
    row_limit: int,
    column_roles: dict[str, str] | None = None,
) -> tk.Canvas:
    """Render a scrollable, role-colored preview of the first rows of the dataframe."""

    return render_shared_dataframe_preview(container, dataframe, row_limit, column_roles, layout="pack")


def render_statistics_tree(
    container: ttk.Frame,
    stats_frame: pd.DataFrame,
    column_roles: dict[str, str] | None = None,
) -> ttk.Treeview:
    """Render a compact engineering statistics tree."""

    tree_font = tkfont.nametofont("TkDefaultFont")
    name_width = _measure_tree_column_width(
        tree_font, "column", [str(row_name) for row_name in stats_frame.index], minimum=70, maximum=180,
    )
    col_specs = [TreeColumnSpec(key="column", label="column", width=name_width, min_width=name_width, anchor="w")]
    for column in STATISTICS_COLUMNS:
        label = STATISTICS_COLUMN_LABELS.get(column, column)
        values = [_format_stat_value(v) for v in stats_frame.get(column, pd.Series(dtype=object)).tolist()]
        width = _measure_tree_column_width(tree_font, label, values, minimum=44, maximum=90)
        col_specs.append(TreeColumnSpec(key=column, label=label, width=width, min_width=width, anchor="center"))

    tree = build_data_tree(container, col_specs)

    resolved_roles = column_roles or {}
    for role_name, (background, foreground) in {
        role: get_column_role_colors(role)
        for role in {get_column_role(resolved_roles, str(row_name)) for row_name in stats_frame.index}
    }.items():
        tree.tag_configure(role_name, background=background, foreground=foreground)

    for row_name, row_values in stats_frame.iterrows():
        formatted_values = [_format_stat_value(row_values[column]) for column in STATISTICS_COLUMNS]
        role_name = get_column_role(resolved_roles, str(row_name))
        tree.insert("", tk.END, values=[row_name, *formatted_values], tags=(role_name,))

    return tree


def render_correlation_view(container: ttk.Frame, correlation_frame: pd.DataFrame) -> tk.Canvas | None:
    """Render the correlation matrix as a scrollable, color-coded grid."""

    _clear_container(container)

    if correlation_frame.empty:
        ttk.Label(
            container,
            text="At least two numeric columns are required for correlations.",
            justify=tk.LEFT,
        ).pack(anchor="w")
        return None

    columns = [str(column) for column in correlation_frame.columns]
    row_labels = [f"{row_index}. {row_name}" for row_index, row_name in enumerate(correlation_frame.index, start=1)]
    rounded_frame = correlation_frame.round(3)
    outer_frame = ttk.Frame(container)
    outer_frame.pack(fill=tk.BOTH, expand=True)
    canvas = tk.Canvas(outer_frame, highlightthickness=0, borderwidth=0)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    vertical_scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
    vertical_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    horizontal_scrollbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=canvas.xview)
    horizontal_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.config(yscrollcommand=vertical_scrollbar.set, xscrollcommand=horizontal_scrollbar.set)

    grid_frame = ttk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=grid_frame, anchor="nw")
    header_font = tkfont.nametofont("TkDefaultFont").copy()
    header_font.configure(weight="bold")

    _build_correlation_header_cell(grid_frame, 0, 0, "#", header_font)
    for column_index, _column in enumerate(columns, start=1):
        _build_correlation_header_cell(grid_frame, 0, column_index, str(column_index), header_font)

    for row_index, row_label in enumerate(row_labels, start=1):
        _build_correlation_header_cell(grid_frame, row_index, 0, row_label, header_font, anchor="w")
        for column_index, column in enumerate(columns, start=1):
            value = rounded_frame.iloc[row_index - 1, column_index - 1]
            display_value = "" if (column_index - 1) > (row_index - 1) or pd.isna(value) else _format_correlation_value(value)
            background, foreground = _get_correlation_cell_colors(column_index - 1, row_index - 1, value)
            label = tk.Label(
                grid_frame,
                text=display_value,
                bg=background,
                fg=foreground,
                borderwidth=1,
                relief="solid",
                padx=8,
                pady=5,
                width=max(7, math.ceil(len(str(column)) * 0.85)),
                anchor="e",
            )
            label.grid(row=row_index, column=column_index, sticky="nsew")

    def _sync_scroll_region(_event: tk.Event | None = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _sync_window_size(event: tk.Event) -> None:
        canvas.itemconfigure(window_id, height=max(event.height, grid_frame.winfo_reqheight()))

    grid_frame.bind("<Configure>", _sync_scroll_region)
    canvas.bind("<Configure>", _sync_window_size)
    _sync_scroll_region()
    return canvas


def render_fft_peaks_tree(container: ttk.Frame, peaks_frame: pd.DataFrame, value_column_label: str = "Amp") -> ttk.Treeview | None:
    """Render a compact table of dominant spectral peaks."""

    _clear_container(container)

    if peaks_frame.empty:
        ttk.Label(container, text="No FFT peaks available.", justify=tk.LEFT).pack(anchor="w")
        return None

    tree = build_data_tree(container, [
        TreeColumnSpec("rank", "#", 45, 45, anchor="center"),
        TreeColumnSpec("frequency_hz", "Hz", 90, 90),
        TreeColumnSpec("amplitude", value_column_label, 100, 100),
    ], clear=False)

    for row in peaks_frame.itertuples(index=False):
        tree.insert(
            "",
            tk.END,
            values=(int(row.rank), _format_stat_value(row.frequency_hz), _format_stat_value(row.amplitude)),
        )

    return tree


def render_cycle_metrics_tree(container: ttk.Frame, metrics_frame: pd.DataFrame) -> ttk.Treeview | None:
    """Render a compact per-cycle metrics table."""

    _clear_container(container)

    if metrics_frame.empty:
        ttk.Label(container, text="No cycle metrics available.", justify=tk.LEFT).pack(anchor="w")
        return None

    col_specs = [TreeColumnSpec("cycle", "#", 45, 45, anchor="center")]
    if "status" in metrics_frame.columns:
        col_specs.append(TreeColumnSpec("status", "status", 78, 70, anchor="center"))
    col_specs.extend(
        [
            TreeColumnSpec("start", "start", 68, 60),
            TreeColumnSpec("end", "end", 68, 60),
            TreeColumnSpec("length", "len", 68, 60),
        ]
    )
    if "duration_seconds" in metrics_frame.columns:
        col_specs.append(TreeColumnSpec("duration_seconds", "dur [s]", 82, 72))
    col_specs.extend(
        [
            TreeColumnSpec("mean", "mean", 82, 72),
            TreeColumnSpec("std", "sd", 82, 72),
            TreeColumnSpec("min", "min", 82, 72),
            TreeColumnSpec("max", "max", 82, 72),
            TreeColumnSpec("rms", "rms", 82, 72),
            TreeColumnSpec("peak_to_peak", "p2p", 82, 72),
        ]
    )

    tree = build_data_tree(container, col_specs, selectmode="extended", clear=False)
    outlier_row_mask = _compute_cycle_outlier_row_mask(metrics_frame)
    tree.tag_configure("cycle-excluded", background="#f1f5f9", foreground="#64748b")
    tree.tag_configure("cycle-outlier", background="#fff7d6", foreground="#7c2d12")
    tree.tag_configure("cycle-excluded-outlier", background="#f8efe4", foreground="#7c2d12")

    for row_index, row in enumerate(metrics_frame.itertuples(index=False)):
        row_values = [int(row.cycle)]
        if "status" in metrics_frame.columns:
            row_values.append(str(row.status))
        row_values.extend(
            [
                int(row.start),
                int(row.end),
                int(row.length),
            ]
        )
        if "duration_seconds" in metrics_frame.columns:
            row_values.append(_format_stat_value(row.duration_seconds))
        row_values.extend(
            [
                _format_stat_value(row.mean),
                _format_stat_value(row.std),
                _format_stat_value(row.min),
                _format_stat_value(row.max),
                _format_stat_value(row.rms),
                _format_stat_value(row.peak_to_peak),
            ]
        )
        tree.insert(
            "",
            tk.END,
            values=tuple(row_values),
            tags=_get_cycle_tree_tags(row, outlier_row_mask.iloc[row_index]),
        )

    return tree


def _compute_cycle_outlier_row_mask(metrics_frame: pd.DataFrame) -> pd.Series:
    metric_columns = [
        column_name
        for column_name in ["length", "duration_seconds", "mean", "std", "min", "max", "rms", "peak_to_peak"]
        if column_name in metrics_frame.columns
    ]
    if not metric_columns:
        return pd.Series(False, index=metrics_frame.index, dtype=bool)

    outlier_mask = pd.Series(False, index=metrics_frame.index, dtype=bool)
    for column_name in metric_columns:
        numeric_values = pd.to_numeric(metrics_frame[column_name], errors="coerce")
        valid_values = numeric_values.dropna()
        if len(valid_values) < 4:
            continue
        first_quartile = float(valid_values.quantile(0.25))
        third_quartile = float(valid_values.quantile(0.75))
        iqr = third_quartile - first_quartile
        if iqr <= 0.0:
            continue
        lower_bound = first_quartile - 1.5 * iqr
        upper_bound = third_quartile + 1.5 * iqr
        outlier_mask |= (numeric_values < lower_bound) | (numeric_values > upper_bound)
    return outlier_mask.fillna(False)


def _get_cycle_tree_tags(row: object, is_outlier: bool) -> tuple[str, ...]:
    status_value = str(getattr(row, "status", "")).strip().lower()
    if status_value == "excluded" and is_outlier:
        return ("cycle-excluded-outlier",)
    if status_value == "excluded":
        return ("cycle-excluded",)
    if is_outlier:
        return ("cycle-outlier",)
    return ()


def _clear_container(container: ttk.Frame) -> None:
    for widget in container.winfo_children():
        widget.destroy()


def _build_preview_cell(
    grid_frame: tk.Frame,
    row_index: int,
    column_index: int,
    text: str,
    background: str,
    foreground: str,
    bold: bool = False,
    anchor: str = "w",
) -> None:
    font = ("TkDefaultFont", 9, "bold") if bold else ("TkDefaultFont", 9)
    label = tk.Label(
        grid_frame,
        text=text,
        bg=background,
        fg=foreground,
        borderwidth=1,
        relief="solid",
        padx=6,
        pady=4,
        justify=tk.LEFT,
        anchor=anchor,
        font=font,
        wraplength=180,
    )
    label.grid(row=row_index, column=column_index, sticky="nsew")


def _measure_tree_column_width(
    tree_font: tkfont.Font,
    header: str,
    values: list[str],
    minimum: int,
    maximum: int,
) -> int:
    measured_width = tree_font.measure(header)
    for value in values:
        measured_width = max(measured_width, tree_font.measure(value))
    return max(minimum, min(maximum, measured_width + 16))


def _build_correlation_header_cell(
    grid_frame: ttk.Frame,
    row_index: int,
    column_index: int,
    text: str,
    font: tkfont.Font,
    anchor: str = "center",
) -> None:
    label = tk.Label(
        grid_frame,
        text=text,
        bg="#eef2f6",
        fg=CORRELATION_HEADER_COLOR,
        font=font,
        borderwidth=1,
        relief="solid",
        padx=8,
        pady=5,
        anchor=anchor,
    )
    label.grid(row=row_index, column=column_index, sticky="nsew")


def _get_correlation_cell_colors(column_index: int, row_index: int, value: object) -> tuple[str, str]:
    if column_index > row_index or pd.isna(value):
        return "#f7f7f7", "#aaaaaa"

    numeric_value = float(value)
    if column_index == row_index:
        return "#dbeafe", CORRELATION_DIAGONAL_COLOR
    if numeric_value >= CORRELATION_POSITIVE_THRESHOLD:
        return "#d9f2d9", CORRELATION_STRONG_POSITIVE_COLOR
    if numeric_value <= CORRELATION_NEGATIVE_THRESHOLD:
        return "#f8d7da", CORRELATION_STRONG_NEGATIVE_COLOR
    if numeric_value >= 0:
        return "#eef7ee", "#2f4f2f"
    return "#fbefef", "#6d2e2e"


def _format_correlation_value(value: object) -> str:
    return format_display_value(value)


def _format_preview_value(value: object) -> str:
    return format_display_value(value)


def _format_stat_value(value: object) -> str:
    return format_display_value(value)
