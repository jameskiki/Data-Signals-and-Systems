

"""
plot_utils.py

Utility functions for building matplotlib plots from tabular data.
Provides helpers for creating subplots, plotting columns, hiding unused
subplots, and syncing axes.
"""

from collections.abc import Mapping, Sequence
from .plot_options import PlotOptions


import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd

from .column_roles import get_column_role, get_column_role_plot_color
from .display_format import apply_numeric_axis_format


DataFrameMap = Mapping[str, pd.DataFrame]
XValueList = list[np.ndarray]


def create_plot_figure(
    plot_options: PlotOptions,
    selected_file_paths: Sequence[str],
    data_frames: DataFrameMap,
    column_roles: dict[str, str] | None = None,
    plt_module=plt,
) -> plt.Figure:
    """
    Build a matplotlib figure for the selected files and columns.
    Args:
        plot_options: PlotOptions dataclass with plot configuration.
        selected_file_paths: List of selected file paths.
        data_frames: Dictionary mapping file paths to pandas DataFrames.
        column_roles: Optional dict of column roles.
        plt_module: Matplotlib pyplot module (default: plt).
    Returns:
        Matplotlib Figure.
    """
    if not selected_file_paths:
        raise ValueError("selected_file_paths must not be empty")
    if not plot_options.cols_to_plot:
        raise ValueError("cols_to_plot must not be empty")
    missing_paths = [path for path in selected_file_paths if path not in data_frames]
    if missing_paths:
        raise KeyError(f"Missing data for selected paths: {missing_paths}")

    if plot_options.use_subplots:
        n = len(plot_options.cols_to_plot)
        fig, axes, _, _ = create_subplots(n, ncols=2, plt_module=plt_module)
        x_values_by_axis = plot_columns_on_axes(
            axes, plot_options.cols_to_plot, selected_file_paths, data_frames, plot_options.xcol, column_roles=column_roles
        )
        hide_unused_subplots(axes, n)
        sync_x_axes(axes, x_values_by_axis, fig)
        return fig

    return create_overlay_figure(
        selected_file_paths,
        data_frames,
        plot_options.cols_to_plot,
        plot_options.xcol,
        column_roles=column_roles,
        plt_module=plt_module,
    )


def create_overlay_figure(
    selected_file_paths: Sequence[str],
    data_frames: DataFrameMap,
    cols_to_plot: list[str],
    xcol: str,
    column_roles: dict[str, str] | None = None,
    plt_module=plt,
) -> plt.Figure:
    """Build a single-axis overlay plot for the selected files and columns."""

    fig, ax = plt_module.subplots(figsize=(10, 6))
    x_values_by_axis: XValueList = []
    x_label = "Index" if xcol == "Index" else xcol

    for col_name in cols_to_plot:
        for path in selected_file_paths:
            df = data_frames[path]
            if df.empty or col_name not in df.columns:
                continue

            x_vals, x_label = resolve_x_values(df, xcol)
            x_arr = np.asarray(x_vals)
            if x_arr.size > 0:
                x_values_by_axis.append(x_arr)

            ax.plot(
                x_vals,
                df[col_name],
                label=_build_overlay_label(path, col_name, selected_file_paths, cols_to_plot),
                color=get_column_role_plot_color(get_column_role(column_roles or {}, col_name)),
                marker='o',
                markersize=2,
                linewidth=2,
            )

    ax.set_title("Overlay Plot", fontsize=10)
    ax.set_xlabel(x_label, fontsize=9)
    ax.set_ylabel("Value", fontsize=9)
    if ax.lines:
        ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    apply_numeric_axis_format(ax, format_x=True, format_y=True)

    x_limits = compute_shared_xlim(x_values_by_axis)
    if x_limits is not None:
        ax.set_xlim(*x_limits)

    fig.tight_layout()
    return fig


def _build_overlay_label(
    path: str,
    col_name: str,
    selected_file_paths: Sequence[str],
    cols_to_plot: Sequence[str],
) -> str:
    """Return a concise legend label for overlay plots."""

    if len(selected_file_paths) == 1:
        return col_name
    if len(cols_to_plot) == 1:
        return os.path.basename(path)
    return f"{os.path.basename(path)} - {col_name}"



