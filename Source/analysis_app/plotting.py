"""Plot orchestration helpers for AnalysisWorkspace.

This module keeps analysis-specific plotting behavior in one place while
reusing shared plotting contracts from Source.shared.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import ttk

from Source.data_ops.cycles import CycleAnalysisResult
from Source.data_ops.spectral import FrequencySpectrumResult, SpectrogramResult
from Source.shared.column_roles import get_preferred_role_column
from Source.shared.display_format import apply_numeric_axis_format
from Source.shared.demo_catalog import get_demo_frequency_guides
from Source.shared.plot_options import (
    FrequencyPlotValues,
    FrequencySeriesPlotData,
    MagnitudePhasePlotData,
    PlotDescriptor,
    PlotOptions,
    PlotStyle,
    ResidualSpectrumPlotData,
    SignalComparisonPlotData,
    SpectrogramPlotData,
)
from Source.shared.plot_preparation import prepare_cycle_plot_data
from Source.shared.plot_utils import (
    create_cycle_figure,
    create_frequency_series_figure,
    create_magnitude_phase_figure,
    create_plot_figure,
    create_residual_spectrum_figure,
    create_signal_comparison_figure,
    create_spectrogram_figure,
)

from .state import PlotStyleVars
from .views import render_cycle_metrics_tree, render_fft_peaks_tree


@dataclass(frozen=True)
class FrequencyDisplayLabels:
    plot_title: str
    y_axis_label: str
    value_column_label: str


def get_frequency_display_labels(result: FrequencySpectrumResult) -> FrequencyDisplayLabels:
    if result.analysis_name == "FFT Amplitude":
        return FrequencyDisplayLabels(
            plot_title=f"FFT of {result.source_column}",
            y_axis_label="Amplitude",
            value_column_label="Amp",
        )
    if result.analysis_name == "Welch PSD":
        return FrequencyDisplayLabels(
            plot_title=f"Welch PSD of {result.source_column}",
            y_axis_label="PSD",
            value_column_label="PSD",
        )
    if result.analysis_name == "Transfer Estimate":
        comparison_column = result.comparison_column or "-"
        return FrequencyDisplayLabels(
            plot_title=f"Transfer Estimate: {comparison_column} -> {result.source_column}",
            y_axis_label="|H(f)| [dB]",
            value_column_label="|H| [dB]",
        )
    if result.analysis_name == "Coherence":
        comparison_column = result.comparison_column or "-"
        return FrequencyDisplayLabels(
            plot_title=f"Coherence: {comparison_column} -> {result.source_column}",
            y_axis_label="Coherence",
            value_column_label="Coh",
        )
    return FrequencyDisplayLabels(
        plot_title=result.analysis_name,
        y_axis_label="Value",
        value_column_label="Value",
    )


def refresh_live_plot(workspace) -> None:
    if not workspace.session.selected_y_columns:
        clear_plot_container(workspace)
        return

    style = get_default_plot_style(workspace.style_vars)
    plot_options = build_time_series_plot_options(
        selected_columns=workspace.session.selected_y_columns,
        x_column=workspace.session.selected_x_column,
        use_subplots=workspace.session.use_subplots,
        style=style,
    )
    figure = create_plot_figure(
        plot_options,
        [workspace.session.source_path],
        {workspace.session.source_path: workspace.session.working_frame},
    )
    variant = "Subplots" if workspace.session.use_subplots else "Overlay"
    render_plot_figure(workspace, figure, PlotDescriptor("Time series", variant))


def update_plot(workspace) -> None:
    selected_columns = workspace._get_selected_plot_y_columns()
    if not selected_columns:
        workspace.notifications.warning("Select at least one Y column")
        return

    x_column = workspace.plot_x_var.get().strip() or "Index"
    workspace.session.selected_x_column = x_column
    workspace.session.selected_y_columns = selected_columns
    workspace.session.use_subplots = workspace.plot_subplots_var.get()

    style = get_default_plot_style(workspace.style_vars)
    plot_options = build_time_series_plot_options(
        selected_columns=selected_columns,
        x_column=x_column,
        use_subplots=workspace.session.use_subplots,
        style=style,
    )
    figure = create_plot_figure(
        plot_options,
        [workspace.session.source_path],
        {workspace.session.source_path: workspace.session.working_frame},
    )
    variant = "Subplots" if workspace.session.use_subplots else "Overlay"
    render_plot_figure(workspace, figure, PlotDescriptor("Time series", variant))


def build_time_series_plot_options(
    selected_columns: list[str],
    x_column: str,
    use_subplots: bool,
    style: PlotStyle | None = None,
) -> PlotOptions:
    return PlotOptions(
        cols_to_plot=selected_columns,
        xcol=x_column,
        use_subplots=use_subplots,
        y_label="Value",
        style=style if style is not None else PlotStyle(),
    )


def get_default_plot_style(style_vars: PlotStyleVars | None = None) -> PlotStyle:
    """Return a PlotStyle built from UI variables, or defaults if none provided."""
    if style_vars is None:
        return PlotStyle()
    return style_vars.to_plot_style()


def get_cycle_time_column(workspace) -> str | None:
    """Resolve the best available time column for cycle-duration metrics."""

    available_columns = [str(column) for column in workspace.session.working_frame.columns]
    preferred_time_column = get_preferred_role_column(
        workspace.column_roles,
        "time",
        available_columns=available_columns,
    )
    if preferred_time_column:
        return preferred_time_column

    # Fall back to the user-selected resample time column when no role is assigned.
    if getattr(workspace, "resample_time_var", None) is not None:
        resample_time_column = workspace.resample_time_var.get().strip()
        if resample_time_column and resample_time_column != "Index" and resample_time_column in available_columns:
            return resample_time_column

    return None


def render_plot_figure(
    workspace,
    figure: plt.Figure,
    plot_type: PlotDescriptor | None = None,
) -> None:
    workspace._render_embedded_figure(
        figure=figure,
        figure_attr="_plot_figure",
        canvas_attr="_plot_canvas",
        toolbar_attr="_plot_toolbar",
        container=workspace.plot_container,
        root_window=workspace.window,
        draw_idle_on_reuse=False,
        clear_container_before_create=True,
        plot_type=plot_type,
    )


def clear_plot_container(workspace) -> None:
    if workspace._plot_figure is not None:
        plt.close(workspace._plot_figure)
        workspace._plot_figure = None
    workspace._plot_canvas = None
    workspace._plot_toolbar = None
    for widget in workspace.plot_container.winfo_children():
        widget.destroy()


def render_fft_result(
    workspace,
    result: FrequencySpectrumResult,
    plot_values: FrequencyPlotValues,
) -> None:
    display_labels = get_frequency_display_labels(result)
    for widget in workspace.fft_peaks_container.winfo_children():
        widget.destroy()
    workspace._fft_peaks_tree = None
    if workspace._fft_canvas is None:
        for widget in workspace.frequency_plot_container.winfo_children():
            widget.destroy()
    if workspace._fft_figure is not None:
        plt.close(workspace._fft_figure)
        workspace._fft_figure = None
    workspace.fft_summary_var.set(workspace._build_frequency_summary(result))

    workspace._fft_peaks_tree = render_fft_peaks_tree(
        workspace.fft_peaks_container,
        result.peaks_frame,
        value_column_label=display_labels.value_column_label,
    )

    style = get_default_plot_style(workspace.style_vars)
    frequencies = np.asarray(plot_values.frequencies)
    amplitudes = np.asarray(plot_values.magnitudes)
    has_phase = plot_values.phase_degrees is not None

    if has_phase:
        phase_title = ""
        phase_label = "Phase [deg]"
        if result.analysis_name == "Transfer Estimate":
            phase_mode_text = "wrapped" if plot_values.wrapped_phase else "unwrapped"
            phase_title = f"Transfer Phase ({phase_mode_text}; output relative to input)"
            phase_label = "Phase [deg] (output/input)"
        figure = create_magnitude_phase_figure(
            MagnitudePhasePlotData(
                x_values=frequencies,
                magnitude_values=amplitudes,
                phase_degrees=plot_values.phase_degrees if plot_values.phase_degrees is not None else (),
                magnitude_title=display_labels.plot_title,
                magnitude_label=display_labels.y_axis_label,
                phase_title=phase_title,
                phase_label=phase_label,
                wrapped_phase=plot_values.wrapped_phase,
            ),
            style=style,
        )
        axis = figure.get_axes()[0]
    else:
        figure = create_frequency_series_figure(
            FrequencySeriesPlotData(
                x_values=frequencies,
                y_values=amplitudes,
                title=display_labels.plot_title,
                y_label=display_labels.y_axis_label,
                y_limits=(-0.02, 1.02) if result.analysis_name == "Coherence" else None,
                coherence_segment_count=result.segment_count if result.analysis_name == "Coherence" else None,
            ),
            style=style,
        )
        axis = figure.get_axes()[0]

    expected_guides = get_demo_frequency_guides(workspace.session.working_frame, result.source_column, result.analysis_name)
    for guide_index, (frequency_hz, label) in enumerate(expected_guides):
        if frequency_hz <= 0 or frequency_hz > float(frequencies[-1] if frequencies.size else 0.0):
            continue
        axis.axvline(frequency_hz, color="#b45309", linestyle="--", linewidth=0.9, alpha=0.35)
        axis.text(
            frequency_hz,
            0.96 - 0.08 * (guide_index % 2),
            label,
            transform=axis.get_xaxis_transform(),
            rotation=90,
            va="top",
            ha="right",
            fontsize=7,
            color="#b45309",
        )
    apply_numeric_axis_format(axis, format_x=True, format_y=True)
    figure.tight_layout()
    render_frequency_figure(workspace, figure, PlotDescriptor("Frequency", result.analysis_name))


def clear_fft_results(workspace, message: str | None = None) -> None:
    if workspace._fft_figure is not None:
        plt.close(workspace._fft_figure)
        workspace._fft_figure = None
    workspace._fft_canvas = None
    workspace._fft_toolbar = None
    workspace._fft_peaks_tree = None
    for container in (workspace.frequency_plot_container, workspace.fft_peaks_container):
        for widget in container.winfo_children():
            widget.destroy()
    if message:
        ttk.Label(workspace.frequency_plot_container, text=message, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)


def render_spectrogram_result(
    workspace,
    result: SpectrogramResult,
    plot_data: SpectrogramPlotData,
) -> None:
    if workspace._fft_canvas is None:
        for widget in workspace.frequency_plot_container.winfo_children():
            widget.destroy()
    for widget in workspace.fft_peaks_container.winfo_children():
        widget.destroy()
    workspace._fft_peaks_tree = None
    if workspace._fft_figure is not None:
        plt.close(workspace._fft_figure)
        workspace._fft_figure = None
    workspace.fft_summary_var.set(
        f"Spectrogram | {result.source_column} | "
        f"fs = {result.sampling_frequency:.2f} Hz | "
        f"Segment: {result.segment_length} samples | "
        f"Overlap: {result.overlap_fraction:.0%} | "
        f"Window: {result.window}"
    )

    style = get_default_plot_style(workspace.style_vars)
    figure = create_spectrogram_figure(plot_data, style=style)

    render_frequency_figure(workspace, figure, PlotDescriptor("Frequency", "Spectrogram"))


def render_frequency_figure(
    workspace,
    figure: plt.Figure,
    plot_type: PlotDescriptor | None = None,
) -> None:
    workspace._render_embedded_figure(
        figure=figure,
        figure_attr="_fft_figure",
        canvas_attr="_fft_canvas",
        toolbar_attr="_fft_toolbar",
        container=workspace.frequency_plot_container,
        root_window=workspace.window,
        draw_idle_on_reuse=True,
        plot_type=plot_type,
    )
    workspace.plot_notebook.select(workspace.frequency_plot_tab)


def render_filter_bode_response(
    workspace,
    frequencies: np.ndarray,
    magnitude_db: np.ndarray,
    phase_deg: np.ndarray,
    operation: str,
) -> None:
    """Render a two-panel Bode-style response plot in the frequency plot area."""

    style = get_default_plot_style(workspace.style_vars)
    figure = create_magnitude_phase_figure(
        MagnitudePhasePlotData(
            x_values=frequencies,
            magnitude_values=magnitude_db,
            phase_degrees=phase_deg,
            magnitude_title=f"Bode Magnitude — {operation}",
            magnitude_label="Magnitude [dB]",
            phase_title="Bode Phase",
        ),
        style=style,
    )
    render_frequency_figure(workspace, figure, PlotDescriptor("Frequency", "Bode response"))


def render_signal_filter_preview(workspace, plot_data: SignalComparisonPlotData) -> None:
    """Render original and filtered signal overlay without modifying workspace data."""

    style = get_default_plot_style(workspace.style_vars)
    figure = create_signal_comparison_figure(plot_data, style=style)
    render_plot_figure(workspace, figure, PlotDescriptor("Comparison", "Filtered signal"))
    workspace.plot_notebook.select(workspace.signal_plot_tab)


def render_signal_filter_residual_preview(
    workspace,
    plot_data: ResidualSpectrumPlotData,
) -> None:
    """Render prepared residual and spectrum values without analysis calculations."""

    style = get_default_plot_style(workspace.style_vars)
    figure = create_residual_spectrum_figure(plot_data, style=style)
    render_plot_figure(workspace, figure, PlotDescriptor("Deviation", "Residual + spectrum"))
    workspace.plot_notebook.select(workspace.signal_plot_tab)


def render_cycle_result(
    workspace,
    result: CycleAnalysisResult,
    full_result: CycleAnalysisResult | None = None,
    kept_cycle_full_indices: list[int] | None = None,
) -> None:
    preserved_full_result = full_result if full_result is not None else result
    resolved_kept_full_indices = (
        list(kept_cycle_full_indices)
        if kept_cycle_full_indices is not None
        else list(range(preserved_full_result.cycle_count))
    )
    workspace._clear_cycle_results()
    workspace._full_cycle_result = preserved_full_result
    workspace._kept_cycle_full_indices = resolved_kept_full_indices
    workspace._latest_cycle_result = result
    excluded_cycles = max(0, preserved_full_result.cycle_count - result.cycle_count)
    cycle_axis_label = workspace._get_cycle_length_axis_label(result.metrics_frame)
    workspace.cycle_summary_var.set(
        " | ".join(
            [
                f"Source: {result.source_column}",
                f"Mode: {result.method}",
                f"Ref: {result.reference_column}",
                f"Cycle length: {result.cycle_length}",
                f"C2C length axis: {cycle_axis_label}",
                f"Cycles: {result.cycle_count}",
                f"Excluded: {excluded_cycles}",
                f"Dropped rows: {result.dropped_rows}",
            ]
        )
    )

    display_metrics = workspace._build_cycle_metrics_display_frame(preserved_full_result, resolved_kept_full_indices)
    workspace._cycle_metrics_tree = render_cycle_metrics_tree(workspace.cycle_metrics_container, display_metrics)
    if workspace._cycle_metrics_tree is not None:
        workspace._cycle_tree_item_to_result_index = workspace._build_cycle_tree_index_map(
            workspace._cycle_metrics_tree,
            resolved_kept_full_indices,
        )
        workspace._cycle_metrics_tree.bind("<<TreeviewSelect>>", workspace._handle_cycle_metrics_selection_changed)
        workspace._cycle_tree_item_to_full_index = workspace._build_cycle_tree_full_index_map(workspace._cycle_metrics_tree)
    render_cycle_plot(workspace, result)


def render_cycle_plot(workspace, result: CycleAnalysisResult) -> None:
    style = get_default_plot_style(workspace.style_vars)
    selected_indices = workspace._get_selected_cycle_indices()
    enabled_metrics = [
        metric_key
        for metric_key, variable in workspace.cycle_metric_toggle_vars.items()
        if variable.get()
    ]
    figure = create_cycle_figure(
        prepare_cycle_plot_data(result, selected_indices),
        enabled_metrics=enabled_metrics,
        style=style,
    )

    workspace._render_embedded_figure(
        figure=figure,
        figure_attr="_cycle_figure",
        canvas_attr="_cycle_canvas",
        toolbar_attr="_cycle_toolbar",
        container=workspace.cycle_plot_container,
        root_window=workspace.window,
        draw_idle_on_reuse=False,
        plot_type=PlotDescriptor("Cycle", result.method.replace("_", " ").title()),
    )
    workspace.notebook.select(workspace.cycles_tab)
    workspace.plot_notebook.select(workspace.cycle_plot_tab)
