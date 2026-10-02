"""Operation handler functions for AnalysisWorkspace.

Each function takes the workspace as its first argument and reads UI state
(tk.StringVar values, etc.) directly from it, matching the pattern used in
datapreparation_app/actions.py.  The corresponding AnalysisWorkspace methods
are thin one-line delegations to these functions.
"""

import numpy as np

from Source.data_ops.cycles import (
    compute_cycle_analysis_from_ranges,
    compute_fixed_length_cycle_analysis,
    detect_peak_cycle_ranges,
    detect_rising_edge_cycle_ranges,
    detect_zero_crossing_cycle_ranges,
)
from Source.data_ops.filtering import resolve_filtered_column_name
from Source.data_ops.frame_ops import resample_to_uniform
from Source.data_ops.spectral import (
    compute_coherence_spectrum,
    compute_fft_spectrum,
    compute_residual_spectrum,
    compute_spectrogram,
    compute_transfer_estimate,
    compute_welch_psd,
)
from Source.data_ops.signals import compute_butterworth_response, evaluate_butterworth_settings
from Source.shared.column_roles import get_transformed_column_role
from Source.shared.plot_options import (
    DeviationPanelPlotData,
    DeviationSeriesPlotData,
    FrequencySeriesPlotData,
    ResidualSpectrumPlotData,
    SignalComparisonPlotData,
)
from Source.shared.plot_preparation import prepare_frequency_plot_values, prepare_spectrogram_plot_data

from .actions import (
    build_derived_signal_update,
    build_signal_filter_update,
    build_simple_filter_update,
)
from .rules import get_rule, validate_params
from .state import UI_FREQUENCY_ANALYSIS_METHODS


def _get_signal_filter_cutoff_values(workspace, operation: str) -> str | list[str]:
    if operation == "butterworth_bandpass":
        return [
            workspace.signal_filter_cutoff_var.get(),
            workspace.signal_filter_cutoff_high_var.get(),
        ]
    return workspace.signal_filter_cutoff_var.get()


def _parse_signal_filter_cutoff(workspace, operation: str) -> float | list[float]:
    raw_cutoff = _get_signal_filter_cutoff_values(workspace, operation)
    if isinstance(raw_cutoff, list):
        defaults = ("10.0", "20.0")
        return [float(value or default) for value, default in zip(raw_cutoff, defaults, strict=True)]
    return float(raw_cutoff or "10.0")


def _validate_butterworth_inputs(workspace, operation: str, notification_title: str) -> bool:
    if not operation.startswith("butterworth"):
        return True

    errors, warnings = evaluate_butterworth_settings(
        operation=operation,
        cutoff_hz=_get_signal_filter_cutoff_values(workspace, operation),
        sample_spacing=workspace.signal_filter_spacing_var.get(),
        filter_order=workspace.signal_filter_order_var.get(),
    )
    if errors:
        workspace.notifications.warning(notification_title, details="\n".join(errors))
        return False
    if warnings:
        workspace.notifications.info(notification_title.replace("validation failed", "warnings"), details="\n".join(warnings))
    return True


def _build_signal_filter_update_from_workspace(workspace, source_column: str, operation: str, output_name: str):
    return build_signal_filter_update(
        workspace.session.working_frame,
        source_column=source_column,
        operation=operation,
        output_name=output_name,
        window_size=int(workspace.signal_filter_window_var.get() or "5"),
        alpha=float(workspace.signal_filter_alpha_var.get() or "0.2"),
        cutoff_hz=_parse_signal_filter_cutoff(workspace, operation),
        sample_spacing=float(workspace.signal_filter_spacing_var.get() or "0.0"),
        filter_order=int(workspace.signal_filter_order_var.get() or "4"),
    )


