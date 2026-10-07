"""
plot_utils.py

Utility functions for building matplotlib plots from tabular data.
Provides helpers for creating subplots, plotting columns, hiding unused
subplots, and syncing axes.
"""

from collections.abc import Mapping, Sequence
from .plot_options import (
    CyclePlotData,
    DeviationPanelPlotData,
    DeviationPlotData,
    DeviationSeriesPlotData,
    FrequencySeriesPlotData,
    MagnitudePhasePlotData,
    PlotOptions,
    PlotStyle,
    ResidualSpectrumPlotData,
    SignalComparisonPlotData,
    SpectrogramPlotData,
)


import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd

from .display_format import apply_numeric_axis_format
from .plot_sampling import plot_adaptive_line


DataFrameMap = Mapping[str, pd.DataFrame]
DatasetLineStyles = Mapping[str, str] | None
XValueList = list[np.ndarray]


def calculate_subplot_grid(item_count: int) -> tuple[int, int]:
    """Return a balanced grid with at least as many columns as rows."""
    if item_count < 1:
        raise ValueError("item_count must be at least 1")
    column_count = int(np.ceil(np.sqrt(item_count)))
    return (item_count + column_count - 1) // column_count, column_count


def create_magnitude_phase_figure(
    plot_data: MagnitudePhasePlotData,
    *,
    style: PlotStyle | None = None,
    figsize: tuple[float, float] = (10.0, 4.6),
    dpi: int = 100,
    plt_module=plt,
) -> plt.Figure:
    """Render fully prepared magnitude and phase values without analysis calculations."""

    resolved_style = style or PlotStyle()
    palette = resolved_style.color_palette or PlotStyle().color_palette
    magnitude_color = palette[0] if palette else "#1f77b4"
    phase_color = palette[3 % len(palette)] if palette else "#d62728"
    figure, (magnitude_axis, phase_axis) = plt_module.subplots(
        *calculate_subplot_grid(2),
        figsize=figsize,
        dpi=dpi,
        sharex=True,
    )

    magnitude_axis.plot(
        plot_data.x_values,
        plot_data.magnitude_values,
        linewidth=resolved_style.line_width,
        color=magnitude_color,
    )
    apply_axis_contract(
        magnitude_axis,
        title=plot_data.magnitude_title,
        x_label=plot_data.x_label,
        y_label=plot_data.magnitude_label,
        style=resolved_style,
    )

    phase_axis.plot(
        plot_data.x_values,
        plot_data.phase_degrees,
        linewidth=resolved_style.line_width,
        color=phase_color,
    )
    apply_axis_contract(
        phase_axis,
        title=plot_data.phase_title,
        x_label=plot_data.x_label,
        y_label=plot_data.phase_label,
        style=resolved_style,
    )
    if plot_data.wrapped_phase:
        phase_axis.set_ylim(-200, 200)
        phase_axis.set_yticks([-180, -90, 0, 90, 180])
    for axis in (magnitude_axis, phase_axis):
        axis.margins(x=0.02)
        apply_numeric_axis_format(axis, format_x=True, format_y=axis is magnitude_axis)
    figure.tight_layout()
    return figure


def create_frequency_series_figure(
    plot_data: FrequencySeriesPlotData,
    *,
    style: PlotStyle | None = None,
    figsize: tuple[float, float] = (6.2, 3.2),
    dpi: int = 100,
    plt_module=plt,
) -> plt.Figure:
    """Render one prepared frequency-domain series using the shared style contract."""

    resolved_style = style or PlotStyle()
    figure, axis = plt_module.subplots(figsize=figsize, dpi=dpi)
    _draw_frequency_series_axis(axis, plot_data, resolved_style)
    figure.tight_layout()
    return figure


