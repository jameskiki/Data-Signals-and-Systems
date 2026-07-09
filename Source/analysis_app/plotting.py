"""Plot orchestration helpers for AnalysisWorkspace.

This module keeps analysis-specific plotting behavior in one place while
reusing shared plotting contracts from Source.shared.
"""

from __future__ import annotations

from dataclasses import dataclass

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
        column_roles=workspace.column_roles,
    )
    render_plot_figure(workspace, figure)


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
    figure, axis = plt.subplots(figsize=(6.2, 3.2), dpi=100)
    frequencies = result.frequencies[1:] if result.frequencies.size > 1 else result.frequencies
    amplitudes = result.amplitudes[1:] if result.amplitudes.size > 1 else result.amplitudes
    has_phase = result.phase is not None and result.phase.size > 0

    if has_phase:
        figure, (axis, phase_axis) = plt.subplots(2, 1, figsize=(6.2, 5.0), dpi=100, sharex=True)
        phase_radians = result.phase[1:] if result.phase.size > 1 else result.phase
        unwrap_phase = bool(getattr(workspace, "transfer_unwrap_phase_var", None).get()) if hasattr(workspace, "transfer_unwrap_phase_var") else False
        if result.analysis_name == "Transfer Estimate" and unwrap_phase:
            phase_radians = np.unwrap(phase_radians)
        phase_values = np.degrees(phase_radians)
        phase_axis.plot(frequencies, phase_values, linewidth=1.0, color="#c62828")
        phase_title = ""
        phase_label = "Phase [deg]"
        if result.analysis_name == "Transfer Estimate":
            phase_mode_text = "unwrapped" if unwrap_phase else "wrapped"
            phase_title = f"Transfer Phase ({phase_mode_text}; output relative to input)"
            phase_label = "Phase [deg] (output/input)"
        apply_axis_contract(phase_axis, title=phase_title, x_label="Frequency [Hz]", y_label=phase_label, style=style)
        if not (result.analysis_name == "Transfer Estimate" and unwrap_phase):
            phase_axis.set_ylim(-200, 200)
            phase_axis.set_yticks([-180, -90, 0, 90, 180])
        phase_axis.margins(x=0.02)
        apply_numeric_axis_format(phase_axis, format_x=True, format_y=False)
    else:
        figure, axis = plt.subplots(figsize=(6.2, 3.2), dpi=100)
    axis.plot(frequencies, amplitudes, linewidth=1.2)
    apply_axis_contract(
        axis,
        title=display_labels.plot_title,
        x_label="Frequency [Hz]",
        y_label=display_labels.y_axis_label,
        style=style,
    )
    axis.margins(x=0.02)

    if result.analysis_name == "Coherence":
        axis.set_ylim(-0.02, 1.02)
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

        segment_count = result.segment_count if result.segment_count is not None else 0
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
    style = get_default_plot_style(workspace.style_vars)
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


def render_filter_bode_response(
    workspace,
    frequencies: np.ndarray,
    magnitude_db: np.ndarray,
    phase_deg: np.ndarray,
    operation: str,
) -> None:
    """Render a two-panel Bode-style response plot in the frequency plot area."""

    style = get_default_plot_style(workspace.style_vars)
    figure, (magnitude_axis, phase_axis) = plt.subplots(2, 1, figsize=(6.2, 5.0), dpi=100, sharex=True)

    magnitude_axis.plot(frequencies, magnitude_db, linewidth=1.4, color="#2563eb")
    apply_axis_contract(
        magnitude_axis,
        title=f"Bode Magnitude — {operation}",
        x_label="",
        y_label="Magnitude [dB]",
        style=style,
    )
    magnitude_axis.margins(x=0.02)
    apply_numeric_axis_format(magnitude_axis, format_x=True, format_y=True)

    phase_axis.plot(frequencies, phase_deg, linewidth=1.2, color="#c62828")
    apply_axis_contract(
        phase_axis,
        title="Bode Phase",
        x_label="Frequency [Hz]",
        y_label="Phase [deg]",
        style=style,
    )
    phase_axis.margins(x=0.02)
    apply_numeric_axis_format(phase_axis, format_x=True, format_y=True)

    figure.tight_layout()
    render_frequency_figure(workspace, figure)