def _compute_signal_filter_preview(workspace, source_column: str, operation: str, error_title: str):
    if not _validate_butterworth_inputs(workspace, operation, f"{error_title} validation failed"):
        return None

    preview_column = "__preview_filter__"
    with workspace._error_dialog(error_title) as failed:
        preview_update = _build_signal_filter_update_from_workspace(
            workspace,
            source_column,
            operation,
            preview_column,
        )
        sample_spacing = float(workspace.signal_filter_spacing_var.get() or "0.0")
    if failed:
        return None
    return preview_update.dataframe[preview_column], sample_spacing


def apply_filter(workspace) -> None:
    """Read filter UI state and apply a simple value-range filter."""
    column = workspace.active_column_var.get().strip()
    if not column:
        workspace.notifications.warning("Select an active analysis column")
        return

    output_column = resolve_filtered_column_name(column, workspace.filter_output_name_var.get())

    with workspace._error_dialog("Filter Error") as _failed:
        update = build_simple_filter_update(
            workspace.session.working_frame,
            active_column=column,
            output_name=workspace.filter_output_name_var.get(),
            minimum_value=workspace.filter_min_var.get(),
            maximum_value=workspace.filter_max_var.get(),
            keep_missing=workspace.keep_missing_var.get(),
        )
    if _failed:
        return

    workspace._replace_working_frame(
        update.dataframe,
        role_overrides={output_column: get_transformed_column_role(workspace.column_roles, column)},
        focus_column=output_column,
    )
    workspace.notifications.success(f"Created {output_column} from {column} using simple filtering")


def apply_signal_filter(workspace) -> None:
    """Read signal-filter UI state and apply the selected filter operation."""
    source_column = workspace.active_column_var.get().strip()
    operation = workspace.signal_filter_operation_var.get().strip()
    if not source_column:
        workspace.notifications.warning("Select an active analysis column")
        return

    rule = get_rule("signal_filter", operation)
    if rule is not None:
        workspace_vars = {
            "window_size": workspace.signal_filter_window_var.get(),
            "alpha": workspace.signal_filter_alpha_var.get(),
            "cutoff_hz": workspace.signal_filter_cutoff_var.get(),
            "cutoff_hz_high": workspace.signal_filter_cutoff_high_var.get(),
            "sample_spacing": workspace.signal_filter_spacing_var.get(),
            "filter_order": workspace.signal_filter_order_var.get(),
        }
        errors = validate_params(rule, workspace_vars)
        if errors:
            workspace.notifications.warning("Signal Filter validation failed", details="\n".join(errors))
            return

    output_column = resolve_filtered_column_name(source_column, workspace.signal_filter_name_var.get())
    if not _validate_butterworth_inputs(workspace, operation, "Signal Filter validation failed"):
        return

    with workspace._error_dialog("Signal Filter Error") as _failed:
        update = _build_signal_filter_update_from_workspace(
            workspace,
            source_column,
            operation,
            workspace.signal_filter_name_var.get(),
        )
    if _failed:
        return

    workspace._replace_working_frame(
        update.dataframe,
        role_overrides={output_column: get_transformed_column_role(workspace.column_roles, source_column)},
        focus_column=output_column,
    )
    workspace.notifications.success(f"Created {output_column} using {operation} on {source_column}")
    workspace.signal_filter_name_var.set("")


def preview_filter_bode(workspace) -> None:
    """Render Butterworth filter frequency response (Bode-style) from current UI parameters."""

    operation = workspace.signal_filter_operation_var.get().strip()
    if operation not in {"butterworth_lowpass", "butterworth_highpass", "butterworth_bandpass"}:
        workspace.notifications.warning("Bode preview is available only for Butterworth filters")
        return

    if not _validate_butterworth_inputs(workspace, operation, "Bode preview validation failed"):
        return

    with workspace._error_dialog("Bode Plot Error") as failed:
        frequencies, magnitude_db, phase_deg = compute_butterworth_response(
            operation=operation,
            cutoff_hz=_parse_signal_filter_cutoff(workspace, operation),
            sample_spacing=float(workspace.signal_filter_spacing_var.get() or "0.0"),
            filter_order=int(workspace.signal_filter_order_var.get() or "4"),
        )
    if failed:
        return

    workspace._render_filter_bode_response(frequencies, magnitude_db, phase_deg, operation)


