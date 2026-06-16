"""Preview table and overview plot helpers for the main application."""

import tkinter as tk
from tkinter import ttk

from matplotlib.widgets import SpanSelector
from Source.shared.dataframe_preview import render_dataframe_preview as render_shared_dataframe_preview
from Source.shared.plot_utils import create_plot_figure
from Source.shared.plot_options import PlotOptions
import pandas as pd

from .datasets import (
    get_column_role,
    sort_columns_by_role,
)


def refresh_preview_plot(
    app,
    dataframe: pd.DataFrame,
    figure_size: tuple[float, float],
    max_columns: int,
    column_roles: dict[str, str] | None = None,
) -> None:
    """Render the index-based preview plot for the selected dataset using shared plot utilities."""
    if app._preview_plot_container is None:
        return

    resolved_roles = column_roles or {}
    preview_columns = get_selected_preview_plot_columns(app, dataframe, max_columns, resolved_roles)
    if not preview_columns:
        clear_preview_plot(app, "No numeric non-time columns available for overview plot.")
        return

    # Determine x-axis column
    time_col = _get_time_role_column(resolved_roles)
    if time_col is not None and time_col in dataframe.columns:
        xcol = time_col
    else:
        xcol = "Index"

    # Build PlotOptions for preview
    plot_options = PlotOptions(
        cols_to_plot=preview_columns,
        xcol=xcol,
        use_subplots=False,
        title="Overlay Plot",
        y_label="Value",
    )

    # Use a single dummy file path and data_frames map for compatibility with plot_utils
    dummy_path = "preview"
    data_frames = {dummy_path: dataframe}
    selected_file_paths = [dummy_path]

    figure = create_plot_figure(
        plot_options=plot_options,
        selected_file_paths=selected_file_paths,
        data_frames=data_frames,
        column_roles=resolved_roles,
    )

    app._render_embedded_figure(
        figure=figure,
        figure_attr="_preview_plot_figure",
        canvas_attr="_preview_plot_canvas",
        toolbar_attr="_preview_plot_toolbar",
        container=app._preview_plot_container,
        root_window=app.root,
        draw_idle_on_reuse=True,
        clear_container_before_create=True,
    )

    # Attach SpanSelector for visual range picking (use the first axis)
    axes = figure.get_axes()
    if axes:
        _attach_span_selector(app, axes[0])


def refresh_preview_plot_signal_controls(
    app,
    dataframe: pd.DataFrame,
    max_columns: int,
    column_roles: dict[str, str] | None = None,
) -> None:
    """Refresh selectable preview plot channels."""

    if not hasattr(app, "_set_preview_plot_signal_options"):
        return

    resolved_roles = column_roles or {}
    available_columns = get_preview_plot_columns(dataframe, resolved_roles)
    selected_columns = _get_preserved_preview_plot_columns(app, available_columns)
    app._set_preview_plot_signal_options(
        available_columns,
        resolved_roles,
        max_columns,
        selected_columns=selected_columns[:max_columns],
    )


def refresh_selected_dataset_preview_plot(app, figure_size: tuple[float, float], max_columns: int) -> None:
    """Refresh the preview plot for the single selected dataset when available."""

    selected_path = app._get_single_selected_file_path()
    if selected_path is None:
        clear_preview_plot(app, "Select exactly one dataset to show the overview plot.")
        return
    roles = _get_selected_dataset_roles(app, selected_path)
    dataframe = app.data_frames[selected_path]
    refresh_preview_plot(
        app,
        dataframe,
        figure_size,
        max_columns,
        roles,
    )


def handle_preview_plot_control_changed(app, figure_size: tuple[float, float], max_columns: int) -> None:
    """Handle selection changes for preview plot controls."""

    refresh_selected_dataset_preview_plot(app, figure_size, max_columns)


