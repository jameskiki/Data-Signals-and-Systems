"""Interactive analysis workspace for exploring a loaded dataframe."""

import os
from collections.abc import Callable

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from shared.documentation_links import open_documentation_path
from shared.notifications import NotificationManager
from .actions import (
    build_derived_signal_update,
    build_reset_update,
    build_signal_filter_update,
    build_simple_filter_update,
)
from .layout import build_analysis_workspace_ui
from .refresh import (
    refresh_filter_controls,
    refresh_overview,
    refresh_plot_controls,
    refresh_role_widget_styles,
    refresh_sidebar,
    set_default_output_names,
)
from .state import (
    ANALYSIS_WINDOW_GEOMETRY,
    DERIVED_OPERATIONS,
    FFT_WINDOW_OPTIONS,
    PREVIEW_ROW_LIMIT,
    AnalysisSession,
    UI_FREQUENCY_ANALYSIS_METHODS,
)
from .views import render_correlation_view, render_dataframe_preview, render_fft_peaks_tree, render_statistics_tree
from .views import render_cycle_metrics_tree
from data_ops.cycles import (
    CycleAnalysisResult,
    compute_fixed_length_cycle_analysis,
    compute_cycle_analysis_from_ranges,
    detect_peak_cycle_ranges,
    detect_rising_edge_cycle_ranges,
    detect_zero_crossing_cycle_ranges,
    rebuild_cycle_analysis_result,
)
from shared.display_format import apply_numeric_axis_format, format_display_number, format_display_percent
from shared.column_roles import (
    apply_literal_role_combobox_style,
    get_column_role,
    get_column_role_cell_colors,
    get_preferred_role_column,
    summarize_column_roles,
    update_projected_column_roles,
)
from shared.demo_catalog import describe_demo_frequency_expectations, get_demo_frequency_guides

from data_ops.filtering import resolve_filtered_column_name
from data_ops.frame_ops import keep_dataframe_index_ranges, resample_to_uniform
from data_ops.models import SIGNAL_FILTER_OPERATIONS
from data_ops.spectral import (
    FrequencySpectrumResult,
    SpectrogramResult,
    compute_coherence_spectrum,
    compute_fft_spectrum,
    compute_spectrogram,
    compute_transfer_estimate,
    compute_welch_psd,
)
from data_ops.summary import summarize_dataframe
from shared.plot_utils import create_plot_figure