def preview_signal_filter_result(workspace) -> None:
    """Render original vs filtered signal preview without mutating the working dataframe."""

    source_column = workspace.active_column_var.get().strip()
    operation = workspace.signal_filter_operation_var.get().strip()
    if not source_column:
        workspace.notifications.warning("Select an active analysis column")
        return

    preview_result = _compute_signal_filter_preview(workspace, source_column, operation, "Filter Preview Error")
    if preview_result is None:
        return
    filtered_series, sample_spacing = preview_result

    original_values = workspace.session.working_frame[source_column].to_numpy(dtype=float)
    filtered_values = filtered_series.to_numpy(dtype=float)
    sample_indices = np.arange(len(original_values), dtype=float)
    x_values = sample_indices * sample_spacing if sample_spacing > 0 else sample_indices

    workspace._render_signal_filter_preview(
        SignalComparisonPlotData(
            x_values=x_values,
            original_values=original_values,
            comparison_values=filtered_values,
            title=f"Filter Preview — {source_column} ({operation})",
            x_label="Time [s]" if sample_spacing > 0 else "Sample",
            y_label=source_column,
        )
    )


def preview_signal_filter_residual(workspace) -> None:
    """Render residual (original-filtered) time trace and quick spectrum preview."""

    source_column = workspace.active_column_var.get().strip()
    operation = workspace.signal_filter_operation_var.get().strip()
    if not source_column:
        workspace.notifications.warning("Select an active analysis column")
        return

    preview_result = _compute_signal_filter_preview(workspace, source_column, operation, "Residual Preview Error")
    if preview_result is None:
        return
    filtered_series, sample_spacing = preview_result
    original_values = workspace.session.working_frame[source_column].to_numpy(dtype=float)
    filtered_values = filtered_series.to_numpy(dtype=float)
    residual_result = compute_residual_spectrum(original_values, filtered_values, sample_spacing)
    sample_indices = np.arange(len(residual_result.residual_values), dtype=float)
    x_values = sample_indices * sample_spacing if sample_spacing > 0 else sample_indices
    spectrum_plot_data = None
    if residual_result.frequencies is not None and residual_result.amplitudes is not None:
        spectrum_plot_data = FrequencySeriesPlotData(
            x_values=residual_result.frequencies,
            y_values=residual_result.amplitudes,
            title="Residual Spectrum",
            x_label=residual_result.frequency_label,
            y_label="Amplitude",
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
    workspace._render_signal_filter_residual_preview(plot_data)


def apply_resample(workspace) -> None:
    """Read resample UI state and resample the working frame to a uniform grid."""
    time_column = workspace.resample_time_var.get().strip()
    if not time_column or time_column == "Index":
        workspace.notifications.warning("Select a time column for resampling")
        return

    with workspace._error_dialog("Resample Error") as _failed:
        target_spacing = float(workspace.resample_spacing_var.get() or "1.0")
        resampled = resample_to_uniform(
            workspace.session.working_frame,
            time_column=time_column,
            target_spacing=target_spacing,
        )
    if _failed:
        return

    workspace._replace_working_frame(
        resampled,
    )
    workspace.notifications.success(
        f"Resampled to uniform grid (spacing={target_spacing}) using {time_column}"
    )


def apply_derived_signal(workspace) -> None:
    """Read derived-signal UI state and append the derived column to the working frame."""
    source_column = workspace.active_column_var.get().strip()
    operation = workspace.derived_operation_var.get().strip()
    new_column = workspace.derived_name_var.get().strip()
    reference_column = workspace.derived_reference_var.get().strip() or "Index"
    if not source_column:
        workspace.notifications.warning("Select an active analysis column")
        return

    with workspace._error_dialog("Derived Signal Error") as _failed:
        update = build_derived_signal_update(
            workspace.session.working_frame,
            source_column=source_column,
            operation=operation,
            new_column=new_column,
            reference_column=None if reference_column == "Index" else reference_column,
            window_size=int(workspace.derived_window_var.get() or "5"),
        )
    if _failed:
        return

    workspace._replace_working_frame(
        update.dataframe,
        role_overrides={new_column: get_transformed_column_role(workspace.column_roles, source_column)},
        focus_column=new_column,
    )
    workspace.notifications.success(f"Created {new_column} using {operation} on {source_column}")
    workspace.derived_name_var.set("")


def compute_fft(workspace) -> None:
    """Read frequency-analysis UI state and run the selected spectral computation."""
    source_column = workspace.active_column_var.get().strip()
    if not source_column:
        workspace.notifications.warning("Select an active analysis column")
        return

    analysis_name = workspace.frequency_analysis_var.get().strip() or UI_FREQUENCY_ANALYSIS_METHODS[0]
    rule = get_rule("frequency", analysis_name)
    if rule is not None:
        workspace_vars = {
            "sample_spacing": workspace.fft_sample_spacing_var.get(),
            "segment_length": workspace.welch_segment_length_var.get(),
            "comparison_signal": workspace.frequency_compare_var.get().strip(),
        }
        errors = validate_params(rule, workspace_vars)
        if errors:
            workspace.notifications.warning("Frequency Analysis validation failed", details="\n".join(errors))
            return

    reference_column = workspace.fft_reference_var.get().strip() or "Index"
    with workspace._error_dialog("Frequency Analysis Error") as _failed:
        common_kwargs = {
            "dataframe": workspace.session.working_frame,
            "source_column": source_column,
            "reference_column": None if reference_column == "Index" else reference_column,
            "sample_spacing": float(workspace.fft_sample_spacing_var.get() or "1.0"),
            "window": workspace.fft_window_var.get().strip(),
            "detrend": workspace.fft_detrend_var.get(),
        }
        if analysis_name == "Spectrogram":
            spectrogram_result = compute_spectrogram(
                **common_kwargs,
                segment_length=int(workspace.welch_segment_length_var.get() or "256"),
                overlap_fraction=float(workspace.welch_overlap_fraction_var.get() or "0.5"),
            )
            workspace._render_spectrogram_result(
                spectrogram_result,
                prepare_spectrogram_plot_data(spectrogram_result),
            )
            workspace._latest_frequency_result = None
            diagnostics_callback = getattr(workspace, "_update_frequency_diagnostics", None)
            if diagnostics_callback is not None:
                diagnostics_callback(None)
            workspace.notifications.success(
                f"Computed Spectrogram for {source_column} "
                f"(segment={spectrogram_result.segment_length}, fs={spectrogram_result.sampling_frequency:.1f} Hz)"
            )
            return
        elif analysis_name == "Welch PSD":
            result = compute_welch_psd(
                **common_kwargs,
                segment_length=int(workspace.welch_segment_length_var.get() or "256"),
                overlap_fraction=float(workspace.welch_overlap_fraction_var.get() or "0.5"),
            )
        elif analysis_name == "Transfer Estimate":
            result = compute_transfer_estimate(
                **common_kwargs,
                comparison_column=workspace.frequency_compare_var.get().strip(),
                segment_length=int(workspace.welch_segment_length_var.get() or "256"),
                overlap_fraction=float(workspace.welch_overlap_fraction_var.get() or "0.5"),
            )
        elif analysis_name == "Coherence":
            result = compute_coherence_spectrum(
                **common_kwargs,
                comparison_column=workspace.frequency_compare_var.get().strip(),
                segment_length=int(workspace.welch_segment_length_var.get() or "256"),
                overlap_fraction=float(workspace.welch_overlap_fraction_var.get() or "0.5"),
            )
        else:
            result = compute_fft_spectrum(**common_kwargs)
    if _failed:
        return

    unwrap_phase = (
        result.analysis_name == "Transfer Estimate"
        and bool(workspace.transfer_unwrap_phase_var.get())
    )
    workspace._render_fft_result(result, prepare_frequency_plot_values(result, unwrap_phase=unwrap_phase))
    workspace._latest_frequency_result = result
    diagnostics_callback = getattr(workspace, "_update_frequency_diagnostics", None)
    if diagnostics_callback is not None:
        diagnostics_callback(result)
    workspace.notifications.success(
        f"Computed {result.analysis_name} for {source_column} using {reference_column} with {result.window} window"
    )


def compute_cycle_analysis(workspace) -> None:
    """Read cycle-analysis UI state and run cycle detection + analysis."""
    source_column = workspace.active_column_var.get().strip()
    if not source_column:
        workspace.notifications.warning("Select an active analysis column")
        return

    cycle_mode = workspace.cycle_mode_var.get().strip() or "fixed_length"
    rule = get_rule("cycle", cycle_mode)
    if rule is not None:
        workspace_vars = {
            "cycle_length": workspace.cycle_length_var.get().strip(),
        }
        errors = validate_params(rule, workspace_vars)
        if errors:
            workspace.notifications.warning("Cycle Analysis validation failed", details="\n".join(errors))
            return

    time_column = workspace._get_cycle_time_column()

    with workspace._error_dialog("Cycle Analysis Error") as _failed:
        cycle_length = int(workspace.cycle_length_var.get().strip() or "0")
        max_cycles_text = workspace.cycle_max_cycles_var.get().strip()
        max_cycles = int(max_cycles_text) if max_cycles_text else None
        if cycle_mode == "rising_edge":
            reference_column = workspace.cycle_reference_var.get().strip() or "Index"
            threshold = float(workspace.cycle_threshold_var.get().strip() or "0.0")
            resolved_reference = source_column if reference_column == "Index" else reference_column
            cycle_ranges = detect_rising_edge_cycle_ranges(
                workspace.session.working_frame,
                reference_column=resolved_reference,
                threshold=threshold,
                min_cycle_length=cycle_length,
                max_cycles=max_cycles,
            )
            result = compute_cycle_analysis_from_ranges(
                workspace.session.working_frame,
                source_column=source_column,
                cycle_ranges=cycle_ranges,
                method="rising_edge",
                reference_column=resolved_reference,
                time_column=time_column,
            )
        elif cycle_mode == "zero_crossing":
            reference_column = workspace.cycle_reference_var.get().strip() or "Index"
            resolved_reference = source_column if reference_column == "Index" else reference_column
            cycle_ranges = detect_zero_crossing_cycle_ranges(
                workspace.session.working_frame,
                reference_column=resolved_reference,
                direction="rising",
                min_cycle_length=cycle_length,
                max_cycles=max_cycles,
            )
            result = compute_cycle_analysis_from_ranges(
                workspace.session.working_frame,
                source_column=source_column,
                cycle_ranges=cycle_ranges,
                method="zero_crossing",
                reference_column=resolved_reference,
                time_column=time_column,
            )
        elif cycle_mode == "peak":
            reference_column = workspace.cycle_reference_var.get().strip() or "Index"
            resolved_reference = source_column if reference_column == "Index" else reference_column
            prominence = float(workspace.cycle_prominence_var.get().strip() or "0.0")
            cycle_ranges = detect_peak_cycle_ranges(
                workspace.session.working_frame,
                reference_column=resolved_reference,
                min_cycle_length=cycle_length,
                prominence=prominence,
                max_cycles=max_cycles,
            )
            result = compute_cycle_analysis_from_ranges(
                workspace.session.working_frame,
                source_column=source_column,
                cycle_ranges=cycle_ranges,
                method="peak",
                reference_column=resolved_reference,
                time_column=time_column,
            )
        else:
            result = compute_fixed_length_cycle_analysis(
                workspace.session.working_frame,
                source_column=source_column,
                cycle_length=cycle_length,
                max_cycles=max_cycles,
                time_column=time_column,
            )
    if _failed:
        return

    workspace._render_cycle_result(result)
    workspace.notifications.success(
        f"Analyzed {result.cycle_count} cycles of length {result.cycle_length} for {source_column}"
    )
