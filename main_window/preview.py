"""Preview table and overview plot helpers for the main application."""

import tkinter as tk
from tkinter import ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import SpanSelector
import pandas as pd

from display_format import apply_numeric_axis_format, format_display_value
from .datasets import (
    get_column_role,
    get_column_role_cell_colors,
    get_column_role_colors,
    get_column_role_label,
    get_column_role_plot_color,
    sort_columns_by_role,
)


def refresh_preview_plot(
    app,
    dataframe: pd.DataFrame,
    figure_size: tuple[float, float],
    max_columns: int,
    column_roles: dict[str, str] | None = None,
) -> None:
    """Render the index-based preview plot for the selected dataset."""

    if app._preview_plot_container is None:
        return

    resolved_roles = column_roles or {}
    preview_columns = get_selected_preview_plot_columns(app, dataframe, max_columns, resolved_roles)
    if not preview_columns:
        clear_preview_plot(app, "No numeric non-time columns available for overview plot.")
        return

    clear_preview_plot(app)
    figure, axis = plt.subplots(figsize=figure_size, dpi=100)
    preview_frame = dataframe.loc[:, preview_columns]

    # Use time-role column for x-axis when available
    time_col = _get_time_role_column(resolved_roles)
    if time_col is not None and time_col in dataframe.columns:
        x_values = pd.to_numeric(dataframe[time_col], errors="coerce")
        x_label = time_col
    else:
        x_values = range(len(preview_frame))
        x_label = "Index"

    for column in preview_columns:
        numeric_values = pd.to_numeric(preview_frame[column], errors="coerce")
        role_name = get_column_role(resolved_roles, str(column))
        axis.plot(
            x_values,
            numeric_values,
            linewidth=1.6,
            label=str(column),
            color=get_column_role_plot_color(role_name),
        )

    axis.set_title("Role-aware overview", fontsize=10)
    axis.set_xlabel(x_label, fontsize=9)
    axis.set_ylabel("Value", fontsize=9)
    axis.grid(True, alpha=0.28, color="#6b7280")
    axis.margins(x=0.02)
    apply_numeric_axis_format(axis, format_x=True, format_y=True)
    if axis.lines:
        axis.legend(fontsize=8, loc="upper right")
    figure.tight_layout()

    app._preview_plot_figure = figure
    app._preview_plot_canvas = FigureCanvasTkAgg(figure, master=app._preview_plot_container)
    app._preview_plot_canvas.draw()
    app._preview_plot_toolbar = NavigationToolbar2Tk(app._preview_plot_canvas, app._preview_plot_container)
    app._preview_plot_toolbar.update()
    app._preview_plot_toolbar.pack(side=tk.TOP, fill=tk.X)
    app._preview_plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # Attach SpanSelector for visual range picking
    _attach_span_selector(app, axis)


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

    clear_preview_table(app)
    preview_frame = dataframe.head(row_limit)
    if preview_frame.empty:
        ttk.Label(app._preview_table_container, text="The dataset is empty.", justify=tk.LEFT).pack(
            anchor="w", padx=5, pady=5
        )
        return

    resolved_roles = column_roles or {}
    outer_frame = ttk.Frame(app._preview_table_container)
    outer_frame.grid(row=0, column=0, sticky="nsew")
    outer_frame.rowconfigure(0, weight=1)
    outer_frame.columnconfigure(0, weight=1)

    canvas = tk.Canvas(outer_frame, highlightthickness=0, borderwidth=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    vertical_scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
    vertical_scrollbar.grid(row=0, column=1, sticky="ns")
    horizontal_scrollbar = ttk.Scrollbar(app._preview_table_container, orient=tk.HORIZONTAL, command=canvas.xview)
    horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
    canvas.configure(yscrollcommand=vertical_scrollbar.set, xscrollcommand=horizontal_scrollbar.set)

    grid_frame = tk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

    _build_preview_cell(grid_frame, 0, 0, "#", "#eef2f6", "#444444", bold=True, anchor="center")
    for column_index, column_name in enumerate(preview_frame.columns, start=1):
        role_name = get_column_role(resolved_roles, str(column_name))
        background, foreground = get_column_role_colors(role_name)
        header_text = f"{column_name}\n[{get_column_role_label(resolved_roles, str(column_name))}]"
        _build_preview_cell(grid_frame, 0, column_index, header_text, background, foreground, bold=True, anchor="w")

    formatted_frame = preview_frame.astype(object).where(pd.notna(preview_frame), "")
    for row_index, row_values in enumerate(formatted_frame.itertuples(index=False, name=None), start=1):
        _build_preview_cell(grid_frame, row_index, 0, str(row_index - 1), "#eef2f6", "#444444", anchor="e")
        for column_index, value in enumerate(row_values, start=1):
            column_name = str(preview_frame.columns[column_index - 1])
            role_name = get_column_role(resolved_roles, column_name)
            background, foreground = get_column_role_cell_colors(role_name)
            _build_preview_cell(
                grid_frame,
                row_index,
                column_index,
                format_display_value(value),
                background,
                foreground,
                anchor="w",
            )

    def _sync_scroll_region(_event: tk.Event | None = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _sync_window_size(event: tk.Event) -> None:
        canvas.itemconfigure(window_id, height=max(event.height, grid_frame.winfo_reqheight()))

    grid_frame.bind("<Configure>", _sync_scroll_region)
    canvas.bind("<Configure>", _sync_window_size)
    app._preview_table_container.rowconfigure(0, weight=1)
    app._preview_table_container.columnconfigure(0, weight=1)
    _sync_scroll_region()


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