def create_deviation_figure(
    plot_data: DeviationPlotData,
    *,
    style: PlotStyle | None = None,
    plt_module=plt,
) -> plt.Figure:
    """Render prepared zero-referenced deviations using a shared panel layout."""

    if not plot_data.panels:
        raise ValueError("plot_data.panels must not be empty")
    resolved_style = style or PlotStyle()
    panel_count = len(plot_data.panels)
    row_count, column_count = calculate_subplot_grid(panel_count)
    figsize = (5.0 * column_count, 4.6 * row_count)
    figure, axes = plt_module.subplots(
        row_count,
        column_count,
        squeeze=False,
        figsize=figsize,
        dpi=100,
    )
    for panel_index, panel in enumerate(plot_data.panels):
        axis = axes[panel_index // column_count][panel_index % column_count]
        _draw_deviation_panel(axis, panel, resolved_style)
    for unused_index in range(panel_count, row_count * column_count):
        axes[unused_index // column_count][unused_index % column_count].set_visible(False)
    figure.suptitle(plot_data.figure_title)
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    return figure


def create_residual_spectrum_figure(
    plot_data: ResidualSpectrumPlotData,
    *,
    style: PlotStyle | None = None,
    plt_module=plt,
) -> plt.Figure:
    """Render prepared residual and spectrum panels without analysis calculations."""

    resolved_style = style or PlotStyle()
    figure, (deviation_axis, spectrum_axis) = plt_module.subplots(
        *calculate_subplot_grid(2),
        figsize=(10.0, 4.6),
        dpi=100,
        sharex=False,
    )
    _draw_deviation_panel(deviation_axis, plot_data.deviation, resolved_style)
    if plot_data.spectrum is None:
        spectrum_axis.text(
            0.5,
            0.5,
            plot_data.unavailable_spectrum_message,
            transform=spectrum_axis.transAxes,
            ha="center",
            va="center",
        )
        apply_axis_contract(
            spectrum_axis,
            title="Residual Spectrum",
            x_label="",
            y_label="",
            style=resolved_style,
        )
    else:
        _draw_frequency_series_axis(spectrum_axis, plot_data.spectrum, resolved_style)
    figure.tight_layout()
    return figure


def draw_deviation_series(
    axis,
    series: DeviationSeriesPlotData,
    *,
    style: PlotStyle,
    series_index: int = 0,
    fill_deviations: bool = False,
    add_fill_labels: bool = False,
    reference_label: str | None = None,
) -> None:
    """Draw one prepared deviation series and its optional sign fills/reference."""

    palette = style.color_palette or PlotStyle().color_palette
    color = palette[series_index % len(palette)]
    x_values = np.asarray(series.x_values, dtype=float)
    values = np.asarray(series.values, dtype=float)
    axis.plot(series.x_values, series.values, label=series.label, color=color, linewidth=style.line_width)
    if fill_deviations:
        positive_mask = values >= 0.0
        negative_mask = values < 0.0
        axis.fill_between(
            x_values,
            0.0,
            values,
            where=positive_mask,
            interpolate=True,
            color="#d62728",
            alpha=0.18,
            label="Above baseline" if add_fill_labels else "_nolegend_",
        )
        axis.fill_between(
            x_values,
            0.0,
            values,
            where=negative_mask,
            interpolate=True,
            color="#1f77b4",
            alpha=0.18,
            label="Below baseline" if add_fill_labels else "_nolegend_",
        )
    if reference_label is not None:
        axis.axhline(
            0.0,
            color="#111827",
            linewidth=1.0,
            linestyle="--",
            label=reference_label,
        )


def fill_signed_deviation(
    axis,
    x_values: Sequence[float],
    reference_values: Sequence[float],
    candidate_values: Sequence[float],
    *,
    add_labels: bool,
) -> None:
    """Fill positive and negative regions between two prepared signal series."""

    reference = np.asarray(reference_values, dtype=float)
    candidate = np.asarray(candidate_values, dtype=float)
    positive_mask = candidate >= reference
    negative_mask = candidate < reference
    axis.fill_between(
        x_values,
        reference,
        candidate,
        where=positive_mask,
        interpolate=True,
        color="#d62728",
        alpha=0.18,
        label="Above baseline" if add_labels else "_nolegend_",
    )
    axis.fill_between(
        x_values,
        reference,
        candidate,
        where=negative_mask,
        interpolate=True,
        color="#1f77b4",
        alpha=0.18,
        label="Below baseline" if add_labels else "_nolegend_",
    )


def _draw_deviation_panel(axis, plot_data: DeviationPanelPlotData, style: PlotStyle) -> None:
    if plot_data.unavailable_message is not None:
        axis.text(0.5, 0.5, plot_data.unavailable_message, ha="center", va="center", transform=axis.transAxes)
        axis.set_axis_off()
        return
    for series_index, series in enumerate(plot_data.series):
        draw_deviation_series(
            axis,
            series,
            style=style,
            series_index=series_index,
            fill_deviations=plot_data.fill_deviations,
            add_fill_labels=series_index == 0,
            reference_label=plot_data.reference_label if series_index == 0 else None,
        )
    if plot_data.reference_label is not None and not plot_data.series:
        axis.axhline(0.0, color="#111827", linewidth=1.0, linestyle="--", label=plot_data.reference_label)
    apply_axis_contract(
        axis,
        title=plot_data.title,
        x_label=plot_data.x_label,
        y_label=plot_data.y_label,
        style=style,
    )
    axis.margins(x=0.02)
    apply_numeric_axis_format(axis, format_x=True, format_y=True)


def _draw_frequency_series_axis(axis, plot_data: FrequencySeriesPlotData, style: PlotStyle) -> None:
    palette = style.color_palette or PlotStyle().color_palette
    axis.plot(
        plot_data.x_values,
        plot_data.y_values,
        linewidth=style.line_width,
        color=palette[0],
    )
    apply_axis_contract(
        axis,
        title=plot_data.title,
        x_label=plot_data.x_label,
        y_label=plot_data.y_label,
        style=style,
    )
    if plot_data.y_limits is not None:
        axis.set_ylim(*plot_data.y_limits)
    if plot_data.coherence_segment_count is not None:
        _draw_coherence_guidance(axis, plot_data.coherence_segment_count)
    axis.margins(x=0.02)
    apply_numeric_axis_format(axis, format_x=True, format_y=True)


def _draw_coherence_guidance(axis, segment_count: int) -> None:
    axis.axhspan(0.0, 0.2, color="#991b1b", alpha=0.06, linewidth=0)
    axis.axhspan(0.2, 0.5, color="#92400e", alpha=0.05, linewidth=0)
    axis.axhspan(0.5, 0.8, color="#065f46", alpha=0.04, linewidth=0)
    axis.axhspan(0.8, 1.0, color="#14532d", alpha=0.06, linewidth=0)
    for marker in (0.2, 0.5, 0.8):
        axis.axhline(marker, color="#334155", linestyle="--", linewidth=0.7, alpha=0.45)
    axis.text(0.99, 0.06, "weak", transform=axis.transAxes, ha="right", va="bottom", fontsize=7, color="#991b1b")
    axis.text(0.99, 0.36, "moderate", transform=axis.transAxes, ha="right", va="center", fontsize=7, color="#92400e")
    axis.text(0.99, 0.67, "strong", transform=axis.transAxes, ha="right", va="center", fontsize=7, color="#166534")
    axis.text(0.99, 0.94, "very strong", transform=axis.transAxes, ha="right", va="top", fontsize=7, color="#14532d")

    if segment_count < 4:
        adequacy_text = f"Low confidence: only {segment_count} Welch segments"
        adequacy_color = "#991b1b"
    elif segment_count < 8:
        adequacy_text = f"Moderate confidence: {segment_count} Welch segments"
        adequacy_color = "#92400e"
    else:
        adequacy_text = f"Good confidence: {segment_count} Welch segments"
        adequacy_color = "#166534"
    axis.text(
        0.01,
        0.98,
        adequacy_text,
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color=adequacy_color,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": adequacy_color, "alpha": 0.75},
    )


def create_spectrogram_figure(
    plot_data: SpectrogramPlotData,
    *,
    style: PlotStyle | None = None,
    plt_module=plt,
) -> plt.Figure:
    """Draw a spectrogram from display-ready dB values."""

    resolved_style = style or PlotStyle()
    figure, axis = plt_module.subplots(figsize=(6.2, 3.8), dpi=100)
    mesh = axis.pcolormesh(
        plot_data.times,
        plot_data.frequencies,
        plot_data.power_db,
        shading="auto",
        cmap="viridis",
    )
    figure.colorbar(mesh, ax=axis, label=plot_data.colorbar_label)
    apply_axis_contract(
        axis,
        title=plot_data.title,
        x_label=plot_data.x_label,
        y_label=plot_data.y_label,
        style=resolved_style,
    )
    apply_numeric_axis_format(axis, format_x=True, format_y=True)
    figure.tight_layout()
    return figure


def create_signal_comparison_figure(
    plot_data: SignalComparisonPlotData,
    *,
    style: PlotStyle | None = None,
    plt_module=plt,
) -> plt.Figure:
    """Draw two prepared signals using the shared presentation contract."""

    resolved_style = style or PlotStyle()
    figure, axis = plt_module.subplots(figsize=(6.2, 3.8), dpi=100)
    colors = resolved_style.color_palette or ["#1f77b4", "#ff7f0e"]
    plot_adaptive_line(
        axis,
        plot_data.x_values,
        plot_data.original_values,
        linewidth=resolved_style.line_width,
        color=colors[0],
        linestyle="--",
        alpha=0.9,
        label=plot_data.original_label,
    )
    plot_adaptive_line(
        axis,
        plot_data.x_values,
        plot_data.comparison_values,
        linewidth=resolved_style.line_width,
        color=colors[1 % len(colors)],
        alpha=0.95,
        label=plot_data.comparison_label,
    )
    apply_axis_contract(
        axis,
        title=plot_data.title,
        x_label=plot_data.x_label,
        y_label=plot_data.y_label,
        style=resolved_style,
    )
    axis.margins(x=0.02)
    apply_numeric_axis_format(axis, format_x=True, format_y=True)
    figure.tight_layout()
    return figure


def create_cycle_figure(
    plot_data: CyclePlotData,
    *,
    enabled_metrics: Sequence[str] = ("mean", "rms", "peak_to_peak", "min", "max"),
    style: PlotStyle | None = None,
    plt_module=plt,
) -> plt.Figure:
    """Draw prepared cycle traces, representative values, and C2C metrics."""

    resolved_style = style or PlotStyle()
    figure, (cycle_axis, representative_axis, metrics_axis) = plt_module.subplots(
        3, 1, figsize=(6.2, 6.2), dpi=100, sharex=False
    )

    for cycle_values in plot_data.selected_cycles:
        cycle_axis.plot(plot_data.step_values, cycle_values, color="#94a3b8", alpha=0.5, linewidth=1.0)
    apply_axis_contract(
        cycle_axis,
        title="Selected Individual Cycles",
        x_label="Sample within cycle",
        y_label=plot_data.source_label,
        style=resolved_style,
    )
    if len(plot_data.step_values) > 0:
        cycle_axis.set_xlim(0, len(plot_data.step_values) - 1)
    apply_numeric_axis_format(cycle_axis, format_x=True, format_y=True)

    mean_values = np.asarray(plot_data.mean_values)
    std_values = np.asarray(plot_data.std_values)
    representative_axis.fill_between(
        plot_data.step_values,
        mean_values - std_values,
        mean_values + std_values,
        color="#14b8a6",
        alpha=0.18,
    )
    representative_axis.plot(plot_data.step_values, mean_values, color="#0f766e", linewidth=2.0, label="mean")
    if plot_data.early_mean_values is not None:
        representative_axis.plot(
            plot_data.step_values, plot_data.early_mean_values, color="#2563eb", linewidth=1.2, linestyle="--", label="early mean"
        )
    if plot_data.late_mean_values is not None:
        representative_axis.plot(
            plot_data.step_values, plot_data.late_mean_values, color="#dc2626", linewidth=1.2, linestyle="--", label="late mean"
        )
    support_axis = None
    if plot_data.support_values is not None:
        support_axis = representative_axis.twinx()
        support_axis.plot(
            plot_data.step_values, plot_data.support_values, color="#475569", linewidth=1.1, linestyle=":", label="support"
        )
        support_axis.set_ylabel("Support [cycles]", fontsize=resolved_style.label_fontsize, color="#475569")
        support_axis.tick_params(axis="y", colors="#475569")
        apply_numeric_axis_format(support_axis, format_x=False, format_y=True)
    apply_axis_contract(
        representative_axis,
        title="Representative Cycle (mean +- std)",
        x_label="Sample within cycle",
        y_label=plot_data.source_label,
        style=resolved_style,
    )
    if len(plot_data.step_values) > 0:
        representative_axis.set_xlim(0, len(plot_data.step_values) - 1)
    apply_numeric_axis_format(representative_axis, format_x=True, format_y=True)
    handles, labels = representative_axis.get_legend_handles_labels()
    if support_axis is not None:
        support_handles, support_labels = support_axis.get_legend_handles_labels()
        handles += support_handles
        labels += support_labels
    if handles and resolved_style.show_legend:
        representative_axis.legend(handles, labels, fontsize=resolved_style.legend_fontsize, loc="best")

    metric_specs = {
        "mean": ("mean", 1.4, None),
        "rms": ("rms", 1.4, None),
        "peak_to_peak": ("p2p", 1.2, None),
        "min": ("min", 1.1, "#2563eb"),
        "max": ("max", 1.1, "#dc2626"),
    }
    for metric_key in enabled_metrics:
        if metric_key not in plot_data.metric_values:
            continue
        label, linewidth, color = metric_specs[metric_key]
        plot_kwargs = {"label": label, "linewidth": linewidth}
        if color is not None:
            plot_kwargs["color"] = color
        metrics_axis.plot(plot_data.cycle_numbers, plot_data.metric_values[metric_key], **plot_kwargs)
    length_axis = metrics_axis.twinx()
    length_axis.plot(
        plot_data.cycle_numbers,
        plot_data.length_values,
        label=plot_data.length_legend,
        linewidth=1.4,
        color="#b45309",
        linestyle="--",
    )
    apply_axis_contract(metrics_axis, title="Cycle-to-Cycle Statistics", x_label="Cycle", y_label="Metric", style=resolved_style)
    length_axis.set_ylabel(plot_data.length_label, fontsize=resolved_style.label_fontsize, color="#b45309", labelpad=12)
    length_axis.tick_params(axis="y", colors="#b45309")
    left_handles, left_labels = metrics_axis.get_legend_handles_labels()
    right_handles, right_labels = length_axis.get_legend_handles_labels()
    if resolved_style.show_legend:
        metrics_axis.legend(left_handles + right_handles, left_labels + right_labels, fontsize=resolved_style.legend_fontsize, loc="best")
    apply_numeric_axis_format(metrics_axis, format_x=True, format_y=True)
    apply_numeric_axis_format(length_axis, format_x=False, format_y=True)
    figure.tight_layout()
    return figure


def create_plot_figure(
    plot_options: PlotOptions,
    selected_file_paths: Sequence[str],
    data_frames: DataFrameMap,
    dataset_line_styles: DatasetLineStyles = None,
    plt_module=plt,
) -> plt.Figure:
    """
    Build a matplotlib figure for the selected files and columns.
    Args:
        plot_options: PlotOptions dataclass with plot configuration.
        selected_file_paths: List of selected file paths.
        data_frames: Dictionary mapping file paths to pandas DataFrames.
        dataset_line_styles: Optional mapping of dataset paths to Matplotlib line styles.
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
        fig, axes, _, _ = create_subplots(
            n,
            ncols=max(1, plot_options.subplot_columns),
            style=plot_options.style,
            plt_module=plt_module,
        )
        x_values_by_axis = plot_columns_on_axes(
            axes,
            plot_options.cols_to_plot,
            selected_file_paths,
            data_frames,
            plot_options.xcol,
            y_label=plot_options.y_label,
            style=plot_options.style,
            dataset_line_styles=dataset_line_styles,
        )
        hide_unused_subplots(axes, n)
        sync_x_axes(axes, x_values_by_axis, fig)
        return fig

    return create_overlay_figure(
        selected_file_paths,
        data_frames,
        plot_options.cols_to_plot,
        plot_options.xcol,
        title=plot_options.title or "Overlay Plot",
        y_label=plot_options.y_label,
        style=plot_options.style,
        dataset_line_styles=dataset_line_styles,
        plt_module=plt_module,
    )


def create_overlay_figure(
    selected_file_paths: Sequence[str],
    data_frames: DataFrameMap,
    cols_to_plot: list[str],
    xcol: str,
    title: str = "Overlay Plot",
    y_label: str = "Value",
    style: PlotStyle | None = None,
    dataset_line_styles: DatasetLineStyles = None,
    plt_module=plt,
) -> plt.Figure:
    """Build a single-axis overlay plot for the selected files and columns."""

    resolved_style = style or PlotStyle()
    fig, ax = plt_module.subplots(figsize=(10, 6))
    x_values_by_axis: XValueList = []
    x_label = "Index" if xcol == "Index" else xcol
    series_index = 0

    for col_name in cols_to_plot:
        for path in selected_file_paths:
            df = data_frames[path]
            if df.empty or col_name not in df.columns:
                continue

            x_vals, x_label = resolve_x_values(df, xcol)
            x_arr = np.asarray(x_vals)
            if x_arr.size > 0:
                x_values_by_axis.append(x_arr)

            plot_adaptive_line(
                ax,
                x_vals,
                df[col_name],
                label=_build_overlay_label(path, col_name, selected_file_paths, cols_to_plot),
                color=_resolve_plot_color(
                    style=resolved_style,
                    series_index=series_index,
                ),
                marker=resolved_style.marker,
                markersize=resolved_style.marker_size,
                linewidth=resolved_style.line_width,
                linestyle=(dataset_line_styles or {}).get(path, "-"),
            )
            series_index += 1

    _apply_axis_contract(
        ax,
        title=title,
        x_label=x_label,
        y_label=y_label,
        style=resolved_style,
    )
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



def create_subplots(
    n: int,
    ncols: int = 2,
    style: PlotStyle | None = None,
    plt_module=plt,
) -> tuple[plt.Figure, object, int, int]:
    """
    Create a grid of matplotlib subplots.
    Args:
        n: Number of subplots.
        ncols: Legacy column preference; balanced grid sizing takes precedence.
    Returns:
        Tuple of (Figure, Axes array, nrows, ncols)
    """
    nrows, ncols = calculate_subplot_grid(n)
    _ = style  # Reserved for future style-driven figure sizing.
    fig, axes = plt_module.subplots(nrows=nrows, ncols=ncols, figsize=(5.0 * ncols, 4.6 * nrows), squeeze=False)
    return fig, axes, nrows, ncols


def plot_columns_on_axes(
    axes: object,
    cols_to_plot: list[str],
    selected_file_paths: Sequence[str],
    data_frames: DataFrameMap,
    xcol: str,
    y_label: str = "Value",
    style: PlotStyle | None = None,
    dataset_line_styles: DatasetLineStyles = None,
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
    resolved_style = style or PlotStyle()
    ncols = axes.shape[1]
    series_index = 0
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
            plot_adaptive_line(
                ax,
                x_vals,
                df[col_name],
                label=os.path.basename(path),
                color=_resolve_plot_color(
                    style=resolved_style,
                    series_index=series_index,
                ),
                marker=resolved_style.marker,
                markersize=resolved_style.marker_size,
                linewidth=resolved_style.line_width,
                linestyle=(dataset_line_styles or {}).get(path, "-"),
            )
            series_index += 1
        _apply_axis_contract(
            ax,
            title=col_name,
            x_label=x_label,
            y_label=y_label,
            style=resolved_style,
        )
        apply_numeric_axis_format(ax, format_x=True, format_y=True)
    return x_values_by_axis


def apply_axis_contract(
    axis: object,
    title: str,
    x_label: str,
    y_label: str,
    style: PlotStyle,
) -> None:
    """Apply shared axis presentation defaults to reduce drift across plot families."""

    axis.set_title(title, fontsize=style.title_fontsize, fontfamily=style.font_family)
    axis.set_xlabel(x_label, fontsize=style.label_fontsize, fontfamily=style.font_family)
    axis.set_ylabel(y_label, fontsize=style.label_fontsize, fontfamily=style.font_family)
    axis.tick_params(axis="both", labelsize=style.tick_fontsize)
    for item in axis.get_xticklabels() + axis.get_yticklabels():
        item.set_fontfamily(style.font_family)
    if style.show_legend and axis.lines:
        handles, labels = axis.get_legend_handles_labels()
        has_public_labels = any(label and not label.startswith("_") for label in labels)
        if handles and has_public_labels:
            axis.legend(fontsize=style.legend_fontsize, loc=style.legend_location)
    if style.show_grid:
        axis.grid(
            True,
            which="major",
            alpha=style.grid_alpha,
            linestyle=style.grid_line_style,
            linewidth=style.grid_line_width,
            color=style.grid_color,
        )
    else:
        axis.grid(False, which="major")
    if style.show_subgrid:
        axis.minorticks_on()
        axis.grid(
            True,
            which="minor",
            alpha=style.subgrid_alpha,
            linestyle=style.subgrid_line_style,
            linewidth=style.subgrid_line_width,
            color=style.subgrid_color,
        )
    else:
        axis.grid(False, which="minor")


def _apply_axis_contract(
    axis: object,
    title: str,
    x_label: str,
    y_label: str,
    style: PlotStyle,
) -> None:
    """Compatibility wrapper around apply_axis_contract for local call sites."""

    apply_axis_contract(axis, title=title, x_label=x_label, y_label=y_label, style=style)


def _resolve_plot_color(
    *,
    style: PlotStyle,
    series_index: int,
) -> str:
    """Resolve a line color from the configured palette."""

    palette = style.color_palette or PlotStyle().color_palette
    if not palette:
        return "#1f77b4"
    return palette[series_index % len(palette)]


def normalize_x_values(series: pd.Series) -> pd.Series:
    """Convert x-axis values to numeric or datetime when the whole series supports it."""

    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
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
        axes[row][col].set_visible(False)


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
        bounds = []
        for values in non_empty_arrays:
            finite_values = values[np.isfinite(values)]
            if finite_values.size:
                bounds.append((float(finite_values.min()), float(finite_values.max())))
        if not bounds:
            return None
        return min(low for low, _ in bounds), max(high for _, high in bounds)

    if all(np.issubdtype(values.dtype, np.datetime64) for values in non_empty_arrays):
        bounds = []
        for values in non_empty_arrays:
            valid_values = values[~np.isnat(values)].astype("datetime64[ns]")
            if valid_values.size:
                bounds.append((valid_values.min(), valid_values.max()))
        if not bounds:
            return None
        return min(low for low, _ in bounds), max(high for _, high in bounds)

    return None
