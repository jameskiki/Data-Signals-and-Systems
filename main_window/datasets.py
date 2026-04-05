"""Dataset registry and table helper functions for the main application."""

import os
import re
from dataclasses import dataclass, field

import pandas as pd
import tkinter as tk
from tkinter import ttk

from data_ops.summary import summarize_dataframe


COLUMN_ROLE_LABELS = {
    "time": "TIME",
    "input": "INPUT",
    "output": "OUTPUT",
    "signal": "SIGNAL",
    "metadata": "META",
}

COLUMN_ROLE_COLORS = {
    "time": ("#dbeafe", "#111111"),
    "input": ("#fff4cc", "#111111"),
    "output": ("#d9f2d9", "#111111"),
    "signal": ("#f3e5f5", "#111111"),
    "metadata": ("#eceff1", "#111111"),
}

COLUMN_ROLE_PLOT_COLORS = {
    "time": "#0d47a1",
    "input": "#a16207",
    "output": "#1b5e20",
    "signal": "#7b1fa2",
    "metadata": "#455a64",
}

COLUMN_ROLE_PRIORITY = {
    "output": 0,
    "signal": 1,
    "input": 2,
    "metadata": 3,
    "time": 4,
}

COLUMN_ROLE_NAMES = list(COLUMN_ROLE_LABELS.keys())


@dataclass
class DatasetContext:
    """Lineage information for one prepared dataset."""

    source_paths: list[str] = field(default_factory=list)
    description: str = ""
    column_roles: dict[str, str] = field(default_factory=dict)


def register_dataset(
    app,
    dataset_path: str,
    dataframe: pd.DataFrame,
    source_paths: list[str] | None = None,
    description: str = "",
    column_roles: dict[str, str] | None = None,
) -> None:
    """Register or replace a dataset and its lineage context."""

    app.data_frames[dataset_path] = dataframe.copy()
    app.dataset_contexts[dataset_path] = DatasetContext(
        source_paths=list(dict.fromkeys(source_paths or [dataset_path])),
        description=description,
        column_roles=infer_column_roles(dataframe, column_roles),
    )


def infer_column_roles(dataframe: pd.DataFrame, preferred_roles: dict[str, str] | None = None) -> dict[str, str]:
    """Infer lightweight semantic roles for dataframe columns."""

    preferred_roles = preferred_roles or {}
    column_roles: dict[str, str] = {}
    for column in dataframe.columns:
        column_name = str(column)
        if column_name in preferred_roles:
            column_roles[column_name] = preferred_roles[column_name]
            continue
        column_roles[column_name] = _infer_column_role(column_name, dataframe[column])
    return column_roles


def project_column_roles(column_roles: dict[str, str], dataframe: pd.DataFrame) -> dict[str, str]:
    """Project stored roles onto a derived dataframe, re-inferring only new columns."""

    available_columns = {str(column) for column in dataframe.columns}
    preserved_roles = {str(column): role for column, role in column_roles.items() if str(column) in available_columns}
    return infer_column_roles(dataframe, preserved_roles)


