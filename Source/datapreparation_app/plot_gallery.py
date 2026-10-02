"""Interactive gallery for production plot controls and renderers."""

from __future__ import annotations

from dataclasses import dataclass, replace
import tkinter as tk
from tkinter import ttk
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from Source.data_ops.cycles import (
    compute_cycle_analysis_from_ranges,
    compute_fixed_length_cycle_analysis,
    detect_peak_cycle_ranges,
    detect_rising_edge_cycle_ranges,
    detect_zero_crossing_cycle_ranges,
)
from Source.data_ops.models import SIGNAL_FILTER_OPERATIONS
from Source.data_ops.signals import apply_signal_filter, compute_butterworth_response
from Source.data_ops.spectral import (
    FrequencySpectrumResult,
    SpectrogramResult,
    compute_coherence_spectrum,
    compute_fft_spectrum,
    compute_residual_spectrum,
    compute_spectrogram,
    compute_transfer_estimate,
    compute_welch_psd,
)
from Source.datapreparation_app.comparison import (
    add_overlay_deviation_highlights,
    build_comparison_display_frames,
    build_difference_figure,
    calculate_subplot_grid,
)
from Source.shared.demo_catalog import (
    COMPARISON_DEMO_SPECS,
    CYCLE_VALIDATION_DEMO,
    DemoDatasetSpec,
    INPUT_OUTPUT_DEMO,
    SPECTRAL_REFERENCE_DEMO,
    create_demo_dataset,
)
from Source.shared.plot_controls import build_time_series_plot_controls
from Source.shared.plot_options import (
    DeviationPanelPlotData,
    DeviationSeriesPlotData,
    FrequencySeriesPlotData,
    MagnitudePhasePlotData,
    PlotDescriptor,
    PlotOptions,
    PlotStyle,
    ResidualSpectrumPlotData,
    SignalComparisonPlotData,
)
from Source.shared.plot_preparation import (
    prepare_cycle_plot_data,
    prepare_frequency_plot_values,
    prepare_spectrogram_plot_data,
)
from Source.shared.plot_utils import (
    create_cycle_figure,
    create_frequency_series_figure,
    create_magnitude_phase_figure,
    create_plot_figure,
    create_residual_spectrum_figure,
    create_signal_comparison_figure,
    create_spectrogram_figure,
)
from Source.shared.presentation_shell import PresentationShellMixin


@dataclass(frozen=True)
class PlotGalleryExamples:
    """Existing demo datasets and their normally computed analysis results."""

    spectral_spec: DemoDatasetSpec
    spectral_frame: pd.DataFrame
    input_output_spec: DemoDatasetSpec
    input_output_frame: pd.DataFrame
    cycle_spec: DemoDatasetSpec
    cycle_frame: pd.DataFrame
    transfer_result: FrequencySpectrumResult
    spectrogram_result: SpectrogramResult
    filtered_frame: pd.DataFrame
    comparison_specs: tuple[DemoDatasetSpec, ...]
    comparison_frames: dict[str, pd.DataFrame]


def build_plot_gallery_examples() -> PlotGalleryExamples:
    """Build gallery inputs from the application's existing demo datasets."""

    spectral_spec, spectral_frame = create_demo_dataset(SPECTRAL_REFERENCE_DEMO.key)
    input_output_spec, input_output_frame = create_demo_dataset(INPUT_OUTPUT_DEMO.key)
    cycle_spec, cycle_frame = create_demo_dataset(CYCLE_VALIDATION_DEMO.key)
    comparison_frames = {
        spec.basename: create_demo_dataset(spec.key)[1]
        for spec in COMPARISON_DEMO_SPECS
    }
    transfer_result = compute_transfer_estimate(
        input_output_frame,
        source_column="system_output",
        comparison_column="actuator_input",
        reference_column="time_s",
        segment_length=1024,
    )
    spectrogram_result = compute_spectrogram(
        spectral_frame,
        source_column="measured_signal",
        reference_column="time_s",
        segment_length=512,
    )
    filtered_frame = apply_signal_filter(
        spectral_frame,
        source_column="measured_signal",
        operation="butterworth_lowpass",
        new_column="filtered_signal",
        cutoff_hz=20.0,
        sample_spacing=0.002,
        filter_order=4,
    )
    return PlotGalleryExamples(
        spectral_spec=spectral_spec,
        spectral_frame=spectral_frame,
        input_output_spec=input_output_spec,
        input_output_frame=input_output_frame,
        cycle_spec=cycle_spec,
        cycle_frame=cycle_frame,
        transfer_result=transfer_result,
        spectrogram_result=spectrogram_result,
        filtered_frame=filtered_frame,
        comparison_specs=COMPARISON_DEMO_SPECS,
        comparison_frames=comparison_frames,
    )