def render_signal_filter_preview(
    workspace,
    source_column: str,
    operation: str,
    original_series: pd.Series,
    filtered_series: pd.Series,
    sample_spacing: float,
) -> None:
    """Render original and filtered signal overlay without modifying workspace data."""

    style = get_default_plot_style(workspace.style_vars)
    figure, axis = plt.subplots(figsize=(6.2, 3.8), dpi=100)

    original_values = pd.to_numeric(original_series, errors="coerce").to_numpy(dtype=float)
    filtered_values = pd.to_numeric(filtered_series, errors="coerce").to_numpy(dtype=float)
    sample_indices = np.arange(len(original_values), dtype=float)
    if sample_spacing > 0:
        x_values = sample_indices * sample_spacing
        x_label = "Time [s]"
    else:
        x_values = sample_indices
        x_label = "Sample"

    axis.plot(x_values, original_values, linewidth=1.0, color="#64748b", alpha=0.9, label="Original")
    axis.plot(x_values, filtered_values, linewidth=1.4, color="#1d4ed8", alpha=0.95, label="Filtered")

    apply_axis_contract(
        axis,
        title=f"Filter Preview — {source_column} ({operation})",
        x_label=x_label,
        y_label=source_column,
        style=style,
    )
    axis.margins(x=0.02)
    apply_numeric_axis_format(axis, format_x=True, format_y=True)

    figure.tight_layout()
    render_plot_figure(workspace, figure)
    workspace.plot_notebook.select(workspace.signal_plot_tab)


def render_signal_filter_residual_preview(
    workspace,
    source_column: str,
    operation: str,
    original_series: pd.Series,
    filtered_series: pd.Series,
    sample_spacing: float,
) -> None:
    """Render residual signal and quick residual spectrum preview."""

    style = get_default_plot_style(workspace.style_vars)
    figure, (residual_axis, spectrum_axis) = plt.subplots(2, 1, figsize=(6.2, 5.0), dpi=100, sharex=False)

    original_values = pd.to_numeric(original_series, errors="coerce").to_numpy(dtype=float)
    filtered_values = pd.to_numeric(filtered_series, errors="coerce").to_numpy(dtype=float)
    residual_values = original_values - filtered_values

    sample_indices = np.arange(len(residual_values), dtype=float)
    if sample_spacing > 0:
        x_values = sample_indices * sample_spacing
        x_label = "Time [s]"
    else:
        x_values = sample_indices
        x_label = "Sample"

    residual_axis.plot(x_values, residual_values, linewidth=1.2, color="#b45309", label="Residual")
    apply_axis_contract(
        residual_axis,
        title=f"Residual Preview — {source_column} ({operation})",
        x_label=x_label,
        y_label="Original - Filtered",
        style=style,
    )
    residual_axis.margins(x=0.02)
    apply_numeric_axis_format(residual_axis, format_x=True, format_y=True)

    valid_residual = residual_values[np.isfinite(residual_values)]
    if valid_residual.size >= 4:
        centered = valid_residual - np.mean(valid_residual)
        if sample_spacing > 0:
            frequencies = np.fft.rfftfreq(centered.size, d=sample_spacing)
            spectrum = np.abs(np.fft.rfft(centered)) / max(centered.size, 1)
            spectrum_axis.plot(frequencies, spectrum, linewidth=1.1, color="#1d4ed8")
            spectrum_x_label = "Frequency [Hz]"
        else:
            frequency_bins = np.arange(np.fft.rfft(centered).size, dtype=float)
            spectrum = np.abs(np.fft.rfft(centered)) / max(centered.size, 1)
            spectrum_axis.plot(frequency_bins, spectrum, linewidth=1.1, color="#1d4ed8")
            spectrum_x_label = "FFT bin"
        apply_axis_contract(
            spectrum_axis,
            title="Residual Spectrum",
            x_label=spectrum_x_label,
            y_label="Amplitude",
            style=style,
        )
        spectrum_axis.margins(x=0.02)
        apply_numeric_axis_format(spectrum_axis, format_x=True, format_y=True)
    else:
        spectrum_axis.text(
            0.5,
            0.5,
            "Residual spectrum unavailable (need at least 4 finite samples).",
            transform=spectrum_axis.transAxes,
            ha="center",
            va="center",
        )
        apply_axis_contract(
            spectrum_axis,
            title="Residual Spectrum",
            x_label="",
            y_label="",
            style=style,
        )

    figure.tight_layout()
    render_plot_figure(workspace, figure)
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