def update_projected_column_roles(
    column_roles: dict[str, str],
    dataframe: pd.DataFrame,
    role_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Project roles to a new dataframe and apply any explicit role overrides."""

    updated_roles = project_column_roles(column_roles, dataframe)
    for column_name, role_name in (role_overrides or {}).items():
        if str(column_name) in dataframe.columns and role_name:
            updated_roles[str(column_name)] = role_name
    return updated_roles


def summarize_column_roles(column_roles: dict[str, str]) -> str:
    """Return a compact human-readable summary of stored column roles."""

    if not column_roles:
        return ""

    time_column = get_preferred_role_column(column_roles, "time")
    input_column = get_preferred_role_column(column_roles, "input")
    output_column = get_preferred_role_column(column_roles, "output")
    signal_columns = [column for column, role in column_roles.items() if role == "signal"]
    metadata_count = sum(1 for role in column_roles.values() if role == "metadata")

    summary_parts: list[str] = []
    if time_column:
        summary_parts.append(f"time={time_column}")
    if input_column:
        summary_parts.append(f"input={input_column}")
    if output_column:
        summary_parts.append(f"output={output_column}")
    if signal_columns:
        shown_signals = ", ".join(signal_columns[:3])
        if len(signal_columns) > 3:
            shown_signals += f", +{len(signal_columns) - 3} more"
        summary_parts.append(f"signals={shown_signals}")
    if metadata_count:
        summary_parts.append(f"metadata={metadata_count}")
    return "Roles: " + " | ".join(summary_parts)


def get_preferred_role_column(
    column_roles: dict[str, str],
    *roles: str,
    available_columns: list[str] | None = None,
) -> str | None:
    """Return the first column matching any preferred role and availability filter."""

    available_set = set(available_columns) if available_columns is not None else None
    for role in roles:
        for column, column_role in column_roles.items():
            if column_role != role:
                continue
            if available_set is not None and column not in available_set:
                continue
            return column
    return None


def get_column_role(column_roles: dict[str, str], column_name: str) -> str:
    """Return the stored role for one column, defaulting to metadata."""

    return column_roles.get(str(column_name), "metadata")


def get_column_role_label(column_roles: dict[str, str], column_name: str) -> str:
    """Return a short human-readable role label for one column."""

    role = get_column_role(column_roles, column_name)
    return COLUMN_ROLE_LABELS.get(role, role.upper())


def get_role_label(role: str) -> str:
    """Return the human-readable label for one role name."""

    return COLUMN_ROLE_LABELS.get(role, role.upper())


def get_available_column_roles() -> list[str]:
    """Return the supported semantic column role names in UI order."""

    return list(COLUMN_ROLE_NAMES)


def get_column_role_colors(role: str) -> tuple[str, str]:
    """Return background and foreground colors for one role."""

    return COLUMN_ROLE_COLORS.get(role, COLUMN_ROLE_COLORS["metadata"])


def get_column_role_plot_color(role: str) -> str:
    """Return a saturated plot color for one role."""

    return COLUMN_ROLE_PLOT_COLORS.get(role, COLUMN_ROLE_PLOT_COLORS["metadata"])


def get_column_role_cell_colors(role: str) -> tuple[str, str]:
    """Return a lighter color pair for table cell fills."""

    background, foreground = get_column_role_colors(role)
    return _lighten_hex(background, 0.72), foreground


def sort_columns_by_role(columns: list[str], column_roles: dict[str, str]) -> list[str]:
    """Sort columns by semantic role before falling back to name."""

    return sorted(
        [str(column) for column in columns],
        key=lambda column_name: (
            COLUMN_ROLE_PRIORITY.get(get_column_role(column_roles, column_name), len(COLUMN_ROLE_PRIORITY)),
            column_name.lower(),
        ),
    )


def colorize_listbox_by_role(listbox: tk.Listbox | None, values: list[str], column_roles: dict[str, str]) -> None:
    """Apply per-row role-aware colors to a Tk listbox."""

    if listbox is None:
        return

    listbox.configure(selectforeground="#111111")
    for index, value in enumerate(values):
        role_name = "metadata" if value == "Index" else get_column_role(column_roles, value)
        background, foreground = get_column_role_cell_colors(role_name)
        listbox.itemconfig(index, background=background, foreground=foreground)


def apply_role_combobox_style(
    combobox: ttk.Combobox | None,
    column_roles: dict[str, str],
    selected_value: str,
) -> None:
    """Apply a role-aware readonly style to a combobox based on its current value."""

    if combobox is None:
        return

    role_name = "metadata" if selected_value == "Index" else get_column_role(column_roles, selected_value)
    background, foreground = get_column_role_cell_colors(role_name)
    style_name = f"Role.{role_name}.TCombobox"
    style = ttk.Style(combobox)
    style.configure(
        style_name,
        fieldbackground=background,
        background=background,
        foreground=foreground,
        arrowcolor=foreground,
    )
    style.map(
        style_name,
        fieldbackground=[("readonly", background), ("!disabled", background)],
        background=[("readonly", background), ("!disabled", background)],
        foreground=[("readonly", foreground), ("!disabled", foreground)],
        selectbackground=[("readonly", background)],
        selectforeground=[("readonly", foreground)],
    )
    combobox.configure(style=style_name)


def apply_literal_role_combobox_style(combobox: ttk.Combobox | None, role_name: str) -> None:
    """Apply a role-aware readonly style to a combobox given a direct role name."""

    if combobox is None:
        return

    background, foreground = get_column_role_cell_colors(role_name or "metadata")
    style_name = f"LiteralRole.{role_name or 'metadata'}.TCombobox"
    style = ttk.Style(combobox)
    style.configure(
        style_name,
        fieldbackground=background,
        background=background,
        foreground=foreground,
        arrowcolor=foreground,
    )
    style.map(
        style_name,
        fieldbackground=[("readonly", background), ("!disabled", background)],
        background=[("readonly", background), ("!disabled", background)],
        foreground=[("readonly", foreground), ("!disabled", foreground)],
        selectbackground=[("readonly", background)],
        selectforeground=[("readonly", foreground)],
    )
    combobox.configure(style=style_name)


def _lighten_hex(color: str, factor: float) -> str:
    color = color.lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    red = int(red + (255 - red) * factor)
    green = int(green + (255 - green) * factor)
    blue = int(blue + (255 - blue) * factor)
    return f"#{red:02x}{green:02x}{blue:02x}"


def collect_source_paths(app, dataset_paths: list[str]) -> list[str]:
    """Collect de-duplicated source paths for one or more datasets."""

    source_paths: list[str] = []
    for dataset_path in dataset_paths:
        context = app.dataset_contexts.get(dataset_path)
        if context is None:
            source_paths.append(dataset_path)
        else:
            source_paths.extend(context.source_paths)
    return list(dict.fromkeys(source_paths))


def refresh_dataset_table(app) -> None:
    """Rebuild the dataset table from the registered datasets."""

    if app.dataset_table is None:
        return

    selected_paths = set(app._get_selected_file_paths())
    for item_id in app.dataset_table.get_children():
        app.dataset_table.delete(item_id)

    for path, dataframe in app.data_frames.items():
        context = app.dataset_contexts.get(path, DatasetContext(source_paths=[path], description="", column_roles={}))
        source_label = format_source_paths(context.source_paths)
        summary = summarize_dataframe(dataframe)
        app.dataset_table.insert(
            "",
            tk.END,
            iid=path,
            values=(
                path,
                summary.row_count,
                summary.column_count,
                summary.numeric_column_count,
                summary.datetime_column_count,
                summary.total_missing_count,
                source_label,
                summary.time_range_text or "-",
                summary.missing_columns_text or "-",
            ),
        )

    for path in selected_paths:
        if app.dataset_table.exists(path):
            app.dataset_table.selection_add(path)


def select_dataset_in_table(app, file_path: str) -> None:
    """Select and reveal one dataset in the dataset table."""

    if app.dataset_table is None or not app.dataset_table.exists(file_path):
        return

    app.dataset_table.selection_set(file_path)
    app.dataset_table.focus(file_path)
    app.dataset_table.see(file_path)


def build_virtual_dataset_path(data_frames: dict[str, pd.DataFrame], source_path: str, suffix: str) -> str:
    """Create a unique virtual dataset path derived from a source path and suffix."""

    source_dir = os.path.dirname(source_path)
    stem, extension = os.path.splitext(os.path.basename(source_path))
    safe_suffix = re.sub(r"[^A-Za-z0-9_-]+", "_", suffix.strip()).strip("_") or "prepared"
    extension = extension or ".csv"

    candidate = os.path.join(source_dir, f"{stem}__{safe_suffix}{extension}")
    counter = 2
    while candidate in data_frames:
        candidate = os.path.join(source_dir, f"{stem}__{safe_suffix}_{counter}{extension}")
        counter += 1
    return candidate


def format_source_paths(source_paths: list[str]) -> str:
    """Return a compact label for one or more lineage source paths."""

    if not source_paths:
        return ""
    basenames = [os.path.basename(path) for path in source_paths]
    if len(basenames) == 1:
        return f"Source experiment: {basenames[0]}"
    return "Source experiments: " + ", ".join(basenames)


def parse_split_ranges(raw_text: str) -> list[tuple[int, int]]:
    """Parse line-based split ranges written as start:end."""

    ranges: list[tuple[int, int]] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid range '{line}'. Use start:end")
        start_text, end_text = line.split(":", 1)
        ranges.append((int(start_text.strip()), int(end_text.strip())))
    if not ranges:
        raise ValueError("Provide at least one index range")
    return ranges


def _infer_column_role(column_name: str, series: pd.Series) -> str:
    normalized_name = column_name.strip().lower()

    if pd.api.types.is_datetime64_any_dtype(series):
        return "time"
    if any(token in normalized_name for token in ("time", "timestamp", "datetime", "date")):
        return "time"
    if any(token in normalized_name for token in ("input", "actuator", "excitation", "command", "drive", "setpoint")):
        return "input"
    if any(token in normalized_name for token in ("output", "response", "measured")):
        return "output"
    if any(token in normalized_name for token in ("temp", "temperature", "phase", "marker", "status", "label", "id")):
        return "metadata"
    if pd.api.types.is_numeric_dtype(series):
        return "signal"
    return "metadata"