class PlotGallery(PresentationShellMixin):
    """Show deterministic examples through the production plot components."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        style: PlotStyle | None = None,
        on_close: Callable[["PlotGallery"], object] | None = None,
    ) -> None:
        self.parent = parent
        self.style = style or PlotStyle()
        self.on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title("Plot Gallery")
        self.window.geometry("1050x760")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._time_figure = None
        self._time_canvas = None
        self._time_toolbar = None
        self._magnitude_phase_figure = None
        self._magnitude_phase_canvas = None
        self._magnitude_phase_toolbar = None
        self._frequency_spectrum_figure = None
        self._frequency_spectrum_canvas = None
        self._frequency_spectrum_toolbar = None
        self._spectrogram_figure = None
        self._spectrogram_canvas = None
        self._spectrogram_toolbar = None
        self._comparison_figure = None
        self._comparison_canvas = None
        self._comparison_toolbar = None
        self._dataset_comparison_figure = None
        self._dataset_comparison_canvas = None
        self._dataset_comparison_toolbar = None
        self._cycle_figure = None
        self._cycle_canvas = None
        self._cycle_toolbar = None

        self.examples = build_plot_gallery_examples()
        self._time_frame = self.examples.spectral_frame
        self.time_x_var = tk.StringVar(value="time_s")
        self.time_y_summary_var = tk.StringVar(value="2 channels selected")
        self.time_subplots_var = tk.BooleanVar(value=False)
        self._time_y_vars = {
            column: tk.BooleanVar(value=True)
            for column in ("clean_signal", "measured_signal")
        }
        self.magnitude_phase_example_var = tk.StringVar(value="Transfer Estimate")
        self.spectrum_method_var = tk.StringVar(value="FFT Amplitude")
        self.spectrum_source_var = tk.StringVar(value="measured_signal")
        self.spectrum_comparison_var = tk.StringVar(value="clean_signal")
        self.spectrum_reference_var = tk.StringVar(value="time_s")
        self.spectrum_spacing_var = tk.StringVar(value="0.002")
        self.spectrum_window_var = tk.StringVar(value="hann")
        self.spectrum_detrend_var = tk.BooleanVar(value=True)
        self.spectrum_segment_var = tk.StringVar(value="512")
        self.spectrum_overlap_var = tk.StringVar(value="0.5")
        self.wrapped_phase_var = tk.BooleanVar(value=True)
        self.frequency_source_var = tk.StringVar(value="system_output")
        self.frequency_comparison_var = tk.StringVar(value="actuator_input")
        self.frequency_reference_var = tk.StringVar(value="time_s")
        self.frequency_spacing_var = tk.StringVar(value="0.002")
        self.frequency_detrend_var = tk.BooleanVar(value=True)
        self.frequency_window_var = tk.StringVar(value="hann")
        self.frequency_segment_var = tk.StringVar(value="1024")
        self.frequency_overlap_var = tk.StringVar(value="0.5")
        self.bode_operation_var = tk.StringVar(value="butterworth_lowpass")
        self.bode_cutoff_var = tk.StringVar(value="20.0")
        self.bode_cutoff_high_var = tk.StringVar(value="45.0")
        self.bode_order_var = tk.StringVar(value="4")
        self.bode_spacing_var = tk.StringVar(value="0.002")
        self.spectrogram_source_var = tk.StringVar(value="measured_signal")
        self.spectrogram_reference_var = tk.StringVar(value="time_s")
        self.spectrogram_spacing_var = tk.StringVar(value="0.002")
        self.spectrogram_window_var = tk.StringVar(value="hann")
        self.spectrogram_segment_var = tk.StringVar(value="512")
        self.spectrogram_overlap_var = tk.StringVar(value="0.5")
        self.spectrogram_detrend_var = tk.BooleanVar(value=True)
        self.filter_source_var = tk.StringVar(value="measured_signal")
        self.signal_comparison_mode_var = tk.StringVar(value="Original vs filtered")
        self.filter_operation_var = tk.StringVar(value="butterworth_lowpass")
        self.filter_window_var = tk.StringVar(value="21")
        self.filter_alpha_var = tk.StringVar(value="0.2")
        self.filter_cutoff_var = tk.StringVar(value="20.0")
        self.filter_cutoff_high_var = tk.StringVar(value="45.0")
        self.filter_order_var = tk.StringVar(value="4")
        self.filter_spacing_var = tk.StringVar(value="0.002")
        self.cycle_mode_var = tk.StringVar(value="rising_edge")
        self.cycle_source_var = tk.StringVar(value="cycle_process")
        self.cycle_reference_var = tk.StringVar(value="trigger_pulse")
        self.cycle_length_var = tk.StringVar(value="100")
        self.cycle_threshold_var = tk.StringVar(value="0.5")
        self.cycle_prominence_var = tk.StringVar(value="0.2")
        self.cycle_max_var = tk.StringVar(value="20")
        self.gallery_status_var = tk.StringVar(value="")
        self.cycle_metric_vars = {
            key: tk.BooleanVar(value=True)
            for key in ("mean", "rms", "peak_to_peak", "min", "max")
        }
        self.dataset_comparison_mode_var = tk.StringVar(value="Overlay")
        self.dataset_comparison_baseline_var = tk.StringVar(value=COMPARISON_DEMO_SPECS[0].basename)
        self.dataset_comparison_x_var = tk.StringVar(value="time_s")
        self.dataset_comparison_column_vars = {
            column: tk.BooleanVar(value=column == "measurement")
            for column in ("measurement", "reference_signal", "residual")
        }
        self.dataset_comparison_visibility_vars = {
            spec.basename: tk.BooleanVar(value=True)
            for spec in self.examples.comparison_specs
        }
        self.dataset_comparison_normalize_var = tk.BooleanVar(value=False)
        self.dataset_comparison_zero_start_var = tk.BooleanVar(value=False)
        self.dataset_comparison_trim_overlap_var = tk.BooleanVar(value=False)
        self.dataset_comparison_subplots_var = tk.BooleanVar(value=False)
        self.dataset_comparison_highlight_var = tk.BooleanVar(value=False)
        self.dataset_comparison_show_legend_var = tk.BooleanVar(value=self.style.show_legend)

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        time_tab = ttk.Frame(notebook)
        magnitude_phase_tab = ttk.Frame(notebook)
        frequency_spectrum_tab = ttk.Frame(notebook)
        spectrogram_tab = ttk.Frame(notebook)
        comparison_tab = ttk.Frame(notebook)
        dataset_comparison_tab = ttk.Frame(notebook)
        cycle_tab = ttk.Frame(notebook)
        notebook.add(time_tab, text="Time Series")
        notebook.add(magnitude_phase_tab, text="Magnitude + Phase")
        notebook.add(frequency_spectrum_tab, text="Frequency Spectrum")
        notebook.add(spectrogram_tab, text="Spectrogram")
        notebook.add(comparison_tab, text="Signal Comparison")
        notebook.add(dataset_comparison_tab, text="Dataset Comparison")
        notebook.add(cycle_tab, text="Cycle Analysis")
        ttk.Label(self.window, textvariable=self.gallery_status_var, foreground="#92400e").pack(
            fill=tk.X, padx=12, pady=(0, 8)
        )

        self._build_time_series_tab(time_tab)
        self._build_magnitude_phase_tab(magnitude_phase_tab)
        self._build_frequency_spectrum_tab(frequency_spectrum_tab)
        self._build_spectrogram_tab(spectrogram_tab)
        self._build_comparison_tab(comparison_tab)
        self._build_dataset_comparison_tab(dataset_comparison_tab)
        self._build_cycle_tab(cycle_tab)
        self._bind_plot_refresh(
            [self.time_x_var, self.time_subplots_var, *self._time_y_vars.values()],
            "_time_plot_refresh_job_id",
            self._render_time_series,
        )
        self._bind_plot_refresh(
            [
                self.magnitude_phase_example_var,
                self.wrapped_phase_var,
                self.frequency_source_var,
                self.frequency_comparison_var,
                self.frequency_reference_var,
                self.frequency_spacing_var,
                self.frequency_detrend_var,
                self.frequency_window_var,
                self.frequency_segment_var,
                self.frequency_overlap_var,
                self.bode_operation_var,
                self.bode_cutoff_var,
                self.bode_cutoff_high_var,
                self.bode_order_var,
                self.bode_spacing_var,
            ],
            "_magnitude_phase_refresh_job_id",
            self._render_magnitude_phase,
        )
        self._bind_plot_refresh(
            [
                self.spectrum_method_var,
                self.spectrum_source_var,
                self.spectrum_comparison_var,
                self.spectrum_reference_var,
                self.spectrum_spacing_var,
                self.spectrum_window_var,
                self.spectrum_detrend_var,
                self.spectrum_segment_var,
                self.spectrum_overlap_var,
            ],
            "_frequency_spectrum_refresh_job_id",
            self._render_frequency_spectrum,
        )
        self._bind_plot_refresh(
            [
                self.spectrogram_source_var,
                self.spectrogram_reference_var,
                self.spectrogram_spacing_var,
                self.spectrogram_window_var,
                self.spectrogram_segment_var,
                self.spectrogram_overlap_var,
                self.spectrogram_detrend_var,
            ],
            "_spectrogram_refresh_job_id",
            self._render_spectrogram,
        )
        self._bind_plot_refresh(
            [
                self.signal_comparison_mode_var,
                self.filter_source_var,
                self.filter_operation_var,
                self.filter_window_var,
                self.filter_alpha_var,
                self.filter_cutoff_var,
                self.filter_cutoff_high_var,
                self.filter_order_var,
                self.filter_spacing_var,
            ],
            "_comparison_refresh_job_id",
            self._render_comparison,
        )
        self._bind_plot_refresh(
            [
                self.cycle_mode_var,
                self.cycle_source_var,
                self.cycle_reference_var,
                self.cycle_length_var,
                self.cycle_threshold_var,
                self.cycle_prominence_var,
                self.cycle_max_var,
                *self.cycle_metric_vars.values(),
            ],
            "_cycle_refresh_job_id",
            self._render_cycle,
        )
        self._bind_plot_refresh(
            [
                self.dataset_comparison_mode_var,
                self.dataset_comparison_baseline_var,
                self.dataset_comparison_x_var,
                *self.dataset_comparison_column_vars.values(),
                *self.dataset_comparison_visibility_vars.values(),
                self.dataset_comparison_normalize_var,
                self.dataset_comparison_zero_start_var,
                self.dataset_comparison_trim_overlap_var,
                self.dataset_comparison_subplots_var,
                self.dataset_comparison_highlight_var,
                self.dataset_comparison_show_legend_var,
            ],
            "_dataset_comparison_refresh_job_id",
            self._render_dataset_comparison,
        )
        self.magnitude_phase_example_var.trace_add("write", lambda *_: self._refresh_magnitude_phase_controls())
        self.spectrum_method_var.trace_add("write", lambda *_: self._refresh_frequency_spectrum_controls())
        self.bode_operation_var.trace_add("write", lambda *_: self._refresh_magnitude_phase_controls())
        self.filter_operation_var.trace_add("write", lambda *_: self._refresh_filter_controls())
        self.cycle_mode_var.trace_add("write", lambda *_: self._refresh_cycle_controls())
        for variable in self._time_y_vars.values():
            variable.trace_add("write", lambda *_: self._update_time_summary())
        self._refresh_magnitude_phase_controls()
        self._refresh_frequency_spectrum_controls()
        self._refresh_filter_controls()
        self._refresh_cycle_controls()
        self._render_time_series()
        self._render_magnitude_phase()
        self._render_frequency_spectrum()
        self._render_spectrogram()
        self._render_comparison()
        self._render_dataset_comparison()
        self._render_cycle()

    def _build_time_series_tab(self, parent: ttk.Frame) -> None:
        controls_frame = ttk.LabelFrame(parent, text="Plot controls", padding=6)
        controls_frame.pack(fill=tk.X, padx=5, pady=(5, 3))
        controls = build_time_series_plot_controls(
            controls_frame,
            x_variable=self.time_x_var,
            y_summary_variable=self.time_y_summary_var,
            subplots_variable=self.time_subplots_var,
            on_select_all=self._select_all_time_columns,
            on_clear_selection=self._clear_time_columns,
            on_update=self._render_time_series,
        )
        controls.update_button.grid_remove()
        controls.x_combo.configure(values=["Index", *self._time_frame.columns])
        controls.y_selector_button.state(["!disabled"])
        for column, variable in self._time_y_vars.items():
            controls.y_selector_menu.add_checkbutton(
                label=column,
                variable=variable,
            )
        self._build_gallery_demo_inputs(parent, self.examples.spectral_spec.menu_label)
        self.time_plot_container = ttk.Frame(parent)
        self.time_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_magnitude_phase_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Plot controls", padding=6)
        controls.pack(fill=tk.X, padx=5, pady=5)
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Example").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        example_combo = ttk.Combobox(
            controls,
            textvariable=self.magnitude_phase_example_var,
            values=("Transfer Estimate", "Bode Response"),
            state="readonly",
        )
        example_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        io_columns = [column for column in self.examples.input_output_frame if column != "time_s"]
        self.frequency_source_controls = self._add_labeled_control(controls, 1, "Signal", ttk.Combobox(
            controls, textvariable=self.frequency_source_var, values=io_columns, state="readonly"
        ))
        self.frequency_comparison_controls = self._add_labeled_control(controls, 2, "Comparison signal", ttk.Combobox(
            controls, textvariable=self.frequency_comparison_var, values=io_columns, state="readonly"
        ))
        self.frequency_reference_controls = self._add_labeled_control(controls, 3, "X / reference", ttk.Combobox(
            controls, textvariable=self.frequency_reference_var, values=("Index", "time_s"), state="readonly"
        ))
        self.frequency_spacing_controls = self._add_labeled_control(controls, 4, "Index step size", ttk.Entry(
            controls, textvariable=self.frequency_spacing_var
        ))
        self.frequency_window_controls = self._add_labeled_control(controls, 5, "Window", ttk.Combobox(
            controls, textvariable=self.frequency_window_var, values=("hann", "hamming", "blackman", "rectangular"), state="readonly"
        ))
        self.frequency_segment_controls = self._add_labeled_control(controls, 6, "Segment length", ttk.Entry(controls, textvariable=self.frequency_segment_var))
        self.frequency_overlap_controls = self._add_labeled_control(controls, 7, "Overlap", ttk.Entry(controls, textvariable=self.frequency_overlap_var))
        self.frequency_detrend_check = ttk.Checkbutton(controls, text="Remove trend", variable=self.frequency_detrend_var)
        self.frequency_detrend_check.grid(row=8, column=0, sticky="w", padx=5, pady=3)
        self.bode_operation_controls = self._add_labeled_control(controls, 1, "Filter type", ttk.Combobox(
            controls,
            textvariable=self.bode_operation_var,
            values=("butterworth_lowpass", "butterworth_highpass", "butterworth_bandpass"),
            state="readonly",
        ))
        self.bode_cutoff_controls = self._add_labeled_control(controls, 2, "Low cutoff [Hz]", ttk.Entry(controls, textvariable=self.bode_cutoff_var))
        self.bode_cutoff_high_controls = self._add_labeled_control(controls, 3, "High cutoff [Hz]", ttk.Entry(controls, textvariable=self.bode_cutoff_high_var))
        self.bode_order_controls = self._add_labeled_control(controls, 4, "Filter order", ttk.Entry(controls, textvariable=self.bode_order_var))
        self.bode_spacing_controls = self._add_labeled_control(controls, 5, "Sample spacing [s]", ttk.Entry(controls, textvariable=self.bode_spacing_var))
        ttk.Checkbutton(controls, text="Wrapped phase", variable=self.wrapped_phase_var).grid(row=8, column=1, sticky="w", padx=5, pady=3)
        self._build_gallery_demo_inputs(
            parent,
            "Input-Output Reference for Transfer Estimate; Bode response is calculated from filter settings.",
        )
        self.magnitude_phase_plot_container = ttk.Frame(parent)
        self.magnitude_phase_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_frequency_spectrum_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Plot controls", padding=6)
        controls.pack(fill=tk.X, padx=5, pady=5)
        controls.columnconfigure(1, weight=1)
        signal_columns = [column for column in self.examples.spectral_frame if column != "time_s"]
        self._add_labeled_control(controls, 0, "Method", ttk.Combobox(
            controls,
            textvariable=self.spectrum_method_var,
            values=("FFT Amplitude", "Welch PSD", "Coherence"),
            state="readonly",
        ))
        self._add_labeled_control(controls, 1, "Signal", ttk.Combobox(
            controls, textvariable=self.spectrum_source_var, values=signal_columns, state="readonly"
        ))
        self.spectrum_comparison_controls = self._add_labeled_control(controls, 2, "Comparison signal", ttk.Combobox(
            controls, textvariable=self.spectrum_comparison_var, values=signal_columns, state="readonly"
        ))
        self._add_labeled_control(controls, 3, "X / reference", ttk.Combobox(
            controls,
            textvariable=self.spectrum_reference_var,
            values=("Index", "time_s"),
            state="readonly",
        ))
        self._add_labeled_control(controls, 4, "Index step size [s]", ttk.Entry(
            controls, textvariable=self.spectrum_spacing_var
        ))
        self._add_labeled_control(controls, 5, "Window", ttk.Combobox(
            controls,
            textvariable=self.spectrum_window_var,
            values=("hann", "hamming", "blackman", "rectangular"),
            state="readonly",
        ))
        self.spectrum_segment_controls = self._add_labeled_control(controls, 6, "Segment length", ttk.Entry(
            controls, textvariable=self.spectrum_segment_var
        ))
        self.spectrum_overlap_controls = self._add_labeled_control(controls, 7, "Overlap", ttk.Entry(
            controls, textvariable=self.spectrum_overlap_var
        ))
        self.spectrum_detrend_check = ttk.Checkbutton(
            controls,
            text="Remove trend before analysis",
            variable=self.spectrum_detrend_var,
        )
        self.spectrum_detrend_check.grid(row=8, column=0, columnspan=2, sticky="w", padx=5, pady=3)
        self._build_gallery_demo_inputs(parent, self.examples.spectral_spec.menu_label)
        self.frequency_spectrum_plot_container = ttk.Frame(parent)
        self.frequency_spectrum_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _refresh_frequency_spectrum_controls(self) -> None:
        method = self.spectrum_method_var.get()
        self._set_labeled_controls_visible(self.spectrum_comparison_controls, method == "Coherence")
        uses_segments = method in {"Welch PSD", "Coherence"}
        self._set_labeled_controls_visible(self.spectrum_segment_controls, uses_segments)
        self._set_labeled_controls_visible(self.spectrum_overlap_controls, uses_segments)

    @staticmethod
    def _add_labeled_control(parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> tuple[ttk.Label, tk.Widget]:
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", padx=5, pady=3)
        widget.grid(row=row, column=1, sticky="ew", padx=5, pady=3)
        return label_widget, widget

    @staticmethod
    def _build_gallery_demo_inputs(parent: ttk.Frame, description: str) -> ttk.LabelFrame:
        inputs = ttk.LabelFrame(parent, text="Gallery demo inputs", padding=(8, 4))
        inputs.pack(fill=tk.X, padx=5, pady=(0, 4))
        ttk.Label(inputs, text=description).pack(anchor="w")
        return inputs

    def _build_spectrogram_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Plot controls", padding=6)
        controls.pack(fill=tk.X, padx=5, pady=5)
        controls.columnconfigure(1, weight=1)
        signal_columns = [column for column in self.examples.spectral_frame if column != "time_s"]
        self._add_labeled_control(controls, 0, "Source", ttk.Combobox(
            controls, textvariable=self.spectrogram_source_var, values=signal_columns, state="readonly"
        ))
        self._add_labeled_control(controls, 1, "X / reference", ttk.Combobox(
            controls, textvariable=self.spectrogram_reference_var, values=("Index", "time_s"), state="readonly"
        ))
        self._add_labeled_control(controls, 2, "Index step size", ttk.Entry(controls, textvariable=self.spectrogram_spacing_var))
        self._add_labeled_control(controls, 3, "Window", ttk.Combobox(
            controls, textvariable=self.spectrogram_window_var, values=("hann", "hamming", "blackman", "rectangular"), state="readonly"
        ))
        self._add_labeled_control(controls, 4, "Segment length", ttk.Entry(controls, textvariable=self.spectrogram_segment_var))
        self._add_labeled_control(controls, 5, "Overlap", ttk.Entry(controls, textvariable=self.spectrogram_overlap_var))
        ttk.Checkbutton(controls, text="Remove trend", variable=self.spectrogram_detrend_var).grid(row=6, column=0, sticky="w", padx=5, pady=3)
        self._build_gallery_demo_inputs(parent, self.examples.spectral_spec.menu_label)
        self.spectrogram_plot_container = ttk.Frame(parent)
        self.spectrogram_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_comparison_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Plot controls", padding=6)
        controls.pack(fill=tk.X, padx=5, pady=5)
        controls.columnconfigure(1, weight=1)
        self._add_labeled_control(controls, 0, "Plot type", ttk.Combobox(
            controls,
            textvariable=self.signal_comparison_mode_var,
            values=("Original vs filtered", "Residual + spectrum"),
            state="readonly",
        ))
        signal_columns = [column for column in self.examples.spectral_frame if column != "time_s"]
        self._add_labeled_control(controls, 1, "Active column", ttk.Combobox(
            controls, textvariable=self.filter_source_var, values=signal_columns, state="readonly"
        ))
        self._add_labeled_control(controls, 2, "Filter type", ttk.Combobox(
            controls, textvariable=self.filter_operation_var, values=SIGNAL_FILTER_OPERATIONS, state="readonly"
        ))
        self.filter_window_controls = self._add_labeled_control(controls, 3, "Window size", ttk.Entry(controls, textvariable=self.filter_window_var))
        self.filter_alpha_controls = self._add_labeled_control(controls, 4, "Alpha", ttk.Entry(controls, textvariable=self.filter_alpha_var))
        self.filter_cutoff_controls = self._add_labeled_control(controls, 5, "Low cutoff [Hz]", ttk.Entry(controls, textvariable=self.filter_cutoff_var))
        self.filter_cutoff_high_controls = self._add_labeled_control(controls, 6, "High cutoff [Hz]", ttk.Entry(controls, textvariable=self.filter_cutoff_high_var))
        self.filter_order_controls = self._add_labeled_control(controls, 7, "Filter order", ttk.Entry(controls, textvariable=self.filter_order_var))
        self.filter_spacing_controls = self._add_labeled_control(controls, 8, "Sample spacing [s]", ttk.Entry(controls, textvariable=self.filter_spacing_var))
        self._build_gallery_demo_inputs(parent, self.examples.spectral_spec.menu_label)
        self.comparison_plot_container = ttk.Frame(parent)
        self.comparison_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_dataset_comparison_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Plot controls", padding=6)
        controls.pack(fill=tk.X, padx=5, pady=(5, 3))
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)
        dataset_paths = [spec.basename for spec in self.examples.comparison_specs]
        ttk.Label(controls, text="Mode").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Combobox(
            controls,
            textvariable=self.dataset_comparison_mode_var,
            values=("Overlay", "Difference (candidate - baseline)"),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(controls, text="Baseline").grid(row=0, column=2, sticky="w", padx=5, pady=3)
        ttk.Combobox(
            controls,
            textvariable=self.dataset_comparison_baseline_var,
            values=dataset_paths,
            state="readonly",
        ).grid(row=0, column=3, sticky="ew", padx=5, pady=3)
        ttk.Label(controls, text="X axis").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        ttk.Combobox(
            controls,
            textvariable=self.dataset_comparison_x_var,
            values=("Index", "time_s"),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        signals = ttk.LabelFrame(controls, text="Signals")
        signals.grid(row=1, column=2, columnspan=2, sticky="ew", padx=5, pady=3)
        for column, variable in self.dataset_comparison_column_vars.items():
            ttk.Checkbutton(signals, text=column, variable=variable).pack(side=tk.LEFT, padx=4)

        options = ttk.Frame(controls)
        options.grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=3)
        for label, variable in (
            ("Normalize amplitude", self.dataset_comparison_normalize_var),
            ("Zero-start", self.dataset_comparison_zero_start_var),
            ("Trim to overlap", self.dataset_comparison_trim_overlap_var),
            ("Channels in grid", self.dataset_comparison_subplots_var),
            ("Highlight deviations", self.dataset_comparison_highlight_var),
            ("Show legend", self.dataset_comparison_show_legend_var),
        ):
            ttk.Checkbutton(options, text=label, variable=variable).pack(side=tk.LEFT, padx=4)

        datasets = ttk.LabelFrame(parent, text="Gallery demo inputs")
        datasets.pack(fill=tk.X, padx=5, pady=3)
        for spec in self.examples.comparison_specs:
            label = spec.menu_label.removeprefix("Comparison Validation - ")
            ttk.Checkbutton(
                datasets,
                text=label,
                variable=self.dataset_comparison_visibility_vars[spec.basename],
            ).pack(side=tk.LEFT, padx=5)

        self.dataset_comparison_plot_container = ttk.Frame(parent)
        self.dataset_comparison_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_cycle_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.LabelFrame(parent, text="Plot controls", padding=6)
        controls.pack(fill=tk.X, padx=5, pady=5)
        controls.columnconfigure(1, weight=1)
        self._add_labeled_control(controls, 0, "Active column", ttk.Combobox(
            controls, textvariable=self.cycle_source_var, values=("cycle_process", "cycle_reference_zero", "trigger_pulse"), state="readonly"
        ))
        self._add_labeled_control(controls, 1, "Mode", ttk.Combobox(
            controls, textvariable=self.cycle_mode_var, values=("fixed_length", "rising_edge", "zero_crossing", "peak"), state="readonly"
        ))
        self.cycle_reference_controls = self._add_labeled_control(controls, 2, "Reference", ttk.Combobox(
            controls, textvariable=self.cycle_reference_var, values=("trigger_pulse", "cycle_reference_zero", "cycle_process"), state="readonly"
        ))
        self.cycle_length_controls = self._add_labeled_control(controls, 3, "Cycle / minimum length", ttk.Entry(controls, textvariable=self.cycle_length_var))
        self.cycle_threshold_controls = self._add_labeled_control(controls, 4, "Threshold", ttk.Entry(controls, textvariable=self.cycle_threshold_var))
        self.cycle_prominence_controls = self._add_labeled_control(controls, 5, "Prominence", ttk.Entry(controls, textvariable=self.cycle_prominence_var))
        self.cycle_max_controls = self._add_labeled_control(controls, 6, "Max cycles", ttk.Entry(controls, textvariable=self.cycle_max_var))
        metrics = ttk.Frame(controls)
        metrics.grid(row=7, column=0, columnspan=2, sticky="ew", padx=5, pady=3)
        for key, label in (("mean", "Mean"), ("rms", "RMS"), ("peak_to_peak", "P2P"), ("min", "Min"), ("max", "Max")):
            ttk.Checkbutton(metrics, text=label, variable=self.cycle_metric_vars[key]).pack(side=tk.LEFT, padx=4)
        self._build_gallery_demo_inputs(parent, self.examples.cycle_spec.menu_label)
        self.cycle_plot_container = ttk.Frame(parent)
        self.cycle_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _selected_time_columns(self) -> list[str]:
        return [column for column, variable in self._time_y_vars.items() if variable.get()]

    def _bind_plot_refresh(
        self,
        variables: list[tk.Variable],
        job_attr: str,
        callback: Callable[[], object],
    ) -> None:
        for variable in variables:
            variable.trace_add(
                "write",
                lambda *_args, job_attr=job_attr, callback=callback: self._schedule_debounced(
                    self.window,
                    job_attr,
                    callback,
                ),
            )

    @staticmethod
    def _set_labeled_controls_visible(controls: tuple[tk.Widget, tk.Widget], visible: bool) -> None:
        for widget in controls:
            if visible:
                widget.grid()
            else:
                widget.grid_remove()

    def _refresh_magnitude_phase_controls(self) -> None:
        transfer_selected = self.magnitude_phase_example_var.get() == "Transfer Estimate"
        for controls in (
            self.frequency_source_controls,
            self.frequency_comparison_controls,
            self.frequency_reference_controls,
            self.frequency_spacing_controls,
            self.frequency_window_controls,
            self.frequency_segment_controls,
            self.frequency_overlap_controls,
        ):
            self._set_labeled_controls_visible(controls, transfer_selected)
        if transfer_selected:
            self.frequency_detrend_check.grid()
        else:
            self.frequency_detrend_check.grid_remove()
        for controls in (
            self.bode_operation_controls,
            self.bode_cutoff_controls,
            self.bode_order_controls,
            self.bode_spacing_controls,
        ):
            self._set_labeled_controls_visible(controls, not transfer_selected)
        self._set_labeled_controls_visible(
            self.bode_cutoff_high_controls,
            not transfer_selected and self.bode_operation_var.get() == "butterworth_bandpass",
        )

    def _refresh_filter_controls(self) -> None:
        operation = self.filter_operation_var.get()
        uses_window = operation in {"moving_average", "median", "high_pass"}
        uses_alpha = operation == "exponential_smoothing"
        uses_butterworth = operation.startswith("butterworth")
        self._set_labeled_controls_visible(self.filter_window_controls, uses_window)
        self._set_labeled_controls_visible(self.filter_alpha_controls, uses_alpha)
        self._set_labeled_controls_visible(self.filter_cutoff_controls, uses_butterworth)
        self._set_labeled_controls_visible(
            self.filter_cutoff_high_controls,
            operation == "butterworth_bandpass",
        )
        self._set_labeled_controls_visible(self.filter_order_controls, uses_butterworth)
        self._set_labeled_controls_visible(self.filter_spacing_controls, uses_butterworth)

    def _refresh_cycle_controls(self) -> None:
        mode = self.cycle_mode_var.get()
        self._set_labeled_controls_visible(self.cycle_reference_controls, mode != "fixed_length")
        self._set_labeled_controls_visible(self.cycle_threshold_controls, mode == "rising_edge")
        self._set_labeled_controls_visible(self.cycle_prominence_controls, mode == "peak")
        self._set_labeled_controls_visible(self.cycle_max_controls, mode != "fixed_length")

    def _select_all_time_columns(self) -> None:
        for variable in self._time_y_vars.values():
            variable.set(True)
        self._update_time_summary()

    def _clear_time_columns(self) -> None:
        for variable in self._time_y_vars.values():
            variable.set(False)
        self._update_time_summary()

    def _update_time_summary(self) -> None:
        selected_count = len(self._selected_time_columns())
        self.time_y_summary_var.set(f"{selected_count} channel{'s' if selected_count != 1 else ''} selected")

    def _render_time_series(self) -> None:
        selected_columns = self._selected_time_columns()
        if not selected_columns:
            return
        figure = create_plot_figure(
            PlotOptions(
                cols_to_plot=selected_columns,
                xcol=self.time_x_var.get() or "Index",
                use_subplots=self.time_subplots_var.get(),
                title=self.examples.spectral_spec.menu_label,
                y_label="Value",
                style=self.style,
            ),
            ["gallery"],
            {"gallery": self._time_frame},
        )
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_time_figure",
            canvas_attr="_time_canvas",
            toolbar_attr="_time_toolbar",
            container=self.time_plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
            plot_type=PlotDescriptor(
                "Time series",
                "Subplots" if self.time_subplots_var.get() else "Overlay",
            ),
        )

    def _render_magnitude_phase(self) -> None:
        try:
            transfer_example = self.magnitude_phase_example_var.get() == "Transfer Estimate"
            if transfer_example:
                reference = self.frequency_reference_var.get()
                transfer_result = compute_transfer_estimate(
                    self.examples.input_output_frame,
                    source_column=self.frequency_source_var.get(),
                    comparison_column=self.frequency_comparison_var.get(),
                    reference_column=None if reference == "Index" else reference,
                    sample_spacing=float(self.frequency_spacing_var.get()),
                    window=self.frequency_window_var.get(),
                    detrend=self.frequency_detrend_var.get(),
                    segment_length=int(self.frequency_segment_var.get()),
                    overlap_fraction=float(self.frequency_overlap_var.get()),
                )
                values = prepare_frequency_plot_values(
                    transfer_result,
                    unwrap_phase=not self.wrapped_phase_var.get(),
                )
                phase_degrees = values.phase_degrees if values.phase_degrees is not None else ()
                plot_data = MagnitudePhasePlotData(
                    x_values=values.frequencies,
                    magnitude_values=values.magnitudes,
                    phase_degrees=phase_degrees,
                    magnitude_title=(
                        f"Transfer Estimate: {self.frequency_comparison_var.get()} -> "
                        f"{self.frequency_source_var.get()}"
                    ),
                    magnitude_label="|H(f)| [dB]",
                    phase_title="Transfer Phase",
                    phase_label="Phase [deg] (output/input)",
                    wrapped_phase=values.wrapped_phase,
                )
            else:
                operation = self.bode_operation_var.get()
                cutoff: float | list[float] = float(self.bode_cutoff_var.get())
                if operation == "butterworth_bandpass":
                    cutoff = [float(self.bode_cutoff_var.get()), float(self.bode_cutoff_high_var.get())]
                frequencies, magnitude_db, phase_degrees = compute_butterworth_response(
                    operation=operation,
                    cutoff_hz=cutoff,
                    sample_spacing=float(self.bode_spacing_var.get()),
                    filter_order=int(self.bode_order_var.get()),
                )
                if not self.wrapped_phase_var.get():
                    phase_degrees = np.degrees(np.unwrap(np.radians(phase_degrees)))
                plot_data = MagnitudePhasePlotData(
                    x_values=frequencies,
                    magnitude_values=magnitude_db,
                    phase_degrees=phase_degrees,
                    magnitude_title=f"Bode Magnitude - {operation}",
                    magnitude_label="Magnitude [dB]",
                    phase_title="Bode Phase",
                    wrapped_phase=self.wrapped_phase_var.get(),
                )
        except (TypeError, ValueError) as error:
            self.gallery_status_var.set(str(error))
            return
        self.gallery_status_var.set("")
        figure = create_magnitude_phase_figure(plot_data, style=self.style)
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_magnitude_phase_figure",
            canvas_attr="_magnitude_phase_canvas",
            toolbar_attr="_magnitude_phase_toolbar",
            container=self.magnitude_phase_plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
            plot_type=PlotDescriptor(
                "Frequency",
                "Transfer estimate" if transfer_example else "Bode response",
            ),
        )

    def _render_frequency_spectrum(self) -> None:
        method = self.spectrum_method_var.get()
        reference = self.spectrum_reference_var.get()
        options = {
            "dataframe": self.examples.spectral_frame,
            "source_column": self.spectrum_source_var.get(),
            "reference_column": None if reference == "Index" else reference,
            "sample_spacing": float(self.spectrum_spacing_var.get()),
            "window": self.spectrum_window_var.get(),
            "detrend": self.spectrum_detrend_var.get(),
        }
        try:
            if method == "FFT Amplitude":
                result = compute_fft_spectrum(**options)
                y_label = "Amplitude"
            elif method == "Welch PSD":
                result = compute_welch_psd(
                    **options,
                    segment_length=int(self.spectrum_segment_var.get()),
                    overlap_fraction=float(self.spectrum_overlap_var.get()),
                )
                y_label = "PSD"
            else:
                result = compute_coherence_spectrum(
                    **options,
                    comparison_column=self.spectrum_comparison_var.get(),
                    segment_length=int(self.spectrum_segment_var.get()),
                    overlap_fraction=float(self.spectrum_overlap_var.get()),
                )
                y_label = "Coherence"
        except (TypeError, ValueError, KeyError) as error:
            self.gallery_status_var.set(str(error))
            return

        values = prepare_frequency_plot_values(result)
        source_column = self.spectrum_source_var.get()
        title = f"{method} of {source_column}"
        if method == "Coherence":
            title = f"Coherence: {self.spectrum_comparison_var.get()} -> {source_column}"
        plot_data = FrequencySeriesPlotData(
            x_values=values.frequencies,
            y_values=values.magnitudes,
            title=title,
            y_label=y_label,
            y_limits=(-0.02, 1.02) if method == "Coherence" else None,
            coherence_segment_count=result.segment_count if method == "Coherence" else None,
        )
        self.gallery_status_var.set("")
        figure = create_frequency_series_figure(plot_data, style=self.style)
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_frequency_spectrum_figure",
            canvas_attr="_frequency_spectrum_canvas",
            toolbar_attr="_frequency_spectrum_toolbar",
            container=self.frequency_spectrum_plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
            plot_type=PlotDescriptor("Frequency", method),
        )

    def _render_spectrogram(self) -> None:
        try:
            reference = self.spectrogram_reference_var.get()
            result = compute_spectrogram(
                self.examples.spectral_frame,
                source_column=self.spectrogram_source_var.get(),
                reference_column=None if reference == "Index" else reference,
                sample_spacing=float(self.spectrogram_spacing_var.get()),
                window=self.spectrogram_window_var.get(),
                detrend=self.spectrogram_detrend_var.get(),
                segment_length=int(self.spectrogram_segment_var.get()),
                overlap_fraction=float(self.spectrogram_overlap_var.get()),
            )
        except (TypeError, ValueError) as error:
            self.gallery_status_var.set(str(error))
            return
        self.gallery_status_var.set("")
        figure = create_spectrogram_figure(
            prepare_spectrogram_plot_data(result),
            style=self.style,
        )
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_spectrogram_figure",
            canvas_attr="_spectrogram_canvas",
            toolbar_attr="_spectrogram_toolbar",
            container=self.spectrogram_plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
            plot_type=PlotDescriptor("Frequency", "Spectrogram"),
        )

    def _render_comparison(self) -> None:
        try:
            operation = self.filter_operation_var.get()
            cutoff: float | list[float] = float(self.filter_cutoff_var.get())
            if operation == "butterworth_bandpass":
                cutoff = [float(self.filter_cutoff_var.get()), float(self.filter_cutoff_high_var.get())]
            filtered_frame = apply_signal_filter(
                self.examples.spectral_frame,
                source_column=self.filter_source_var.get(),
                operation=operation,
                new_column="filtered_signal",
                window_size=int(self.filter_window_var.get()),
                alpha=float(self.filter_alpha_var.get()),
                cutoff_hz=cutoff,
                sample_spacing=float(self.filter_spacing_var.get()),
                filter_order=int(self.filter_order_var.get()),
            )
        except (TypeError, ValueError) as error:
            self.gallery_status_var.set(str(error))
            return
        self.gallery_status_var.set("")
        source_column = self.filter_source_var.get()
        if self.signal_comparison_mode_var.get() == "Residual + spectrum":
            sample_spacing = float(self.filter_spacing_var.get())
            residual_result = compute_residual_spectrum(
                filtered_frame[source_column].to_numpy(dtype=float),
                filtered_frame["filtered_signal"].to_numpy(dtype=float),
                sample_spacing,
            )
            sample_indices = np.arange(len(residual_result.residual_values), dtype=float)
            x_values = sample_indices * sample_spacing if sample_spacing > 0 else sample_indices
            spectrum_plot_data = None
            if residual_result.frequencies is not None and residual_result.amplitudes is not None:
                spectrum_plot_data = FrequencySeriesPlotData(
                    x_values=residual_result.frequencies,
                    y_values=residual_result.amplitudes,
                    title="Residual Spectrum",
                    x_label=residual_result.frequency_label,
                )
            plot_data = ResidualSpectrumPlotData(
                deviation=DeviationPanelPlotData(
                    series=(
                        DeviationSeriesPlotData(
                            x_values=x_values,
                            values=residual_result.residual_values,
                            label="Residual",
                        ),
                    ),
                    title=f"Residual Preview - {source_column} ({operation})",
                    x_label="Time [s]" if sample_spacing > 0 else "Sample",
                    y_label="Original - Filtered",
                    reference_label="Zero residual",
                ),
                spectrum=spectrum_plot_data,
            )
            figure = create_residual_spectrum_figure(plot_data, style=self.style)
            plot_type = PlotDescriptor("Deviation", "Residual + spectrum")
        else:
            figure = create_signal_comparison_figure(
                SignalComparisonPlotData(
                    x_values=filtered_frame["time_s"],
                    original_values=filtered_frame[source_column],
                    comparison_values=filtered_frame["filtered_signal"],
                    title=f"Filter Preview - {source_column} ({operation})",
                    x_label="Time [s]",
                    y_label=source_column,
                ),
                style=self.style,
            )
            plot_type = PlotDescriptor("Comparison", "Filtered signal")
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_comparison_figure",
            canvas_attr="_comparison_canvas",
            toolbar_attr="_comparison_toolbar",
            container=self.comparison_plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
            plot_type=plot_type,
        )

    def _render_dataset_comparison(self) -> None:
        dataset_paths = [
            spec.basename
            for spec in self.examples.comparison_specs
            if self.dataset_comparison_visibility_vars[spec.basename].get()
        ]
        baseline_path = self.dataset_comparison_baseline_var.get()
        selected_columns = [
            column
            for column, variable in self.dataset_comparison_column_vars.items()
            if variable.get()
        ]
        difference_mode = self.dataset_comparison_mode_var.get().startswith("Difference")
        if not selected_columns:
            self.gallery_status_var.set("Select at least one comparison signal.")
            return
        if difference_mode:
            candidates = [path for path in dataset_paths if path != baseline_path]
            if not candidates:
                self.gallery_status_var.set("Select at least one candidate dataset.")
                return
            if baseline_path not in dataset_paths:
                dataset_paths.insert(0, baseline_path)
        elif not dataset_paths:
            self.gallery_status_var.set("Select at least one dataset to display.")
            return

        x_column = self.dataset_comparison_x_var.get().strip() or "Index"
        comparison_style = replace(
            self.style,
            show_legend=self.dataset_comparison_show_legend_var.get(),
        )
        try:
            if difference_mode:
                figure = build_difference_figure(
                    dataset_paths,
                    self.examples.comparison_frames,
                    baseline_path,
                    selected_columns,
                    x_column=x_column,
                    normalize=self.dataset_comparison_normalize_var.get(),
                    zero_start=self.dataset_comparison_zero_start_var.get(),
                    trim_overlap=self.dataset_comparison_trim_overlap_var.get(),
                    channels_in_grid=self.dataset_comparison_subplots_var.get(),
                    highlight_deviations=self.dataset_comparison_highlight_var.get(),
                    style=comparison_style,
                )
            else:
                display_paths = list(dataset_paths)
                if self.dataset_comparison_highlight_var.get() and baseline_path not in display_paths:
                    display_paths.insert(0, baseline_path)
                plot_frames = build_comparison_display_frames(
                    display_paths,
                    self.examples.comparison_frames,
                    selected_columns,
                    x_column=x_column,
                    trim_overlap=self.dataset_comparison_trim_overlap_var.get(),
                    normalize=self.dataset_comparison_normalize_var.get(),
                    zero_start=self.dataset_comparison_zero_start_var.get(),
                )
                _, subplot_columns = calculate_subplot_grid(len(selected_columns))
                figure = create_plot_figure(
                    PlotOptions(
                        cols_to_plot=selected_columns,
                        xcol=x_column,
                        use_subplots=self.dataset_comparison_subplots_var.get(),
                        title="Dataset Comparison",
                        y_label="Value",
                        subplot_columns=subplot_columns,
                        style=comparison_style,
                    ),
                    dataset_paths,
                    plot_frames,
                    dataset_line_styles={baseline_path: "--"},
                )
                if self.dataset_comparison_highlight_var.get():
                    add_overlay_deviation_highlights(
                        figure,
                        dataset_paths,
                        plot_frames,
                        baseline_path,
                        selected_columns,
                        x_column=x_column,
                        channels_in_grid=self.dataset_comparison_subplots_var.get(),
                        style=comparison_style,
                    )
        except (TypeError, ValueError) as error:
            self.gallery_status_var.set(str(error))
            return
        self.gallery_status_var.set("")
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_dataset_comparison_figure",
            canvas_attr="_dataset_comparison_canvas",
            toolbar_attr="_dataset_comparison_toolbar",
            container=self.dataset_comparison_plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
            plot_type=PlotDescriptor("Comparison", "Difference" if difference_mode else "Overlay"),
        )

    def _render_cycle(self) -> None:
        try:
            frame = self.examples.cycle_frame
            mode = self.cycle_mode_var.get()
            source = self.cycle_source_var.get()
            reference = self.cycle_reference_var.get()
            cycle_length = int(self.cycle_length_var.get())
            max_cycles = int(self.cycle_max_var.get()) if self.cycle_max_var.get().strip() else None
            if mode == "fixed_length":
                result = compute_fixed_length_cycle_analysis(
                    frame, source_column=source, cycle_length=cycle_length, max_cycles=max_cycles, time_column="time_s"
                )
            else:
                if mode == "rising_edge":
                    ranges = detect_rising_edge_cycle_ranges(
                        frame, reference, float(self.cycle_threshold_var.get()), cycle_length, max_cycles
                    )
                elif mode == "zero_crossing":
                    ranges = detect_zero_crossing_cycle_ranges(
                        frame, reference, min_cycle_length=cycle_length, max_cycles=max_cycles
                    )
                elif mode == "peak":
                    ranges = detect_peak_cycle_ranges(
                        frame, reference, min_cycle_length=cycle_length,
                        prominence=float(self.cycle_prominence_var.get()), max_cycles=max_cycles
                    )
                else:
                    raise ValueError(f"Unsupported cycle mode: {mode}")
                result = compute_cycle_analysis_from_ranges(
                    frame,
                    source_column=source,
                    cycle_ranges=ranges,
                    method=mode,
                    reference_column=reference,
                    time_column="time_s",
                )
        except (TypeError, ValueError) as error:
            self.gallery_status_var.set(str(error))
            return
        self.gallery_status_var.set("")
        enabled_metrics = [key for key, variable in self.cycle_metric_vars.items() if variable.get()]
        figure = create_cycle_figure(
            prepare_cycle_plot_data(result),
            enabled_metrics=enabled_metrics,
            style=self.style,
        )
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_cycle_figure",
            canvas_attr="_cycle_canvas",
            toolbar_attr="_cycle_toolbar",
            container=self.cycle_plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
            plot_type=PlotDescriptor("Cycle", mode.replace("_", " ").title()),
        )

    def focus(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def close(self) -> None:
        self._cancel_scheduled(
            self.window,
            "_time_plot_refresh_job_id",
            "_magnitude_phase_refresh_job_id",
            "_frequency_spectrum_refresh_job_id",
            "_spectrogram_refresh_job_id",
            "_comparison_refresh_job_id",
            "_dataset_comparison_refresh_job_id",
            "_cycle_refresh_job_id",
        )
        for figure in (
            self._time_figure,
            self._magnitude_phase_figure,
            self._frequency_spectrum_figure,
            self._spectrogram_figure,
            self._comparison_figure,
            self._dataset_comparison_figure,
            self._cycle_figure,
        ):
            if figure is not None:
                plt.close(figure)
        self.window.destroy()
        if self.on_close is not None:
            self.on_close(self)
