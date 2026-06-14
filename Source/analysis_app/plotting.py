"""Plot orchestration helpers for AnalysisWorkspace.

This module keeps analysis-specific plotting behavior in one place while
reusing shared plotting contracts from Source.shared.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk

from Source.data_ops.cycles import CycleAnalysisResult
from Source.data_ops.spectral import FrequencySpectrumResult, SpectrogramResult
from Source.shared.column_roles import get_preferred_role_column
from Source.shared.display_format import apply_numeric_axis_format
from Source.shared.demo_catalog import get_demo_frequency_guides
from Source.shared.plot_options import PlotOptions, PlotStyle
from Source.shared.plot_utils import apply_axis_contract, create_plot_figure

from .state import PlotStyleVars
from .views import render_cycle_metrics_tree, render_fft_peaks_tree


def refresh_live_plot(workspace) -> None:
    if not workspace.session.selected_y_columns:
        clear_plot_container(workspace)
        return

    plot_options = build_time_series_plot_options(
        selected_columns=workspace.session.selected_y_columns,
        x_column=workspace.session.selected_x_column,
        use_subplots=workspace.session.use_subplots,
    )
    figure = create_plot_figure(
        plot_options,
        [workspace.session.source_path],
        {workspace.session.source_path: workspace.session.working_frame},
        column_roles=workspace.column_roles,
    )
    render_plot_figure(workspace, figure)


def update_plot(workspace) -> None:
    selected_columns = workspace._get_selected_plot_y_columns()
    if not selected_columns:
        workspace.notifications.warning("Select at least one Y column")
        return

    x_column = workspace.plot_x_var.get().strip() or "Index"
    workspace.session.selected_x_column = x_column
    workspace.session.selected_y_columns = selected_columns
    workspace.session.use_subplots = workspace.plot_subplots_var.get()

    plot_options = build_time_series_plot_options(
        selected_columns=selected_columns,
        x_column=x_column,
        use_subplots=workspace.session.use_subplots,
    )
    figure = create_plot_figure(
        plot_options,
        [workspace.session.source_path],
        {workspace.session.source_path: workspace.session.working_frame},
        column_roles=workspace.column_roles,
    )
    render_plot_figure(workspace, figure)


def build_time_series_plot_options(
    selected_columns: list[str],
    x_column: str,
    use_subplots: bool,
) -> PlotOptions:
    return PlotOptions(
        cols_to_plot=selected_columns,
        xcol=x_column,
        use_subplots=use_subplots,
        y_label="Value",
    )


def get_default_plot_style(style_vars: PlotStyleVars | None = None) -> PlotStyle:
    """Return a PlotStyle built from UI variables, or defaults if none provided."""
    if style_vars is None:
        return PlotStyle()
    _d = PlotStyle()

    def _safe_float(var, default: float) -> float:
        try:
            return float(var.get())
        except (ValueError, tk.TclError):
            return default

    def _safe_int(var, default: int) -> int:
        try:
            return int(var.get())
        except (ValueError, tk.TclError):
            return default

    return PlotStyle(
        show_grid=style_vars.show_grid.get(),
        show_subgrid=style_vars.show_subgrid.get(),
        show_legend=style_vars.show_legend.get(),
        grid_alpha=round(_safe_float(style_vars.grid_alpha, _d.grid_alpha), 2),
        subgrid_alpha=round(_safe_float(style_vars.subgrid_alpha, _d.subgrid_alpha), 2),
        line_width=max(0.1, _safe_float(style_vars.line_width, _d.line_width)),
        marker_size=max(0.5, _safe_float(style_vars.marker_size, _d.marker_size)),
        title_fontsize=max(4, _safe_int(style_vars.title_fontsize, _d.title_fontsize)),
        label_fontsize=max(4, _safe_int(style_vars.label_fontsize, _d.label_fontsize)),
        tick_fontsize=max(4, _safe_int(style_vars.tick_fontsize, _d.tick_fontsize)),
        legend_fontsize=max(4, _safe_int(style_vars.legend_fontsize, _d.legend_fontsize)),
        font_family=style_vars.font_family.get() or _d.font_family,
        marker=style_vars.marker.get() or _d.marker,
        legend_location=style_vars.legend_location.get() or _d.legend_location,
    )


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


def render_plot_figure(workspace, figure: plt.Figure) -> None:
    workspace._render_embedded_figure(
        figure=figure,
        figure_attr="_plot_figure",
        canvas_attr="_plot_canvas",
        toolbar_attr="_plot_toolbar",
        container=workspace.plot_container,
        root_window=workspace.window,
        draw_idle_on_reuse=False,
        clear_container_before_create=True,
    )


def clear_plot_container(workspace) -> None:
    if workspace._plot_figure is not None:
        plt.close(workspace._plot_figure)
        workspace._plot_figure = None
    workspace._plot_canvas = None
    workspace._plot_toolbar = None
    for widget in workspace.plot_container.winfo_children():
        widget.destroy()


def render_fft_result(workspace, result: FrequencySpectrumResult) -> None:
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
        value_column_label=result.value_column_label,
    )

    style = get_default_plot_style()
    figure, axis = plt.subplots(figsize=(6.2, 3.2), dpi=100)
    frequencies = result.frequencies[1:] if result.frequencies.size > 1 else result.frequencies
    amplitudes = result.amplitudes[1:] if result.amplitudes.size > 1 else result.amplitudes
    has_phase = result.phase is not None and result.phase.size > 0

    if has_phase:
        figure, (axis, phase_axis) = plt.subplots(2, 1, figsize=(6.2, 5.0), dpi=100, sharex=True)
        phase_values = np.degrees(result.phase[1:]) if result.phase.size > 1 else np.degrees(result.phase)
        phase_axis.plot(frequencies, phase_values, linewidth=1.0, color="#c62828")
        apply_axis_contract(phase_axis, title="", x_label="Frequency [Hz]", y_label="Phase [deg]", style=style)
        phase_axis.set_ylim(-200, 200)
        phase_axis.set_yticks([-180, -90, 0, 90, 180])
        phase_axis.margins(x=0.02)
        apply_numeric_axis_format(phase_axis, format_x=True, format_y=False)
    else:
        figure, axis = plt.subplots(figsize=(6.2, 3.2), dpi=100)
    axis.plot(frequencies, amplitudes, linewidth=1.2)
    apply_axis_contract(axis, title=result.plot_title, x_label="Frequency [Hz]", y_label=result.y_axis_label, style=style)
    axis.margins(x=0.02)
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
    render_frequency_figure(workspace, figure)


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


def render_spectrogram_result(workspace, result: SpectrogramResult) -> None:
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

    power_db = 10.0 * np.log10(result.power.T + 1e-20)
    style = get_default_plot_style()
    figure, axis = plt.subplots(figsize=(6.2, 3.8), dpi=100)
    mesh = axis.pcolormesh(
        result.times,
        result.frequencies,
        power_db,
        shading="auto",
        cmap="viridis",
    )
    figure.colorbar(mesh, ax=axis, label="Power [dB]")
    apply_axis_contract(
        axis,
        title=f"Spectrogram — {result.source_column}",
        x_label="Time [s]" if result.reference_column else "Sample",
        y_label="Frequency [Hz]",
        style=style,
    )
    apply_numeric_axis_format(axis, format_x=True, format_y=True)
    figure.tight_layout()

    render_frequency_figure(workspace, figure)


def render_frequency_figure(workspace, figure: plt.Figure) -> None:
    workspace._render_embedded_figure(
        figure=figure,
        figure_attr="_fft_figure",
        canvas_attr="_fft_canvas",
        toolbar_attr="_fft_toolbar",
        container=workspace.frequency_plot_container,
        root_window=workspace.window,
        draw_idle_on_reuse=True,
    )
    workspace.plot_notebook.select(workspace.frequency_plot_tab)


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
    style = get_default_plot_style()
    all_cycles = result.cycles_frame.to_numpy()
    max_cycle_len = all_cycles.shape[1]
    all_cycle_count = all_cycles.shape[0]

    def pad_to_max(arr, maxlen):
        if arr.shape[1] == maxlen:
            return arr
        out = np.full((arr.shape[0], maxlen), np.nan)
        out[:, :arr.shape[1]] = arr
        return out

    selected_indices = workspace._get_selected_cycle_indices()
    if not selected_indices:
        selected_indices = list(range(all_cycle_count))
    selected_cycles = result.cycles_frame.iloc[selected_indices].to_numpy()
    selected_cycles = pad_to_max(selected_cycles, max_cycle_len)

    step_values = np.arange(max_cycle_len)

    if workspace._cycle_figure is not None:
        workspace._cycle_figure.clf()
        axes = workspace._cycle_figure.subplots(3, 1, sharex=False)
    else:
        workspace._cycle_figure, axes = plt.subplots(3, 1, figsize=(6.2, 6.2), dpi=100, sharex=False)

    ax_top = axes[0]
    ax_top.clear()
    for cycle_index in range(len(selected_cycles)):
        ax_top.plot(step_values, selected_cycles[cycle_index], color="#94a3b8", alpha=0.5, linewidth=1.0)
    apply_axis_contract(
        ax_top,
        title="Selected Individual Cycles",
        x_label="Sample within cycle",
        y_label=result.source_column,
        style=style,
    )
    if max_cycle_len > 0:
        ax_top.set_xlim(0, max_cycle_len - 1)
    apply_numeric_axis_format(ax_top, format_x=True, format_y=True)

    ax_mid = axes[1]
    ax_mid.clear()
    representative = result.representative_frame
    mean_values = representative["mean"].to_numpy(dtype=float)
    std_values = representative["std"].fillna(0.0).to_numpy(dtype=float)
    support_values = representative["support_count"].to_numpy(dtype=float) if "support_count" in representative.columns else None
    ax_mid.fill_between(step_values, mean_values - std_values, mean_values + std_values, color="#14b8a6", alpha=0.18)
    ax_mid.plot(step_values, mean_values, color="#0f766e", linewidth=2.0, label="mean")
    if all_cycle_count >= 4:
        half = max(1, all_cycle_count // 2)
        early_mean = pd.DataFrame(all_cycles[:half]).mean(axis=0, skipna=True).to_numpy(dtype=float)
        late_mean = pd.DataFrame(all_cycles[-half:]).mean(axis=0, skipna=True).to_numpy(dtype=float)
        ax_mid.plot(step_values, early_mean, color="#2563eb", linewidth=1.2, linestyle="--", label="early mean")
        ax_mid.plot(step_values, late_mean, color="#dc2626", linewidth=1.2, linestyle="--", label="late mean")
    support_axis = None
    if support_values is not None and np.nanmin(support_values) < np.nanmax(support_values):
        support_axis = ax_mid.twinx()
        support_axis.plot(
            step_values,
            support_values,
            color="#475569",
            linewidth=1.1,
            linestyle=":",
            label="support",
        )
        support_axis.set_ylabel("Support [cycles]", fontsize=style.label_fontsize, color="#475569")
        support_axis.tick_params(axis="y", colors="#475569")
    apply_axis_contract(
        ax_mid,
        title="Representative Cycle (mean +- std)",
        x_label="Sample within cycle",
        y_label=result.source_column,
        style=style,
    )
    if max_cycle_len > 0:
        ax_mid.set_xlim(0, max_cycle_len - 1)
    apply_numeric_axis_format(ax_mid, format_x=True, format_y=True)
    if support_axis is not None:
        apply_numeric_axis_format(support_axis, format_x=False, format_y=True)
    mid_handles, mid_labels = ax_mid.get_legend_handles_labels()
    if support_axis is not None:
        support_handles, support_labels = support_axis.get_legend_handles_labels()
        ax_mid.legend(mid_handles + support_handles, mid_labels + support_labels, fontsize=style.legend_fontsize, loc="best")
    elif mid_handles:
        ax_mid.legend(mid_handles, mid_labels, fontsize=style.legend_fontsize, loc="best")

    ax_bot = axes[2]
    ax_bot.clear()
    metrics = result.metrics_frame
    c2c_metric_specs = [
        ("mean", "mean", metrics["mean"], 1.4, None),
        ("rms", "rms", metrics["rms"], 1.4, None),
        ("peak_to_peak", "p2p", metrics["peak_to_peak"], 1.2, None),
        ("min", "min", metrics["min"], 1.1, "#2563eb"),
        ("max", "max", metrics["max"], 1.1, "#dc2626"),
    ]
    for metric_key, label, values, linewidth, color in c2c_metric_specs:
        if not workspace.cycle_metric_toggle_vars[metric_key].get():
            continue
        plot_kwargs = {"label": label, "linewidth": linewidth}
        if color is not None:
            plot_kwargs["color"] = color
        ax_bot.plot(metrics["cycle"], values, **plot_kwargs)
    ax_bot_right = ax_bot.twinx()
    ax_bot_right.clear()
    length_series = metrics["length"]
    right_axis_values = length_series
    right_axis_label = workspace._get_cycle_length_axis_label(metrics)
    right_axis_legend = "len"
    if "duration_seconds" in metrics.columns and metrics["duration_seconds"].notna().any():
        right_axis_values = metrics["duration_seconds"]
        right_axis_legend = "dur [s]"
    ax_bot_right.plot(
        metrics["cycle"],
        right_axis_values,
        label=right_axis_legend,
        linewidth=1.4,
        color="#b45309",
        linestyle="--",
    )
    apply_axis_contract(ax_bot, title="Cycle-to-Cycle Statistics", x_label="Cycle", y_label="Metric", style=style)
    ax_bot_right.set_ylabel(right_axis_label, fontsize=style.label_fontsize, color="#b45309", labelpad=12)
    ax_bot_right.yaxis.set_label_position("right")
    ax_bot_right.yaxis.tick_right()
    ax_bot_right.tick_params(axis="y", colors="#b45309")
    left_handles, left_labels = ax_bot.get_legend_handles_labels()
    right_handles, right_labels = ax_bot_right.get_legend_handles_labels()
    ax_bot.legend(left_handles + right_handles, left_labels + right_labels, fontsize=style.legend_fontsize, loc="best")
    apply_numeric_axis_format(ax_bot, format_x=True, format_y=True)
    apply_numeric_axis_format(ax_bot_right, format_x=False, format_y=True)

    workspace._cycle_figure.tight_layout()

    workspace._render_embedded_figure(
        figure=workspace._cycle_figure,
        figure_attr="_cycle_figure",
        canvas_attr="_cycle_canvas",
        toolbar_attr="_cycle_toolbar",
        container=workspace.cycle_plot_container,
        root_window=workspace.window,
        draw_idle_on_reuse=False,
    )
    workspace.notebook.select(workspace.cycles_tab)
    workspace.plot_notebook.select(workspace.cycle_plot_tab)
