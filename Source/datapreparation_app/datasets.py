"""Dataset registry and table helper functions for the main application."""

import os
import re
from dataclasses import dataclass, field

import pandas as pd
import tkinter as tk

from Source.shared.column_roles import (
    apply_literal_role_combobox_style,
    apply_role_combobox_style,
    colorize_listbox_by_role,
    get_available_column_roles,
    get_column_role,
    get_column_role_cell_colors,
    get_column_role_colors,
    get_column_role_label,
    get_column_role_plot_color,
    get_preferred_role_column,
    get_role_label,
    infer_column_roles,
    project_column_roles,
    sort_columns_by_role,
    summarize_column_roles,
    update_projected_column_roles,
)
from Source.data_ops.models import DataSummary
from Source.data_ops.summary import summarize_dataframe


@dataclass
class DatasetContext:
    """Lineage information for one prepared dataset."""

    source_paths: list[str] = field(default_factory=list)
    description: str = ""
    column_roles: dict[str, str] = field(default_factory=dict)
    cached_summary: DataSummary | None = None


def register_dataset(
    app,
    dataset_path: str,
    dataframe: pd.DataFrame,
    source_paths: list[str] | None = None,
    description: str = "",
    column_roles: dict[str, str] | None = None,
) -> None:
    """Register or replace a dataset and its lineage context."""

    app.data_frames[dataset_path] = dataframe
    app.dataset_contexts[dataset_path] = DatasetContext(
        source_paths=list(dict.fromkeys(source_paths or [dataset_path])),
        description=description,
        column_roles=infer_column_roles(dataframe, column_roles),
        cached_summary=None,
    )


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
    """Rebuild the compact dataset selector table."""

    if app.dataset_table is None:
        return

    selected_paths = {
        iid
        for iid in app.dataset_table.selection()
        if app.dataset_table.exists(iid)
    }
    for item_id in app.dataset_table.get_children():
        app.dataset_table.delete(item_id)

    for path, dataframe in app.data_frames.items():
        context = app.dataset_contexts.get(path, DatasetContext(source_paths=[path], description="", column_roles={}))
        if context.cached_summary is None:
            context.cached_summary = summarize_dataframe(dataframe, include_details=False)
        summary = context.cached_summary
        app.dataset_table.insert(
            "",
            tk.END,
            iid=path,
            values=(
                os.path.basename(path),
                summary.row_count,
                summary.column_count,
                summary.total_missing_count,
                format_source_paths(context.source_paths),
            ),
        )

    valid_selected = {path for path in selected_paths if app.dataset_table.exists(path)}
    if valid_selected:
        for path in valid_selected:
            app.dataset_table.selection_add(path)
    elif app.data_frames:
        # Auto-select the first remaining dataset when the previously selected one was removed
        first_path = next(iter(app.data_frames))
        if app.dataset_table.exists(first_path):
            app.dataset_table.selection_set(first_path)


def select_dataset_in_table(app, file_path: str) -> None:
    """Select and reveal one dataset in the selector table."""

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
