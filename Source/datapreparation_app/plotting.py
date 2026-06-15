"""Plot dialog and figure window helpers for the main application."""


import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import SpanSelector
import pandas as pd
import tkinter as tk
from tkinter import ttk

from Source.shared.plot_options import PlotOptions, PlotStyle
from Source.shared.plot_utils import create_plot_figure

from .datasets import get_column_role, sort_columns_by_role

class PlotOptionsDialog:
    """Modal dialog for choosing plot columns and axis options."""

    def __init__(self, parent: tk.Tk, df: pd.DataFrame, window_title: str, default_style: PlotStyle | None = None) -> None:
        self.parent = parent
        self.df = df
        self.window_title = window_title
        self.default_style = default_style or PlotStyle()
        self.result: PlotOptions | None = None

    def show(self) -> PlotOptions | None:
        cols = list(self.df.columns)
        if not cols:
            return None

        default_xcol = self._detect_default_xcol(cols)
        dialog = tk.Toplevel(self.parent)
        dialog.title(self.window_title + " Options")
        dialog.grab_set()
        dialog.resizable(True, True)

        row = 0
        tk.Label(dialog, text="Select columns to plot:").grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))
        row += 1

        cols_listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=0, height=min(8, len(cols)))
        for col in cols:
            cols_listbox.insert(tk.END, col)
        cols_listbox.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0, 2))
        row += 1

        tk.Label(dialog, text="Select x-axis column:").grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 0))
        row += 1

        xcol_var = tk.StringVar(value=default_xcol)
        ttk.Combobox(dialog, textvariable=xcol_var, values=["Index"] + cols, state="readonly").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
            pady=(0, 2),
        )
        row += 1

        use_subplots_var = tk.BooleanVar(value=True)
        tk.Checkbutton(dialog, text="Subplots", variable=use_subplots_var).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 0)
        )
        row += 1

        def on_ok() -> None:
            selected_indices = cols_listbox.curselection()
            ycols = cols.copy() if not selected_indices else [cols[index] for index in selected_indices]
            xcol = xcol_var.get() if xcol_var.get() in cols or xcol_var.get() == "Index" else default_xcol
            if xcol != "Index":
                ycols = [col for col in ycols if col != xcol]
            if not ycols:
                ycols = [col for col in cols if col != xcol]
            self.result = PlotOptions(
                cols_to_plot=ycols,
                xcol=xcol,
                use_subplots=use_subplots_var.get(),
                style=self.default_style,
            )
            dialog.destroy()

        def on_cancel() -> None:
            self.result = None
            dialog.destroy()

        tk.Button(dialog, text="OK", command=on_ok).grid(row=row, column=0, padx=10, pady=8, sticky="e")
        tk.Button(dialog, text="Cancel", command=on_cancel).grid(row=row, column=1, padx=10, pady=8, sticky="w")

        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(1, weight=1)
        dialog.wait_window()
        return self.result

    def _detect_default_xcol(self, cols: list[str]) -> str:
        for col in cols:
            if pd.api.types.is_datetime64_any_dtype(self.df[col]) or any(
                token in col.lower() for token in ["time", "date", "timestamp"]
            ):
                return col
        return "Index"


def show_figure_in_window(root: tk.Tk, figure: plt.Figure, window_title: str, window_geometry: str) -> None:
    """Show a matplotlib figure in a separate Tk window."""

    window = tk.Toplevel(root)
    window.title(window_title)
    window.geometry(window_geometry)
    container = ttk.Frame(window)
    container.pack(fill=tk.BOTH, expand=True)
    canvas = FigureCanvasTkAgg(figure, master=container)
    canvas.draw()
    toolbar = NavigationToolbar2Tk(canvas, container)
    toolbar.update()
    toolbar.pack(side=tk.TOP, fill=tk.X)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)

    resize_job: str | None = None

    def _sync_canvas_size() -> None:
        widget = canvas.get_tk_widget()
        widget.update_idletasks()
        width = max(widget.winfo_width(), 1)
        height = max(widget.winfo_height(), 1)
        dpi = float(figure.get_dpi() or 100.0)
        figure.set_size_inches(width / dpi, height / dpi, forward=True)
        canvas.draw_idle()

    def _on_configure(event: tk.Event) -> None:
        nonlocal resize_job
        if event.widget is not container:
            return
        if resize_job is not None:
            window.after_cancel(resize_job)
        resize_job = window.after(150, _sync_canvas_size)

    container.bind("<Configure>", _on_configure)
    window.after_idle(_sync_canvas_size)

    def _on_close() -> None:
        plt.close(figure)
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", _on_close)


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

    time_col = _get_time_role_column(resolved_roles)
    xcol = time_col if time_col is not None and time_col in dataframe.columns else "Index"

    plot_options = PlotOptions(
        cols_to_plot=preview_columns,
        xcol=xcol,
        use_subplots=False,
        title="Overlay Plot",
        y_label="Value",
        style=app.style_vars.to_plot_style() if hasattr(app, "style_vars") else PlotStyle(),
    )

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


def _get_preserved_preview_plot_columns(app, available_columns: list[str]) -> list[str]:
    if not hasattr(app, "_get_selected_preview_plot_columns_from_selector"):
        return available_columns

    selected_columns = app._get_selected_preview_plot_columns_from_selector()
    preserved_columns = [column for column in selected_columns if column in available_columns]
    return preserved_columns or available_columns


def _get_selected_dataset_roles(app, selected_path: str) -> dict[str, str]:
    context = app.dataset_contexts.get(selected_path)
    return dict(context.column_roles) if context is not None else {}


def _get_time_role_column(column_roles: dict[str, str]) -> str | None:
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
    app._row_range_span_selector = span