class AnalysisWorkspace:
    """Tkinter window for filtering, deriving, plotting, and exporting one dataset."""

    def __init__(
        self,
        parent: tk.Misc,
        dataset_path: str,
        dataframe: pd.DataFrame,
        column_roles: dict[str, str] | None = None,
        dataset_description: str = "",
        on_close: Callable[["AnalysisWorkspace"], None] | None = None,
    ) -> None:
        self.parent = parent
        self.on_close = on_close
        self.column_roles = dict(column_roles or {})
        self.dataset_description = dataset_description
        self.notifications = NotificationManager()
        self.session = AnalysisSession(
            source_path=dataset_path,
            original_frame=dataframe.copy(),
            working_frame=dataframe.copy(),
        )
        self.window = tk.Toplevel(parent)
        self.window.title(f"Analysis Workspace - {os.path.basename(dataset_path)}")
        self.window.geometry(ANALYSIS_WINDOW_GEOMETRY)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.dataset_label_var = tk.StringVar()
        self.original_shape_var = tk.StringVar()
        self.working_shape_var = tk.StringVar()
        self.numeric_columns_var = tk.StringVar()
        self.role_summary_var = tk.StringVar(value=summarize_column_roles(self.column_roles))
        self.active_column_var = tk.StringVar()

        self.filter_min_var = tk.StringVar()
        self.filter_max_var = tk.StringVar()
        self.keep_missing_var = tk.BooleanVar(value=False)
        self.filter_output_name_var = tk.StringVar()
        self.signal_filter_operation_var = tk.StringVar(value=SIGNAL_FILTER_OPERATIONS[0])
        self.signal_filter_window_var = tk.StringVar(value="5")
        self.signal_filter_alpha_var = tk.StringVar(value="0.2")
        self.signal_filter_name_var = tk.StringVar()
        self.signal_filter_cutoff_var = tk.StringVar(value="10.0")
        self.signal_filter_order_var = tk.StringVar(value="4")
        self.signal_filter_spacing_var = tk.StringVar(value="0.0")

        self.resample_time_var = tk.StringVar(value="Index")
        self.resample_spacing_var = tk.StringVar(value="1.0")

        self.derived_operation_var = tk.StringVar(value=DERIVED_OPERATIONS[0])
        self.derived_source_var = tk.StringVar()
        self.derived_reference_var = tk.StringVar(value="Index")
        self.derived_name_var = tk.StringVar()
        self.derived_window_var = tk.StringVar(value="5")

        self.plot_x_var = tk.StringVar(value="Index")
        self.plot_y_selection_summary_var = tk.StringVar(value="No numeric channels available")
        self.plot_subplots_var = tk.BooleanVar(value=True)
        self.frequency_analysis_var = tk.StringVar(value=UI_FREQUENCY_ANALYSIS_METHODS[0])
        self.fft_reference_var = tk.StringVar(value="Index")
        self.frequency_compare_var = tk.StringVar(value="")
        self.fft_sample_spacing_var = tk.StringVar(value="1.0")
        self.fft_window_var = tk.StringVar(value=FFT_WINDOW_OPTIONS[0])
        self.fft_detrend_var = tk.BooleanVar(value=True)
        self.welch_segment_length_var = tk.StringVar(value="256")
        self.welch_overlap_fraction_var = tk.StringVar(value="0.5")
        self.fft_summary_var = tk.StringVar(value=self._default_frequency_summary_text())
        self.frequency_expectation_var = tk.StringVar(value="Select a signal to see built-in hints for demo datasets.")
        self.cycle_length_var = tk.StringVar(value="100")
        self.cycle_mode_var = tk.StringVar(value="fixed_length")
        self.cycle_reference_var = tk.StringVar(value="Index")
        self.cycle_threshold_var = tk.StringVar(value="0.0")
        self.cycle_max_cycles_var = tk.StringVar(value="")
        self.cycle_prominence_var = tk.StringVar(value="0.0")
        self.cycle_summary_var = tk.StringVar(value="Analyze equal-length cycles for the active column.")
        self.cycle_metric_toggle_vars: dict[str, tk.BooleanVar] = {
            "mean": tk.BooleanVar(value=True),
            "rms": tk.BooleanVar(value=True),
            "peak_to_peak": tk.BooleanVar(value=True),
            "min": tk.BooleanVar(value=True),
            "max": tk.BooleanVar(value=True),
        }

        self._plot_figure: plt.Figure | None = None
        self._plot_canvas: FigureCanvasTkAgg | None = None
        self._plot_toolbar: NavigationToolbar2Tk | None = None
        self._fft_figure: plt.Figure | None = None
        self._fft_canvas: FigureCanvasTkAgg | None = None
        self._fft_toolbar: NavigationToolbar2Tk | None = None
        self._preview_tree: tk.Widget | None = None
        self._stats_tree: ttk.Treeview | None = None
        self._correlation_widget: tk.Widget | None = None
        self._fft_peaks_tree: ttk.Treeview | None = None
        self._cycle_figure: plt.Figure | None = None
        self._cycle_canvas: FigureCanvasTkAgg | None = None
        self._cycle_toolbar: NavigationToolbar2Tk | None = None
        self._cycle_metrics_tree: ttk.Treeview | None = None
        self._cycle_tree_item_to_result_index: dict[str, int] = {}
        self._cycle_tree_item_to_full_index: dict[str, int] = {}
        self._kept_cycle_full_indices: list[int] = []
        self._full_cycle_result: CycleAnalysisResult | None = None
        self._latest_cycle_result: CycleAnalysisResult | None = None
        self.plot_y_selector_button: ttk.Menubutton | None = None
        self.plot_y_selector_menu: tk.Menu | None = None
        self.plot_y_selection_vars: dict[str, tk.BooleanVar] = {}
        self._plot_y_selector_sync_in_progress = False
        self._frame_replacing = False
        self._refreshing_frequency_controls = False

        build_analysis_workspace_ui(self)
        self.active_column_var.trace_add("write", self._handle_active_column_changed)
        self.frequency_analysis_var.trace_add("write", self._handle_frequency_expectation_changed)
        self.frequency_compare_var.trace_add("write", self._handle_frequency_expectation_changed)
        self.plot_x_var.trace_add("write", self._handle_role_widget_selection_changed)
        self.derived_reference_var.trace_add("write", self._handle_role_widget_selection_changed)
        self.fft_reference_var.trace_add("write", self._handle_role_widget_selection_changed)
        self.cycle_reference_var.trace_add("write", self._handle_role_widget_selection_changed)
        self.signal_filter_operation_var.trace_add("write", self._handle_output_defaults_changed)
        self.derived_operation_var.trace_add("write", self._handle_output_defaults_changed)
        self.cycle_mode_var.trace_add("write", lambda *_: self._refresh_cycle_method_controls())
        for metric_toggle_var in self.cycle_metric_toggle_vars.values():
            metric_toggle_var.trace_add("write", self._handle_cycle_metric_toggle_changed)
        self._refresh_all_views()
        self._refresh_cycle_method_controls()
        self._refresh_live_plot()

    def close(self) -> None:
        """Destroy the window and release plotting resources."""

        if self._plot_figure is not None:
            plt.close(self._plot_figure)
            self._plot_figure = None
        if self._fft_figure is not None:
            plt.close(self._fft_figure)
            self._fft_figure = None
        if self._cycle_figure is not None:
            plt.close(self._cycle_figure)
            self._cycle_figure = None
        self._fft_toolbar = None
        self._cycle_toolbar = None
        self.window.destroy()
        if self.on_close is not None:
            self.on_close(self)

    def _refresh_cycle_method_controls(self) -> None:
        mode = self.cycle_mode_var.get().strip() or "fixed_length"
        # Hide all frames first
        if hasattr(self, "cycle_fixed_frame") and self.cycle_fixed_frame is not None:
            self.cycle_fixed_frame.grid_remove()
        if hasattr(self, "cycle_edge_frame") and self.cycle_edge_frame is not None:
            self.cycle_edge_frame.grid_remove()
        if hasattr(self, "cycle_peak_frame") and self.cycle_peak_frame is not None:
            self.cycle_peak_frame.grid_remove()
        if hasattr(self, "cycle_max_frame") and self.cycle_max_frame is not None:
            self.cycle_max_frame.grid_remove()

        # Show relevant frames
        if mode == "fixed_length":
            self.cycle_fixed_frame.grid()
        elif mode in {"rising_edge", "zero_crossing"}:
            self.cycle_edge_frame.grid()
            self.cycle_max_frame.grid()
        elif mode == "peak":
            self.cycle_peak_frame.grid()
            self.cycle_max_frame.grid()

    def _ensure_current_summary(self) -> None:
        if self.session.last_summary is not None and self.session.last_summary_revision == self.session.working_revision:
            return
        self.session.last_summary = summarize_dataframe(self.session.working_frame)
        self.session.last_summary_revision = self.session.working_revision

    def _refresh_all_views(self, refresh_summary: bool = True) -> None:
        if refresh_summary:
            self._ensure_current_summary()
        refresh_sidebar(self)
        refresh_overview(self)
        self._refresh_preview()
        refresh_filter_controls(self)
        self._refresh_statistics()
        refresh_plot_controls(self)
        self._refresh_frequency_expectation()
        self._refresh_frequency_method_controls()
        self._refresh_cycle_method_controls()

    def _refresh_summary_views(self) -> None:
        self._ensure_current_summary()
        refresh_sidebar(self)
        refresh_overview(self)
        self._refresh_statistics()

    def refresh_column_roles(self, column_roles: dict[str, str]) -> None:
        self.column_roles = dict(column_roles)
        self._refresh_all_views(refresh_summary=False)
        self._refresh_live_plot()

    def _refresh_preview(self) -> None:
        self._preview_tree = render_dataframe_preview(
            self.preview_container,
            self.session.working_frame,
            PREVIEW_ROW_LIMIT,
            self.column_roles,
        )

    def _refresh_statistics(self) -> None:
        stats_frame = self.session.last_summary.statistics_frame if self.session.last_summary else pd.DataFrame()
        self._stats_tree = render_statistics_tree(self.stats_container, stats_frame, self.column_roles)

        correlation_frame = self.session.last_summary.correlation_frame if self.session.last_summary else pd.DataFrame()
        self._correlation_widget = render_correlation_view(self.correlation_container, correlation_frame)

    def _refresh_live_plot(self) -> None:
        if not self.session.selected_y_columns:
            self._clear_plot_container()
            return

        from shared.plot_options import PlotOptions
        plot_options = PlotOptions(
            cols_to_plot=self.session.selected_y_columns,
            xcol=self.session.selected_x_column,
            use_subplots=self.session.use_subplots,
        )
        figure = create_plot_figure(
            plot_options,
            [self.session.source_path],
            {self.session.source_path: self.session.working_frame},
            column_roles=self.column_roles,
        )
        self._render_plot_figure(figure)

    def _apply_filter(self) -> None:
        column = self.active_column_var.get().strip()
        if not column:
            messagebox.showwarning("Warning", "Select an active analysis column")
            return

        output_column = resolve_filtered_column_name(column, self.filter_output_name_var.get())

        try:
            update = build_simple_filter_update(
                self.session.working_frame,
                active_column=column,
                output_name=self.filter_output_name_var.get(),
                minimum_value=self.filter_min_var.get(),
                maximum_value=self.filter_max_var.get(),
                keep_missing=self.keep_missing_var.get(),
            )
        except Exception as error:
            messagebox.showerror("Filter Error", str(error))
            return

        self._replace_working_frame(
            update.dataframe,
            update.history_entry,
            role_overrides={output_column: self.column_roles.get(column, "signal")},
            focus_column=output_column,
        )

    def _apply_signal_filter(self) -> None:
        source_column = self.active_column_var.get().strip()
        operation = self.signal_filter_operation_var.get().strip()
        if not source_column:
            messagebox.showwarning("Warning", "Select an active analysis column")
            return

        output_column = resolve_filtered_column_name(source_column, self.signal_filter_name_var.get())

        try:
            update = build_signal_filter_update(
                self.session.working_frame,
                source_column=source_column,
                operation=operation,
                output_name=self.signal_filter_name_var.get(),
                window_size=int(self.signal_filter_window_var.get() or "5"),
                alpha=float(self.signal_filter_alpha_var.get() or "0.2"),
                cutoff_hz=float(self.signal_filter_cutoff_var.get() or "10.0"),
                sample_spacing=float(self.signal_filter_spacing_var.get() or "0.0"),
                filter_order=int(self.signal_filter_order_var.get() or "4"),
            )
        except Exception as error:
            messagebox.showerror("Signal Filter Error", str(error))
            return

        self._replace_working_frame(
            update.dataframe,
            update.history_entry,
            role_overrides={output_column: self.column_roles.get(source_column, "signal")},
            focus_column=output_column,
        )
        self.signal_filter_name_var.set("")

    def _apply_resample(self) -> None:
        time_column = self.resample_time_var.get().strip()
        if not time_column or time_column == "Index":
            messagebox.showwarning("Warning", "Select a time column for resampling")
            return

        try:
            target_spacing = float(self.resample_spacing_var.get() or "1.0")
            resampled = resample_to_uniform(
                self.session.working_frame,
                time_column=time_column,
                target_spacing=target_spacing,
            )
        except Exception as error:
            messagebox.showerror("Resample Error", str(error))
            return

        self._replace_working_frame(
            resampled,
            f"Resampled to uniform grid (spacing={target_spacing}) using {time_column}",
        )

    def _apply_derived_signal(self) -> None:
        source_column = self.active_column_var.get().strip()
        operation = self.derived_operation_var.get().strip()
        new_column = self.derived_name_var.get().strip()
        reference_column = self.derived_reference_var.get().strip() or "Index"
        if not source_column:
            messagebox.showwarning("Warning", "Select an active analysis column")
            return

        try:
            update = build_derived_signal_update(
                self.session.working_frame,
                source_column=source_column,
                operation=operation,
                new_column=new_column,
                reference_column=None if reference_column == "Index" else reference_column,
                window_size=int(self.derived_window_var.get() or "5"),
            )
        except Exception as error:
            messagebox.showerror("Derived Signal Error", str(error))
            return

        derived_role = self.column_roles.get(source_column, "signal")
        if derived_role == "time":
            derived_role = "signal"
        self._replace_working_frame(
            update.dataframe,
            update.history_entry,
            role_overrides={new_column: derived_role},
            focus_column=new_column,
        )
        self.derived_name_var.set("")

    def _compute_fft(self) -> None:
        source_column = self.active_column_var.get().strip()
        if not source_column:
            messagebox.showwarning("Warning", "Select an active analysis column")
            return

        reference_column = self.fft_reference_var.get().strip() or "Index"
        analysis_name = self.frequency_analysis_var.get().strip() or UI_FREQUENCY_ANALYSIS_METHODS[0]
        try:
            common_kwargs = {
                "dataframe": self.session.working_frame,
                "source_column": source_column,
                "reference_column": None if reference_column == "Index" else reference_column,
                "sample_spacing": float(self.fft_sample_spacing_var.get() or "1.0"),
                "window": self.fft_window_var.get().strip(),
                "detrend": self.fft_detrend_var.get(),
            }
            if analysis_name == "Spectrogram":
                spectrogram_result = compute_spectrogram(
                    **common_kwargs,
                    segment_length=int(self.welch_segment_length_var.get() or "256"),
                    overlap_fraction=float(self.welch_overlap_fraction_var.get() or "0.5"),
                )
                self._render_spectrogram_result(spectrogram_result)
                self.notifications.success(
                    f"Computed Spectrogram for {source_column} "
                    f"(segment={spectrogram_result.segment_length}, fs={spectrogram_result.sampling_frequency:.1f} Hz)"
                )
                return
            elif analysis_name == "Welch PSD":
                result = compute_welch_psd(
                    **common_kwargs,
                    segment_length=int(self.welch_segment_length_var.get() or "256"),
                    overlap_fraction=float(self.welch_overlap_fraction_var.get() or "0.5"),
                )
            elif analysis_name == "Transfer Estimate":
                result = compute_transfer_estimate(
                    **common_kwargs,
                    comparison_column=self.frequency_compare_var.get().strip(),
                    segment_length=int(self.welch_segment_length_var.get() or "256"),
                    overlap_fraction=float(self.welch_overlap_fraction_var.get() or "0.5"),
                )
            elif analysis_name == "Coherence":
                result = compute_coherence_spectrum(
                    **common_kwargs,
                    comparison_column=self.frequency_compare_var.get().strip(),
                    segment_length=int(self.welch_segment_length_var.get() or "256"),
                    overlap_fraction=float(self.welch_overlap_fraction_var.get() or "0.5"),
                )
            else:
                result = compute_fft_spectrum(**common_kwargs)
        except Exception as error:
            messagebox.showerror("Frequency Analysis Error", str(error))
            return

        self._render_fft_result(result)
        self.notifications.success(
            f"Computed {result.analysis_name} for {source_column} using {reference_column} with {result.window} window"
        )

    def _compute_cycle_analysis(self) -> None:
        source_column = self.active_column_var.get().strip()
        if not source_column:
            messagebox.showwarning("Warning", "Select an active analysis column")
            return

        time_column = self._get_cycle_time_column()

        try:
            cycle_length = int(self.cycle_length_var.get().strip() or "0")
            max_cycles_text = self.cycle_max_cycles_var.get().strip()
            max_cycles = int(max_cycles_text) if max_cycles_text else None
            cycle_mode = self.cycle_mode_var.get().strip() or "fixed_length"
            if cycle_mode == "rising_edge":
                reference_column = self.cycle_reference_var.get().strip() or "Index"
                threshold = float(self.cycle_threshold_var.get().strip() or "0.0")
                resolved_reference = source_column if reference_column == "Index" else reference_column
                cycle_ranges = detect_rising_edge_cycle_ranges(
                    self.session.working_frame,
                    reference_column=resolved_reference,
                    threshold=threshold,
                    min_cycle_length=cycle_length,
                    max_cycles=max_cycles,
                )
                result = compute_cycle_analysis_from_ranges(
                    self.session.working_frame,
                    source_column=source_column,
                    cycle_ranges=cycle_ranges,
                    method="rising_edge",
                    reference_column=resolved_reference,
                    time_column=time_column,
                )
            elif cycle_mode == "zero_crossing":
                reference_column = self.cycle_reference_var.get().strip() or "Index"
                resolved_reference = source_column if reference_column == "Index" else reference_column
                cycle_ranges = detect_zero_crossing_cycle_ranges(
                    self.session.working_frame,
                    reference_column=resolved_reference,
                    direction="rising",
                    min_cycle_length=cycle_length,
                    max_cycles=max_cycles,
                )
                result = compute_cycle_analysis_from_ranges(
                    self.session.working_frame,
                    source_column=source_column,
                    cycle_ranges=cycle_ranges,
                    method="zero_crossing",
                    reference_column=resolved_reference,
                    time_column=time_column,
                )
            elif cycle_mode == "peak":
                reference_column = self.cycle_reference_var.get().strip() or "Index"
                resolved_reference = source_column if reference_column == "Index" else reference_column
                prominence = float(self.cycle_prominence_var.get().strip() or "0.0")
                cycle_ranges = detect_peak_cycle_ranges(
                    self.session.working_frame,
                    reference_column=resolved_reference,
                    min_cycle_length=cycle_length,
                    prominence=prominence,
                    max_cycles=max_cycles,
                )
                result = compute_cycle_analysis_from_ranges(
                    self.session.working_frame,
                    source_column=source_column,
                    cycle_ranges=cycle_ranges,
                    method="peak",
                    reference_column=resolved_reference,
                    time_column=time_column,
                )
            else:
                result = compute_fixed_length_cycle_analysis(
                    self.session.working_frame,
                    source_column=source_column,
                    cycle_length=cycle_length,
                    max_cycles=max_cycles,
                    time_column=time_column,
                )
        except Exception as error:
            messagebox.showerror("Cycle Analysis Error", str(error))
            return

        self._render_cycle_result(result)
        self.notifications.success(
            f"Analyzed {result.cycle_count} cycles of length {result.cycle_length} for {source_column}"
        )

    def _update_plot(self) -> None:
        selected_columns = self._get_selected_plot_y_columns()
        if not selected_columns:
            messagebox.showwarning("Warning", "Select at least one Y column")
            return

        x_column = self.plot_x_var.get().strip() or "Index"
        self.session.selected_x_column = x_column
        self.session.selected_y_columns = selected_columns
        self.session.use_subplots = self.plot_subplots_var.get()

        from shared.plot_options import PlotOptions
        plot_options = PlotOptions(
            cols_to_plot=selected_columns,
            xcol=x_column,
            use_subplots=self.session.use_subplots,
        )
        figure = create_plot_figure(
            plot_options,
            [self.session.source_path],
            {self.session.source_path: self.session.working_frame},
            column_roles=self.column_roles,
        )
        self._render_plot_figure(figure)

    def _render_plot_figure(self, figure: plt.Figure) -> None:
        if self._plot_canvas is not None:
            if self._plot_figure is not None:
                plt.close(self._plot_figure)
            self._plot_figure = figure
            self._plot_canvas.figure = figure
            figure.canvas = self._plot_canvas
            self._sync_plot_canvas_size()
            self._plot_canvas.draw()
            if self._plot_toolbar is not None:
                self._plot_toolbar.update()
        else:
            self._clear_plot_container()
            self._plot_figure = figure
            self._plot_canvas = FigureCanvasTkAgg(figure, master=self.plot_container)
            self._plot_canvas.draw()
            self._plot_toolbar = NavigationToolbar2Tk(self._plot_canvas, self.plot_container)
            self._plot_toolbar.update()
            self._plot_toolbar.pack(side=tk.TOP, fill=tk.X)
            self._plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
            self.window.after_idle(self._sync_plot_canvas_size)
            self.window.after_idle(self._plot_canvas.draw)

    def _sync_plot_canvas_size(self) -> None:
        if self._plot_canvas is None or self._plot_figure is None:
            return
        canvas_widget = self._plot_canvas.get_tk_widget()
        canvas_widget.update_idletasks()
        width = max(canvas_widget.winfo_width(), 1)
        height = max(canvas_widget.winfo_height(), 1)
        dpi = float(self._plot_figure.get_dpi() or 100.0)
        self._plot_figure.set_size_inches(width / dpi, height / dpi, forward=True)

    def _clear_plot_container(self) -> None:
        if self._plot_figure is not None:
            plt.close(self._plot_figure)
            self._plot_figure = None
        self._plot_canvas = None
        self._plot_toolbar = None
        for widget in self.plot_container.winfo_children():
            widget.destroy()

    def _render_fft_result(self, result: FrequencySpectrumResult) -> None:
        # Partial clear: preserve the canvas widget for reuse; only destroy peaks
        # tree children and (first time) any stale message labels in the plot container.
        for widget in self.fft_peaks_container.winfo_children():
            widget.destroy()
        self._fft_peaks_tree = None
        if self._fft_canvas is None:
            for widget in self.frequency_plot_container.winfo_children():
                widget.destroy()
        if self._fft_figure is not None:
            plt.close(self._fft_figure)
            self._fft_figure = None
        self.fft_summary_var.set(self._build_frequency_summary(result))

        self._fft_peaks_tree = render_fft_peaks_tree(
            self.fft_peaks_container,
            result.peaks_frame,
            value_column_label=result.value_column_label,
        )

        figure, axis = plt.subplots(figsize=(6.2, 3.2), dpi=100)
        frequencies = result.frequencies[1:] if result.frequencies.size > 1 else result.frequencies
        amplitudes = result.amplitudes[1:] if result.amplitudes.size > 1 else result.amplitudes
        has_phase = result.phase is not None and result.phase.size > 0

        if has_phase:
            figure, (axis, phase_axis) = plt.subplots(2, 1, figsize=(6.2, 5.0), dpi=100, sharex=True)
            phase_values = np.degrees(result.phase[1:]) if result.phase.size > 1 else np.degrees(result.phase)
            phase_axis.plot(frequencies, phase_values, linewidth=1.0, color="#c62828")
            phase_axis.set_xlabel("Frequency [Hz]", fontsize=9)
            phase_axis.set_ylabel("Phase [deg]", fontsize=9)
            phase_axis.set_ylim(-200, 200)
            phase_axis.set_yticks([-180, -90, 0, 90, 180])
            phase_axis.grid(True, alpha=0.3)
            phase_axis.margins(x=0.02)
            apply_numeric_axis_format(phase_axis, format_x=True, format_y=False)
        else:
            figure, axis = plt.subplots(figsize=(6.2, 3.2), dpi=100)
        axis.plot(frequencies, amplitudes, linewidth=1.2)
        axis.set_title(result.plot_title, fontsize=10)
        axis.set_xlabel("Frequency [Hz]", fontsize=9)
        axis.set_ylabel(result.y_axis_label, fontsize=9)
        axis.grid(True, alpha=0.3)
        axis.margins(x=0.02)
        expected_guides = get_demo_frequency_guides(self.session.working_frame, result.source_column, result.analysis_name)
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

        self._fft_figure = figure
        if self._fft_canvas is not None:
            self._fft_canvas.figure = figure
            figure.canvas = self._fft_canvas
            self._fft_canvas.draw_idle()
            if self._fft_toolbar is not None:
                self._fft_toolbar.update()
        else:
            self._fft_canvas = FigureCanvasTkAgg(figure, master=self.frequency_plot_container)
            self._fft_canvas.draw()
            self._fft_toolbar = NavigationToolbar2Tk(self._fft_canvas, self.frequency_plot_container)
            self._fft_toolbar.update()
            self._fft_toolbar.pack(side=tk.TOP, fill=tk.X)
            self._fft_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
        self.plot_notebook.select(self.frequency_plot_tab)

    def _clear_fft_results(self, message: str | None = None) -> None:
        if self._fft_figure is not None:
            plt.close(self._fft_figure)
            self._fft_figure = None
        self._fft_canvas = None
        self._fft_toolbar = None
        self._fft_peaks_tree = None
        for container in (self.frequency_plot_container, self.fft_peaks_container):
            for widget in container.winfo_children():
                widget.destroy()
        if message:
            ttk.Label(self.frequency_plot_container, text=message, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)

    def _render_spectrogram_result(self, result: SpectrogramResult) -> None:
        # Partial clear: preserve canvas for reuse.
        if self._fft_canvas is None:
            for widget in self.frequency_plot_container.winfo_children():
                widget.destroy()
        for widget in self.fft_peaks_container.winfo_children():
            widget.destroy()
        self._fft_peaks_tree = None
        if self._fft_figure is not None:
            plt.close(self._fft_figure)
            self._fft_figure = None
        self.fft_summary_var.set(
            f"Spectrogram | {result.source_column} | "
            f"fs = {result.sampling_frequency:.2f} Hz | "
            f"Segment: {result.segment_length} samples | "
            f"Overlap: {result.overlap_fraction:.0%} | "
            f"Window: {result.window}"
        )

        power_db = 10.0 * np.log10(result.power.T + 1e-20)
        figure, axis = plt.subplots(figsize=(6.2, 3.8), dpi=100)
        mesh = axis.pcolormesh(
            result.times,
            result.frequencies,
            power_db,
            shading="auto",
            cmap="viridis",
        )
        figure.colorbar(mesh, ax=axis, label="Power [dB]")
        axis.set_title(f"Spectrogram — {result.source_column}", fontsize=10)
        axis.set_xlabel("Time [s]" if result.reference_column else "Sample", fontsize=9)
        axis.set_ylabel("Frequency [Hz]", fontsize=9)
        apply_numeric_axis_format(axis, format_x=True, format_y=True)
        figure.tight_layout()

        self._fft_figure = figure
        if self._fft_canvas is not None:
            self._fft_canvas.figure = figure
            figure.canvas = self._fft_canvas
            self._fft_canvas.draw_idle()
            if self._fft_toolbar is not None:
                self._fft_toolbar.update()
        else:
            self._fft_canvas = FigureCanvasTkAgg(figure, master=self.frequency_plot_container)
            self._fft_canvas.draw()
            self._fft_toolbar = NavigationToolbar2Tk(self._fft_canvas, self.frequency_plot_container)
            self._fft_toolbar.update()
            self._fft_toolbar.pack(side=tk.TOP, fill=tk.X)
            self._fft_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
        self.plot_notebook.select(self.frequency_plot_tab)

    def _render_cycle_result(
        self,
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
        self._clear_cycle_results()
        self._full_cycle_result = preserved_full_result
        self._kept_cycle_full_indices = resolved_kept_full_indices
        self._latest_cycle_result = result
        excluded_cycles = max(0, preserved_full_result.cycle_count - result.cycle_count)
        cycle_axis_label = self._get_cycle_length_axis_label(result.metrics_frame)
        self.cycle_summary_var.set(
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

        display_metrics = self._build_cycle_metrics_display_frame(preserved_full_result, resolved_kept_full_indices)
        self._cycle_metrics_tree = render_cycle_metrics_tree(self.cycle_metrics_container, display_metrics)
        if self._cycle_metrics_tree is not None:
            self._cycle_tree_item_to_result_index = self._build_cycle_tree_index_map(
                self._cycle_metrics_tree,
                resolved_kept_full_indices,
            )
            self._cycle_metrics_tree.bind("<<TreeviewSelect>>", self._handle_cycle_metrics_selection_changed)
            self._cycle_tree_item_to_full_index = self._build_cycle_tree_full_index_map(self._cycle_metrics_tree)
        self._render_cycle_plot(result)

    def _render_cycle_plot(self, result: CycleAnalysisResult) -> None:
        # Always use all cycles for representative and C2C plots
        all_cycles = result.cycles_frame.to_numpy()
        max_cycle_len = all_cycles.shape[1]
        all_cycle_count = all_cycles.shape[0]

        # Pad all cycles to max length (should already be the case, but ensure)
        def pad_to_max(arr, maxlen):
            if arr.shape[1] == maxlen:
                return arr
            out = np.full((arr.shape[0], maxlen), np.nan)
            out[:, :arr.shape[1]] = arr
            return out

        # Top: only selected cycles, padded
        selected_indices = self._get_selected_cycle_indices()
        if not selected_indices:
            selected_indices = list(range(all_cycle_count))
        selected_cycles = result.cycles_frame.iloc[selected_indices].to_numpy()
        selected_cycles = pad_to_max(selected_cycles, max_cycle_len)

        # X axis for cycles
        step_values = np.arange(max_cycle_len)

        # Reuse or create the figure and axes (OO-API)
        if self._cycle_figure is not None:
            self._cycle_figure.clf()
            axes = self._cycle_figure.subplots(3, 1, sharex=False)
        else:
            self._cycle_figure, axes = plt.subplots(3, 1, figsize=(6.2, 6.2), dpi=100, sharex=False)

        # Top: Individual cycles (selected only)
        ax_top = axes[0]
        ax_top.clear()
        for cycle_index in range(len(selected_cycles)):
            ax_top.plot(step_values, selected_cycles[cycle_index], color="#94a3b8", alpha=0.5, linewidth=1.0)
        ax_top.set_title("Selected Individual Cycles", fontsize=10)
        ax_top.set_xlabel("Sample within cycle", fontsize=9)
        ax_top.set_ylabel(result.source_column, fontsize=9)
        ax_top.grid(True, alpha=0.3)
        # Keep top and middle cycle plots on the same x-domain even when selected cycles are shorter.
        if max_cycle_len > 0:
            ax_top.set_xlim(0, max_cycle_len - 1)
        apply_numeric_axis_format(ax_top, format_x=True, format_y=True)

        # Middle: Representative cycle (all cycles, mean ± std, early/late means)
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
            early_mean = np.nanmean(all_cycles[:half], axis=0)
            late_mean = np.nanmean(all_cycles[-half:], axis=0)
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
            support_axis.set_ylabel("Support [cycles]", fontsize=9, color="#475569")
            support_axis.tick_params(axis="y", colors="#475569")
        ax_mid.set_title("Representative Cycle (mean ± std)", fontsize=10)
        ax_mid.set_xlabel("Sample within cycle", fontsize=9)
        ax_mid.set_ylabel(result.source_column, fontsize=9)
        ax_mid.grid(True, alpha=0.3)
        if max_cycle_len > 0:
            ax_mid.set_xlim(0, max_cycle_len - 1)
        apply_numeric_axis_format(ax_mid, format_x=True, format_y=True)
        if support_axis is not None:
            apply_numeric_axis_format(support_axis, format_x=False, format_y=True)
        mid_handles, mid_labels = ax_mid.get_legend_handles_labels()
        if support_axis is not None:
            support_handles, support_labels = support_axis.get_legend_handles_labels()
            ax_mid.legend(mid_handles + support_handles, mid_labels + support_labels, fontsize=8, loc="best")
        elif mid_handles:
            ax_mid.legend(mid_handles, mid_labels, fontsize=8, loc="best")

        # Bottom: Cycle-to-cycle statistics (all cycles)
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
            if not self.cycle_metric_toggle_vars[metric_key].get():
                continue
            plot_kwargs = {"label": label, "linewidth": linewidth}
            if color is not None:
                plot_kwargs["color"] = color
            ax_bot.plot(metrics["cycle"], values, **plot_kwargs)
        ax_bot_right = ax_bot.twinx()
        ax_bot_right.clear()
        length_series = metrics["length"]
        right_axis_values = length_series
        right_axis_label = self._get_cycle_length_axis_label(metrics)
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
        ax_bot.set_title("Cycle-to-Cycle Statistics", fontsize=10)
        ax_bot.set_xlabel("Cycle", fontsize=9)
        ax_bot.set_ylabel("Metric", fontsize=9)
        ax_bot_right.set_ylabel(right_axis_label, fontsize=9, color="#b45309", labelpad=12)
        ax_bot_right.yaxis.set_label_position("right")
        ax_bot_right.yaxis.tick_right()
        ax_bot_right.tick_params(axis="y", colors="#b45309")
        ax_bot.grid(True, alpha=0.3)
        left_handles, left_labels = ax_bot.get_legend_handles_labels()
        right_handles, right_labels = ax_bot_right.get_legend_handles_labels()
        ax_bot.legend(left_handles + right_handles, left_labels + right_labels, fontsize=8, loc="best")
        apply_numeric_axis_format(ax_bot, format_x=True, format_y=True)
        apply_numeric_axis_format(ax_bot_right, format_x=False, format_y=True)

        self._cycle_figure.tight_layout()

        # Canvas and toolbar management
        if self._cycle_canvas is None:
            self._cycle_canvas = FigureCanvasTkAgg(self._cycle_figure, master=self.cycle_plot_container)
            self._cycle_toolbar = NavigationToolbar2Tk(self._cycle_canvas, self.cycle_plot_container)
            self._cycle_toolbar.update()
            self._cycle_toolbar.pack(side=tk.TOP, fill=tk.X)
            self._cycle_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
        else:
            self._cycle_canvas.draw()
        self.notebook.select(self.cycles_tab)
        self.plot_notebook.select(self.cycle_plot_tab)

    def _get_cycle_time_column(self) -> str | None:
        preferred_time_column = get_preferred_role_column(self.column_roles, "time", available_columns=list(self.session.working_frame.columns))
        candidate_columns = [
            preferred_time_column or "",
            self.plot_x_var.get().strip(),
            getattr(self.session, "selected_x_column", "").strip(),
        ]
        for column_name in candidate_columns:
            if column_name and column_name != "Index" and column_name in self.session.working_frame.columns:
                return column_name
        return None

    def _get_cycle_length_axis_label(self, metrics_frame: pd.DataFrame) -> str:
        if "duration_seconds" in metrics_frame.columns and metrics_frame["duration_seconds"].notna().any():
            return "Cycle duration [s]"
        return "Cycle length [samples]"

    def _build_cycle_metrics_display_frame(
        self,
        full_result: CycleAnalysisResult,
        kept_cycle_full_indices: list[int],
    ) -> pd.DataFrame:
        display_frame = full_result.metrics_frame.copy()
        kept_index_set = set(kept_cycle_full_indices)
        display_frame.insert(1, "status", ["kept" if index in kept_index_set else "excluded" for index in range(len(display_frame))])
        return display_frame

    def _build_cycle_tree_index_map(
        self,
        tree: ttk.Treeview,
        kept_cycle_full_indices: list[int],
    ) -> dict[str, int]:
        full_to_active_index = {full_index: active_index for active_index, full_index in enumerate(kept_cycle_full_indices)}
        item_to_result_index: dict[str, int] = {}
        for full_index, item_id in enumerate(tree.get_children()):
            if full_index in full_to_active_index:
                item_to_result_index[item_id] = full_to_active_index[full_index]
        return item_to_result_index

    def _get_selected_cycle_indices(self) -> list[int]:
        if self._cycle_metrics_tree is None:
            return []
        selected_items = self._cycle_metrics_tree.selection()
        if not selected_items:
            return []
        selected_indices = [self._cycle_tree_item_to_result_index[item_id] for item_id in selected_items if item_id in self._cycle_tree_item_to_result_index]
        return sorted(set(selected_indices))

    def _build_cycle_tree_full_index_map(self, tree: ttk.Treeview) -> dict[str, int]:
        return {item_id: full_index for full_index, item_id in enumerate(tree.get_children())}

    def _get_selected_cycle_full_indices(self) -> list[int]:
        if self._cycle_metrics_tree is None:
            return []
        selected_items = self._cycle_metrics_tree.selection()
        if not selected_items:
            return []
        selected_full_indices = [self._cycle_tree_item_to_full_index[item_id] for item_id in selected_items if item_id in self._cycle_tree_item_to_full_index]
        return sorted(set(selected_full_indices))

    def _handle_cycle_metrics_selection_changed(self, _event: tk.Event | None = None) -> None:
        if self._latest_cycle_result is not None:
            self._render_cycle_plot(self._latest_cycle_result)

    def _handle_cycle_metric_toggle_changed(self, *_args: object) -> None:
        if self._latest_cycle_result is not None:
            self._render_cycle_plot(self._latest_cycle_result)

    def _select_all_cycles(self) -> None:
        if self._cycle_metrics_tree is None:
            return
        item_ids = self._cycle_metrics_tree.get_children()
        self._cycle_metrics_tree.selection_set(item_ids)
        if self._latest_cycle_result is not None:
            self._render_cycle_plot(self._latest_cycle_result)

    def _clear_selected_cycles(self) -> None:
        if self._cycle_metrics_tree is None:
            return
        self._cycle_metrics_tree.selection_remove(self._cycle_metrics_tree.selection())
        if self._latest_cycle_result is not None:
            self._render_cycle_plot(self._latest_cycle_result)

    def _exclude_selected_cycles(self) -> None:
        if self._cycle_metrics_tree is None or self._latest_cycle_result is None or self._full_cycle_result is None:
            return

        selected_indices = self._get_selected_cycle_indices()
        if not selected_indices:
            messagebox.showwarning("Warning", "Select at least one kept cycle to exclude")
            return

        selected_index_set = set(selected_indices)
        kept_full_indices = [
            full_index
            for active_index, full_index in enumerate(self._kept_cycle_full_indices)
            if active_index not in selected_index_set
        ]
        if not kept_full_indices:
            messagebox.showwarning("Warning", "At least one cycle must remain after exclusion")
            return

        try:
            updated_result = rebuild_cycle_analysis_result(
                self.session.working_frame,
                self._full_cycle_result,
                kept_full_indices,
            )
        except Exception as error:
            messagebox.showerror("Cycle Analysis Error", str(error))
            return

        self._render_cycle_result(
            updated_result,
            full_result=self._full_cycle_result,
            kept_cycle_full_indices=kept_full_indices,
        )

    def _restore_all_cycles(self) -> None:
        if self._full_cycle_result is None:
            return
        self._render_cycle_result(
            self._full_cycle_result,
            full_result=self._full_cycle_result,
            kept_cycle_full_indices=list(range(self._full_cycle_result.cycle_count)),
        )

    def _restore_selected_cycles(self) -> None:
        if self._full_cycle_result is None or self._latest_cycle_result is None:
            return

        selected_full_indices = self._get_selected_cycle_full_indices()
        if not selected_full_indices:
            messagebox.showwarning("Warning", "Select at least one excluded cycle to restore")
            return

        kept_full_index_set = set(self._kept_cycle_full_indices)
        excluded_selected_indices = [full_index for full_index in selected_full_indices if full_index not in kept_full_index_set]
        if not excluded_selected_indices:
            messagebox.showwarning("Warning", "Select at least one excluded cycle to restore")
            return

        kept_full_indices = sorted(kept_full_index_set.union(excluded_selected_indices))
        try:
            updated_result = rebuild_cycle_analysis_result(
                self.session.working_frame,
                self._full_cycle_result,
                kept_full_indices,
            )
        except Exception as error:
            messagebox.showerror("Cycle Analysis Error", str(error))
            return

        self._render_cycle_result(
            updated_result,
            full_result=self._full_cycle_result,
            kept_cycle_full_indices=kept_full_indices,
        )

    def _apply_kept_cycles_to_working_data(self) -> None:
        if self._latest_cycle_result is None:
            messagebox.showwarning("Warning", "Run cycle analysis before applying kept cycles")
            return

        try:
            kept_frame = keep_dataframe_index_ranges(self.session.working_frame, self._latest_cycle_result.cycle_ranges)
        except Exception as error:
            messagebox.showerror("Cycle Analysis Error", str(error))
            return

        should_apply = messagebox.askyesno(
            "Apply Kept Cycles",
            (
                f"Replace the working dataframe with the currently kept cycles?\n\n"
                f"Kept cycles: {self._latest_cycle_result.cycle_count}\n"
                f"Rows retained: {len(kept_frame)}\n\n"
                f"Excluded cycles and non-cycle rows will be removed from the working data."
            ),
        )
        if not should_apply:
            return

        self._replace_working_frame(
            kept_frame,
            history_entry=(
                f"Applied kept cycles to working data: "
                f"{self._latest_cycle_result.cycle_count} cycles, {len(kept_frame)} rows retained"
            ),
            focus_column=self._latest_cycle_result.source_column,
        )

    def _clear_cycle_results(self, message: str | None = None) -> None:
        if self._cycle_figure is not None:
            plt.close(self._cycle_figure)
            self._cycle_figure = None
        self._cycle_canvas = None
        self._cycle_toolbar = None
        self._cycle_metrics_tree = None
        self._cycle_tree_item_to_result_index = {}
        self._cycle_tree_item_to_full_index = {}
        self._kept_cycle_full_indices = []
        self._full_cycle_result = None
        self._latest_cycle_result = None
        for container in (self.cycle_plot_container, self.cycle_metrics_container):
            for widget in container.winfo_children():
                widget.destroy()
        if message:
            ttk.Label(self.cycle_metrics_container, text=message, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)
            ttk.Label(self.cycle_plot_container, text=message, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)

    def _reset_working_data(self) -> None:
        update = build_reset_update(self.session.original_frame)
        self._replace_working_frame(update.dataframe, update.history_entry)

    def _export_current_view(self) -> None:
        save_path = filedialog.asksaveasfilename(
            title="Export current view",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not save_path:
            return

        self.session.working_frame.to_csv(save_path, sep=";", index=False)
        self.notifications.success(f"Exported to {os.path.basename(save_path)}")
        messagebox.showinfo("Exported", f"Saved current view to:\n{save_path}")

    def open_documentation(self, relative_path: str) -> None:
        try:
            open_documentation_path(relative_path)
        except Exception as error:
            messagebox.showerror("Documentation Error", str(error))

    def _replace_working_frame(
        self,
        dataframe: pd.DataFrame,
        history_entry: str,
        role_overrides: dict[str, str] | None = None,
        focus_column: str | None = None,
    ) -> None:
        self.session.working_frame = dataframe.copy()
        self.column_roles = update_projected_column_roles(self.column_roles, self.session.working_frame, role_overrides)
        self.session.working_revision += 1
        self.session.last_summary = None
        self.notifications.success(history_entry)
        self.fft_summary_var.set(self._default_frequency_summary_text())
        self._clear_fft_results("Recompute the frequency analysis after data changes.")
        self.cycle_summary_var.set("Analyze equal-length cycles for the active column.")
        self._clear_cycle_results("Recompute cycle analysis after data changes.")
        if focus_column and focus_column in self.session.working_frame.columns:
            # Set focus column before refresh so a single _refresh_all_views call uses it;
            # suppress the trace-driven handler to avoid a redundant second refresh pass.
            self._frame_replacing = True
            self.filter_output_name_var.set("")
            self.signal_filter_name_var.set("")
            self.derived_name_var.set("")
            self.active_column_var.set(focus_column)
            self._frame_replacing = False
        self._refresh_all_views()
        self._set_default_output_names()
        self._refresh_role_widget_styles()

    def _set_default_output_names(self) -> None:
        set_default_output_names(self)

    def _handle_active_column_changed(self, *_args: object) -> None:
        if self._frame_replacing:
            return
        self.filter_output_name_var.set("")
        self.signal_filter_name_var.set("")
        self.derived_name_var.set("")
        self.fft_summary_var.set(self._default_frequency_summary_text())
        self._clear_fft_results("Compute the frequency analysis for the currently active column.")
        self.cycle_summary_var.set("Analyze equal-length cycles for the active column.")
        self._clear_cycle_results("Compute cycle analysis for the currently active column.")
        refresh_filter_controls(self)
        refresh_plot_controls(self)
        self._set_default_output_names()
        self._refresh_frequency_expectation()
        self._refresh_role_widget_styles()

    def _handle_frequency_expectation_changed(self, *_args: object) -> None:
        if self._refreshing_frequency_controls:
            return
        self._refreshing_frequency_controls = True
        try:
            self.fft_summary_var.set(self._default_frequency_summary_text())
            self._refresh_frequency_method_controls()
            self._refresh_frequency_expectation()
            self._refresh_role_widget_styles()
        finally:
            self._refreshing_frequency_controls = False

    def _handle_output_defaults_changed(self, *_args: object) -> None:
        self._set_default_output_names()

    def _handle_role_widget_selection_changed(self, *_args: object) -> None:
        self._refresh_role_widget_styles()

    def _refresh_role_widget_styles(self) -> None:
        refresh_role_widget_styles(self)
        self._refresh_active_column_badges()

    def _refresh_frequency_method_controls(self) -> None:
        analysis_name = self.frequency_analysis_var.get().strip() or UI_FREQUENCY_ANALYSIS_METHODS[0]
        uses_comparison = analysis_name in {"Transfer Estimate", "Coherence"}
        uses_welch_specific = analysis_name in {"Welch PSD", "Transfer Estimate", "Coherence"}

        # Show/hide comparison frame
        if hasattr(self, "comparison_frame") and self.comparison_frame is not None:
            if uses_comparison:
                self.comparison_frame.grid()
                self.frequency_compare_combo.state(["!disabled"])
            else:
                self.comparison_frame.grid_remove()
                self.frequency_compare_combo.state(["disabled"])

        # Show general frequency options for all methods
        if hasattr(self, "freq_general_frame") and self.freq_general_frame is not None:
            self.freq_general_frame.grid()

        # Show Welch-specific options only for Welch/Transfer/Coherence
        if hasattr(self, "welch_specific_frame") and self.welch_specific_frame is not None:
            if uses_welch_specific:
                self.welch_specific_frame.grid()
            else:
                self.welch_specific_frame.grid_remove()

    def _default_frequency_summary_text(self) -> str:
        analysis_name = self.frequency_analysis_var.get().strip() or UI_FREQUENCY_ANALYSIS_METHODS[0]
        if analysis_name == "Welch PSD":
            return "Ready to estimate a power spectral density for the selected signal."
        return "Ready to inspect the dominant frequencies in the selected signal."

    def _refresh_active_column_badges(self) -> None:
        active_column = self.active_column_var.get().strip()
        role_name = get_column_role(self.column_roles, active_column) if active_column else "metadata"
        background, foreground = get_column_role_cell_colors(role_name)
        for label_name in (
            "filter_active_column_label",
            "signal_filter_active_column_label",
            "derived_active_column_label",
            "frequency_active_column_label",
            "cycles_active_column_label",
        ):
            label = getattr(self, label_name, None)
            if label is not None:
                label.configure(bg=background, fg=foreground)

    def _set_plot_y_column_options(self, numeric_columns: list[str], selected_columns: list[str]) -> None:
        if self.plot_y_selector_menu is None or self.plot_y_selector_button is None:
            return

        self.plot_y_selection_vars = {}
        self.plot_y_selector_menu.delete(0, tk.END)
        if not numeric_columns:
            self._clear_plot_y_column_selector()
            return

        self.plot_y_selector_menu.add_command(label="Select all", command=self._select_all_plot_y_columns)
        self.plot_y_selector_menu.add_command(label="Clear selection", command=self._clear_selected_plot_y_columns)
        self.plot_y_selector_menu.add_separator()

        self._plot_y_selector_sync_in_progress = True
        for column_name in numeric_columns:
            variable = tk.BooleanVar(value=column_name in selected_columns)
            variable.trace_add("write", self._handle_plot_y_column_selector_changed)
            self.plot_y_selection_vars[column_name] = variable
            background, foreground = self._get_plot_y_selector_colors(column_name)
            self.plot_y_selector_menu.add_checkbutton(
                label=column_name,
                variable=variable,
                onvalue=True,
                offvalue=False,
                background=background,
                foreground=foreground,
                activebackground=background,
                activeforeground=foreground,
                selectcolor=background,
            )
        self._plot_y_selector_sync_in_progress = False
        self.plot_y_selector_button.state(["!disabled"])
        self._update_plot_y_column_summary()

    def _clear_plot_y_column_selector(self) -> None:
        self.plot_y_selection_vars = {}
        if self.plot_y_selector_menu is not None:
            self.plot_y_selector_menu.delete(0, tk.END)
        if self.plot_y_selector_button is not None:
            self.plot_y_selector_button.state(["disabled"])
        self.plot_y_selection_summary_var.set("No numeric channels available")

    def _handle_plot_y_column_selector_changed(self, *_args: object) -> None:
        self._update_plot_y_column_summary()
        if not self._plot_y_selector_sync_in_progress:
            self.session.selected_y_columns = self._get_selected_plot_y_columns()

    def _update_plot_y_column_summary(self) -> None:
        selected_columns = self._get_selected_plot_y_columns()
        if not self.plot_y_selection_vars:
            self.plot_y_selection_summary_var.set("No numeric channels available")
            return
        if not selected_columns:
            self.plot_y_selection_summary_var.set("Choose channels")
            return
        if len(selected_columns) <= 2:
            self.plot_y_selection_summary_var.set(", ".join(selected_columns))
            return
        shown_columns = ", ".join(selected_columns[:2])
        self.plot_y_selection_summary_var.set(f"{len(selected_columns)} selected: {shown_columns}, +{len(selected_columns) - 2}")

    def _select_all_plot_y_columns(self) -> None:
        self._plot_y_selector_sync_in_progress = True
        for variable in self.plot_y_selection_vars.values():
            variable.set(True)
        self._plot_y_selector_sync_in_progress = False
        self.session.selected_y_columns = self._get_selected_plot_y_columns()
        self._update_plot_y_column_summary()

    def _clear_selected_plot_y_columns(self) -> None:
        self._plot_y_selector_sync_in_progress = True
        for variable in self.plot_y_selection_vars.values():
            variable.set(False)
        self._plot_y_selector_sync_in_progress = False
        self.session.selected_y_columns = self._get_selected_plot_y_columns()
        self._update_plot_y_column_summary()

    def _get_selected_plot_y_columns(self) -> list[str]:
        return [column for column, variable in self.plot_y_selection_vars.items() if variable.get()]

    def _get_plot_y_selector_colors(self, column_name: str) -> tuple[str, str]:
        return get_column_role_cell_colors(self.column_roles.get(column_name, "metadata"))

    def _refresh_frequency_expectation(self) -> None:
        active_column = self.active_column_var.get().strip()
        if not active_column:
            self.frequency_expectation_var.set("Select a signal to see built-in hints for demo datasets.")
            return
        self.frequency_expectation_var.set(
            describe_demo_frequency_expectations(
                self.session.working_frame,
                active_column,
                self.frequency_analysis_var.get(),
                self.frequency_compare_var.get(),
            )
        )

    @staticmethod
    def _build_frequency_summary(result: FrequencySpectrumResult) -> str:
        summary_parts = [
            f"n={result.sample_count}",
            f"dt={format_display_number(result.sample_spacing)} s",
            f"fs={format_display_number(result.sampling_frequency)} Hz",
            f"f_nyq={format_display_number(result.nyquist_frequency)} Hz",
            f"dominant={format_display_number(result.dominant_frequency)} Hz",
            f"{result.value_column_label.lower()}={format_display_number(result.dominant_amplitude)}",
            result.spacing_source_text,
        ]
        if result.comparison_column:
            summary_parts.append(f"vs={result.comparison_column}")
        if result.uniformity_ratio > 0.05:
            summary_parts.append(f"nonuniformity~{format_display_percent(result.uniformity_ratio)}")
        if result.dominant_frequency > 0.8 * result.nyquist_frequency:
            summary_parts.append("\u26a0 dominant peak near Nyquist")
        return " | ".join(summary_parts)