def get_selected_preview_plot_columns(
    app,
    dataframe: pd.DataFrame,
    max_columns: int,
    column_roles: dict[str, str] | None = None,
) -> list[str]:
    """Return selected preview plot columns constrained to valid numeric series."""

    available_columns = get_preview_plot_columns(dataframe, column_roles)
    if not hasattr(app, "_get_selected_preview_plot_columns_from_selector"):
        return available_columns[:max_columns]

    selected_columns = app._get_selected_preview_plot_columns_from_selector()
    if not selected_columns:
        return available_columns[:max_columns]

    return [column for column in selected_columns if column in available_columns]


def _get_preserved_preview_plot_columns(app, available_columns: list[str]) -> list[str]:
    if not hasattr(app, "_get_selected_preview_plot_columns_from_selector"):
        return available_columns

    selected_columns = app._get_selected_preview_plot_columns_from_selector()
    preserved_columns = [column for column in selected_columns if column in available_columns]
    return preserved_columns or available_columns


def clear_preview_plot(app, message: str | None = None) -> None:
    """Clear the preview plot area and optionally show a message."""

    if app._preview_plot_figure is not None:
        import matplotlib.pyplot as plt
        plt.close(app._preview_plot_figure)
        app._preview_plot_figure = None
    app._preview_plot_canvas = None
    app._preview_plot_toolbar = None
    if app._preview_plot_container is None:
        return
    for widget in app._preview_plot_container.winfo_children():
        widget.destroy()
    if message:
        ttk.Label(app._preview_plot_container, text=message, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)


def refresh_preview_table(app, dataframe: pd.DataFrame, row_limit: int, column_roles: dict[str, str] | None = None) -> None:
    """Render the dataframe head preview table."""

    if app._preview_table_container is None:
        return

    render_shared_dataframe_preview(
        app._preview_table_container,
        dataframe,
        row_limit,
        column_roles,
        layout="grid",
        empty_message="The dataset is empty.",
    )


def clear_preview_table(app, message: str | None = None) -> None:
    """Clear the preview table area and optionally show a message."""

    if app._preview_table_container is None:
        return

    for widget in app._preview_table_container.winfo_children():
        widget.destroy()
    if message:
        ttk.Label(app._preview_table_container, text=message, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)


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


def get_preview_plot_columns(dataframe: pd.DataFrame, column_roles: dict[str, str] | None = None) -> list[str]:
    """Return numeric, non-time-like columns suitable for the overview plot."""

    preview_columns: list[str] = []
    resolved_roles = column_roles or {}
    for column in dataframe.columns:
        column_name = str(column)
        if get_column_role(resolved_roles, column_name) == "time":
            continue
        if any(token in column_name.lower() for token in ["time", "date", "timestamp"]):
            continue
        if pd.api.types.is_datetime64_any_dtype(dataframe[column]):
            continue
        numeric_values = pd.to_numeric(dataframe[column], errors="coerce")
        if numeric_values.notna().any():
            preview_columns.append(column_name)
    return sort_columns_by_role(preview_columns, resolved_roles)


def _get_selected_dataset_roles(app, selected_path: str) -> dict[str, str]:
    context = app.dataset_contexts.get(selected_path)
    return dict(context.column_roles) if context is not None else {}


def _get_time_role_column(column_roles: dict[str, str]) -> str | None:
    """Return the first column with role 'time', or None."""
    for column, role in column_roles.items():
        if role == "time":
            return column
    return None


def _attach_span_selector(app, axis) -> None:
    """Attach a horizontal SpanSelector to let users drag-select a row range."""

    def _on_select(xmin: float, xmax: float) -> None:
        if hasattr(app, "_set_row_range_from_span"):
            app._set_row_range_from_span(xmin, xmax)

    span = SpanSelector(
        axis,
        _on_select,
        "horizontal",
        useblit=True,
        props=dict(alpha=0.25, facecolor="#3b82f6"),
        interactive=True,
        drag_from_anywhere=True,
    )
    # Keep a reference so matplotlib doesn't garbage-collect it
    app._row_range_span_selector = span