def create_subplots(n: int, ncols: int = 2, plt_module=plt) -> tuple[plt.Figure, object, int, int]:
    """
    Create a grid of matplotlib subplots.
    Args:
        n: Number of subplots.
        ncols: Number of columns.
    Returns:
        Tuple of (Figure, Axes array, nrows, ncols)
    """
    ncols = min(ncols, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt_module.subplots(nrows=nrows, ncols=ncols, figsize=(8 * ncols, 4 * nrows), squeeze=False)
    return fig, axes, nrows, ncols


def plot_columns_on_axes(
    axes: object,
    cols_to_plot: list[str],
    selected_file_paths: Sequence[str],
    data_frames: DataFrameMap,
    xcol: str,
    column_roles: dict[str, str] | None = None,
) -> XValueList:
    """
    Plot selected columns from dataframes onto axes.
    Args:
        axes: Matplotlib Axes array.
        cols_to_plot: List of column names to plot.
        selected_file_paths: List of selected file paths.
        data_frames: Dict mapping file paths to DataFrames.
        xcol: Name of x-axis column.
    Returns:
        List of all x-values arrays for axis syncing.
    """
    x_values_by_axis: XValueList = []
    ncols = axes.shape[1]
    for idx, col_name in enumerate(cols_to_plot):
        row = idx // ncols
        col = idx % ncols
        ax = axes[row][col]
        x_label = "Index" if xcol == "Index" else xcol
        for path in selected_file_paths:
            df = data_frames[path]
            if df.empty or col_name not in df.columns:
                continue
            x_vals, x_label = resolve_x_values(df, xcol)
            x_arr = np.asarray(x_vals)
            if x_arr.size > 0:
                x_values_by_axis.append(x_arr)
            ax.plot(
                x_vals,
                df[col_name],
                label=os.path.basename(path),
                color=get_column_role_plot_color(get_column_role(column_roles or {}, col_name)),
                marker='o',
                markersize=2,
                linewidth=2,
            )
        ax.set_title(col_name, fontsize=10)
        ax.set_xlabel(x_label, fontsize=9)
        ax.set_ylabel("Value", fontsize=9)
        if ax.lines:
            ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, alpha=0.3)
        apply_numeric_axis_format(ax, format_x=True, format_y=True)
    return x_values_by_axis


def normalize_x_values(series: pd.Series) -> pd.Series:
    """Convert x-axis values to numeric or datetime when the whole series supports it."""

    if np.issubdtype(series.dtype, np.number) or np.issubdtype(series.dtype, np.datetime64):
        return series

    numeric_values = pd.to_numeric(series, errors="coerce")
    if numeric_values.notna().all():
        return numeric_values

    datetime_values = pd.to_datetime(series, errors="coerce")
    if datetime_values.notna().all():
        return datetime_values

    return series.astype(str)


def resolve_x_values(dataframe: pd.DataFrame, xcol: str) -> tuple[pd.Index | pd.Series, str]:
    """Return x-axis values and label for a dataframe and requested x column."""

    if xcol == "Index" or xcol not in dataframe.columns:
        return dataframe.index, "Index"
    return normalize_x_values(dataframe[xcol]), xcol


def hide_unused_subplots(axes: object, n: int) -> None:
    """
    Hide unused subplots in a grid of axes.
    Args:
        axes: Matplotlib Axes array.
        n: Number of used subplots.
    """
    nrows, ncols = axes.shape
    for idx in range(n, nrows * ncols):
        row = idx // ncols
        col = idx % ncols
        axes[row][col].axis('off')


def sync_x_axes(axes: object, x_values_by_axis: XValueList, fig: plt.Figure) -> None:
    """
    Synchronize x-axis limits across all subplots.
    Args:
        axes: Matplotlib Axes array.
        x_values_by_axis: List of all x-values arrays.
        fig: Matplotlib Figure object.
    """
    x_limits = compute_shared_xlim(x_values_by_axis)
    if x_limits is not None:
        xmin, xmax = x_limits
        for ax in axes.flat:
            ax.set_xlim(xmin, xmax)
        sync_lock = {'locked': False}

        def make_sync_callback():
            def _on_xlim_changed(event_ax: object) -> None:
                if sync_lock['locked']:
                    return
                sync_lock['locked'] = True
                try:
                    new_xlim = event_ax.get_xlim()
                    for other_ax in axes.flat:
                        if other_ax is not event_ax:
                            other_ax.set_xlim(new_xlim)
                finally:
                    sync_lock['locked'] = False
                fig.canvas.draw_idle()

            return _on_xlim_changed

        for ax in axes.flat:
            ax.callbacks.connect('xlim_changed', make_sync_callback())
    fig.tight_layout()


def compute_shared_xlim(x_values_by_axis: XValueList) -> tuple[object, object] | None:
    """Compute shared x-axis bounds when all plotted x values share a compatible dtype."""

    if not x_values_by_axis:
        return None

    non_empty_arrays = [np.asarray(values) for values in x_values_by_axis if np.asarray(values).size > 0]
    if not non_empty_arrays:
        return None

    if all(np.issubdtype(values.dtype, np.number) for values in non_empty_arrays):
        combined = np.concatenate([values.astype(float, copy=False) for values in non_empty_arrays])
        finite_values = combined[np.isfinite(combined)]
        if finite_values.size == 0:
            return None
        return float(finite_values.min()), float(finite_values.max())

    if all(np.issubdtype(values.dtype, np.datetime64) for values in non_empty_arrays):
        combined = np.concatenate([values.astype("datetime64[ns]") for values in non_empty_arrays])
        valid_values = combined[~np.isnat(combined)]
        if valid_values.size == 0:
            return None
        return valid_values.min(), valid_values.max()

    return None
