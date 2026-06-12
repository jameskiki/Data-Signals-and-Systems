"""Interactive analysis workspace for exploring a loaded dataframe."""

import os
from collections.abc import Callable

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from Source.shared.documentation_links import open_documentation_path
from Source.shared.notifications import NotificationManager
from .actions import (
    build_reset_update,
)
from .handlers import (
    apply_derived_signal,
    apply_filter,
    apply_resample,
    apply_signal_filter,
    compute_cycle_analysis,
    compute_fft,
)
from .layout import build_analysis_workspace_ui
from .rules_orchestrator import (
    apply_cycle_method_rule,
    apply_frequency_method_rule,
    apply_signal_filter_rule,
)
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
from .views import render_correlation_view, render_dataframe_preview, render_statistics_tree
from Source.data_ops.cycles import (
    CycleAnalysisResult,
    rebuild_cycle_analysis_result,
)
from Source.shared.display_format import format_display_number, format_display_percent
from Source.shared.column_roles import (
    apply_literal_role_combobox_style,
    get_column_role,
    get_column_role_cell_colors,
    summarize_column_roles,
    update_projected_column_roles,
)
from Source.shared.base_app_shell import BaseAppShell
from Source.shared.demo_catalog import describe_demo_frequency_expectations

from Source.data_ops.filtering import resolve_filtered_column_name
from Source.data_ops.frame_ops import keep_dataframe_index_ranges, resample_to_uniform
from Source.data_ops.models import SIGNAL_FILTER_OPERATIONS
from Source.data_ops.spectral import FrequencySpectrumResult, SpectrogramResult
from Source.data_ops.summary import summarize_dataframe
from Source.shared.plot_options import PlotOptions, PlotStyle
from . import plotting as plotting_ops


class AnalysisWorkspace(BaseAppShell):
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
        self.signal_filter_cutoff_high_var = tk.StringVar(value="20.0")
        self.signal_filter_order_var = tk.StringVar(value="4")
        self.signal_filter_spacing_var = tk.StringVar(value="0.0")
        self.signal_filter_spacing_status_var = tk.StringVar(value="User-set")

        self.resample_time_var = tk.StringVar(value="Index")
        self.resample_spacing_var = tk.StringVar(value="1.0")
        self.resample_spacing_status_var = tk.StringVar(value="User-set")

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
        self.fft_sample_spacing_status_var = tk.StringVar(value="User-set")
        self.fft_window_var = tk.StringVar(value=FFT_WINDOW_OPTIONS[0])
        self.fft_detrend_var = tk.BooleanVar(value=True)
        self.welch_segment_length_var = tk.StringVar(value="256")
        self.welch_segment_length_status_var = tk.StringVar(value="User-set")
        self.welch_overlap_fraction_var = tk.StringVar(value="0.5")
        self.fft_summary_var = tk.StringVar(value=self._default_frequency_summary_text())
        self.frequency_expectation_var = tk.StringVar(value="Select a signal to see built-in hints for demo datasets.")
        self.cycle_length_var = tk.StringVar(value="100")
        self.cycle_mode_var = tk.StringVar(value="fixed_length")
        self.cycle_reference_var = tk.StringVar(value="Index")
        self.cycle_threshold_var = tk.StringVar(value="0.0")
        self.cycle_max_cycles_var = tk.StringVar(value="")
        self.cycle_prominence_var = tk.StringVar(value="0.0")
        self.cycle_length_status_var = tk.StringVar(value="User-set")
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
        self._applying_inferred_defaults = False
        self._inferred_fields: set[str] = set()
        self._user_edited_fields: set[str] = set()

        build_analysis_workspace_ui(self)
        self.active_column_var.trace_add("write", self._handle_active_column_changed)
        self._bind_write(self._handle_frequency_expectation_changed,
                         self.frequency_analysis_var, self.frequency_compare_var)
        self._bind_write(self._handle_role_widget_selection_changed,
                         self.plot_x_var, self.derived_reference_var,
                         self.fft_reference_var, self.cycle_reference_var)
        self._bind_write(self._handle_output_defaults_changed,
                         self.signal_filter_operation_var, self.derived_operation_var)
        self.cycle_mode_var.trace_add("write", lambda *_: self._refresh_cycle_method_controls())
        self.signal_filter_operation_var.trace_add("write", lambda *_: self._refresh_signal_filter_controls())
        self._bind_inferred_field_traces()
        for metric_toggle_var in self.cycle_metric_toggle_vars.values():
            metric_toggle_var.trace_add("write", self._handle_cycle_metric_toggle_changed)
        self._refresh_all_views()
        self._refresh_cycle_method_controls()
        self._refresh_signal_filter_controls()
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
        apply_cycle_method_rule(self)

    def _refresh_signal_filter_controls(self) -> None:
        apply_signal_filter_rule(self)

    def _ensure_current_summary(self) -> None:
        if self.session.last_summary is not None and self.session.last_summary_revision == self.session.working_revision:
            return
        self.session.last_summary = summarize_dataframe(self.session.working_frame)
        self.session.last_summary_revision = self.session.working_revision

    def _refresh_all_views(self, refresh_summary: bool = True) -> None:
        if refresh_summary:
            self._ensure_current_summary()
        self._refresh_summary_widgets()
        self._refresh_preview()
        refresh_filter_controls(self)
        refresh_plot_controls(self)
        self._refresh_frequency_expectation()
        self._refresh_frequency_method_controls()
        self._refresh_cycle_method_controls()
        self._refresh_signal_filter_controls()

    def _refresh_summary_widgets(self) -> None:
        """Refresh sidebar labels, overview text, and statistics trees from the current session state.

        Does not recompute the summary — call ``_ensure_current_summary`` first if needed.
        Both ``_refresh_all_views`` and ``_refresh_summary_views`` delegate here so that
        adding a new summary panel only requires one change in this method.
        """
        refresh_sidebar(self)
        refresh_overview(self)
        self._refresh_statistics()

    def _refresh_summary_views(self) -> None:
        self._ensure_current_summary()
        self._refresh_summary_widgets()

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
        return plotting_ops.refresh_live_plot(self)

    def _apply_filter(self) -> None:
        return apply_filter(self)

    def _apply_signal_filter(self) -> None:
        return apply_signal_filter(self)

    def _apply_resample(self) -> None:
        return apply_resample(self)

    def _apply_derived_signal(self) -> None:
        return apply_derived_signal(self)

    def _compute_fft(self) -> None:
        return compute_fft(self)

    def _compute_cycle_analysis(self) -> None:
        return compute_cycle_analysis(self)

    def _update_plot(self) -> None:
        return plotting_ops.update_plot(self)

    def _build_time_series_plot_options(
        self,
        selected_columns: list[str],
        x_column: str,
        use_subplots: bool,
    ) -> PlotOptions:
        return plotting_ops.build_time_series_plot_options(selected_columns, x_column, use_subplots)

    def _get_default_plot_style(self) -> PlotStyle:
        return plotting_ops.get_default_plot_style()

    def _render_plot_figure(self, figure: plt.Figure) -> None:
        return plotting_ops.render_plot_figure(self, figure)

    def _clear_plot_container(self) -> None:
        return plotting_ops.clear_plot_container(self)

    def _render_fft_result(self, result: FrequencySpectrumResult) -> None:
        return plotting_ops.render_fft_result(self, result)

    def _clear_fft_results(self, message: str | None = None) -> None:
        return plotting_ops.clear_fft_results(self, message)

    def _render_spectrogram_result(self, result: SpectrogramResult) -> None:
        return plotting_ops.render_spectrogram_result(self, result)

    def _render_frequency_figure(self, figure: plt.Figure) -> None:
        return plotting_ops.render_frequency_figure(self, figure)

    def _render_cycle_result(
        self,
        result: CycleAnalysisResult,
        full_result: CycleAnalysisResult | None = None,
        kept_cycle_full_indices: list[int] | None = None,
    ) -> None:
        return plotting_ops.render_cycle_result(self, result, full_result, kept_cycle_full_indices)

    def _render_cycle_plot(self, result: CycleAnalysisResult) -> None:
        return plotting_ops.render_cycle_plot(self, result)

    def _get_cycle_time_column(self) -> str | None:
        return plotting_ops.get_cycle_time_column(self)

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
            self.notifications.warning("Select at least one kept cycle to exclude")
            return

        selected_index_set = set(selected_indices)
        kept_full_indices = [
            full_index
            for active_index, full_index in enumerate(self._kept_cycle_full_indices)
            if active_index not in selected_index_set
        ]
        if not kept_full_indices:
            self.notifications.warning("At least one cycle must remain after exclusion")
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
            self.notifications.warning("Select at least one excluded cycle to restore")
            return

        kept_full_index_set = set(self._kept_cycle_full_indices)
        excluded_selected_indices = [full_index for full_index in selected_full_indices if full_index not in kept_full_index_set]
        if not excluded_selected_indices:
            self.notifications.warning("Select at least one excluded cycle to restore")
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
            self.notifications.warning("Run cycle analysis before applying kept cycles")
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
            focus_column=self._latest_cycle_result.source_column,
        )
        self.notifications.success(
            f"Applied kept cycles: {self._latest_cycle_result.cycle_count} cycles, {len(kept_frame)} rows retained"
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
        self._replace_working_frame(update.dataframe)
        self.notifications.success("Reset working dataframe to the original loaded state")

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

    def open_documentation(self, relative_path: str) -> None:
        try:
            open_documentation_path(relative_path)
        except Exception as error:
            messagebox.showerror("Documentation Error", str(error))

    def _replace_working_frame(
        self,
        dataframe: pd.DataFrame,
        role_overrides: dict[str, str] | None = None,
        focus_column: str | None = None,
    ) -> None:
        self.session.working_frame = dataframe.copy()
        self.column_roles = update_projected_column_roles(self.column_roles, self.session.working_frame, role_overrides)
        self.session.working_revision += 1
        self.session.last_summary = None
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

    def _bind_inferred_field_traces(self) -> None:
        field_to_var = {
            "signal_filter_spacing": self.signal_filter_spacing_var,
            "fft_sample_spacing": self.fft_sample_spacing_var,
            "resample_spacing": self.resample_spacing_var,
            "welch_segment_length": self.welch_segment_length_var,
            "cycle_length": self.cycle_length_var,
        }
        for field_name, variable in field_to_var.items():
            variable.trace_add("write", lambda *_args, name=field_name: self._handle_inferred_field_edited(name))

    def _handle_inferred_field_edited(self, field_name: str) -> None:
        if self._applying_inferred_defaults:
            return
        self._inferred_fields.discard(field_name)
        self._user_edited_fields.add(field_name)
        self._refresh_inferred_badges()

    def _set_inferred_field_value(self, field_name: str, variable: tk.StringVar, value: str) -> None:
        current_value = variable.get()
        if current_value == value and field_name in self._inferred_fields:
            return
        self._applying_inferred_defaults = True
        try:
            variable.set(value)
        finally:
            self._applying_inferred_defaults = False
        self._inferred_fields.add(field_name)
        self._refresh_inferred_badges()

    def _refresh_inferred_badges(self) -> None:
        self.signal_filter_spacing_status_var.set("Inferred" if "signal_filter_spacing" in self._inferred_fields else "User-set")
        self.fft_sample_spacing_status_var.set("Inferred" if "fft_sample_spacing" in self._inferred_fields else "User-set")
        self.resample_spacing_status_var.set("Inferred" if "resample_spacing" in self._inferred_fields else "User-set")
        self.welch_segment_length_status_var.set("Inferred" if "welch_segment_length" in self._inferred_fields else "User-set")
        self.cycle_length_status_var.set("Inferred" if "cycle_length" in self._inferred_fields else "User-set")

    def _handle_role_widget_selection_changed(self, *_args: object) -> None:
        self._refresh_role_widget_styles()

    def _refresh_role_widget_styles(self) -> None:
        refresh_role_widget_styles(self)
        self._refresh_active_column_badges()

    def _refresh_frequency_method_controls(self) -> None:
        apply_frequency_method_rule(self)

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
