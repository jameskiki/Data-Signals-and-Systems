"""Operation handler functions for AnalysisWorkspace.

Each function takes the workspace as its first argument and reads UI state
(tk.StringVar values, etc.) directly from it, matching the pattern used in
datapreparation_app/actions.py.  The corresponding AnalysisWorkspace methods
are thin one-line delegations to these functions.
"""

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
    compute_spectrogram,
    compute_transfer_estimate,
    compute_welch_psd,
)

from .actions import (
    build_derived_signal_update,
    build_signal_filter_update,
    build_simple_filter_update,
)
from .rules import get_rule, validate_params
from .state import UI_FREQUENCY_ANALYSIS_METHODS


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
        role_overrides={output_column: workspace.column_roles.get(column, "signal")},
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
    cutoff_hz: float | list[float]
    if operation == "butterworth_bandpass":
        cutoff_hz = [
            float(workspace.signal_filter_cutoff_var.get() or "10.0"),
            float(workspace.signal_filter_cutoff_high_var.get() or "20.0"),
        ]
    else:
        cutoff_hz = float(workspace.signal_filter_cutoff_var.get() or "10.0")

    with workspace._error_dialog("Signal Filter Error") as _failed:
        update = build_signal_filter_update(
            workspace.session.working_frame,
            source_column=source_column,
            operation=operation,
            output_name=workspace.signal_filter_name_var.get(),
            window_size=int(workspace.signal_filter_window_var.get() or "5"),
            alpha=float(workspace.signal_filter_alpha_var.get() or "0.2"),
            cutoff_hz=cutoff_hz,
            sample_spacing=float(workspace.signal_filter_spacing_var.get() or "0.0"),
            filter_order=int(workspace.signal_filter_order_var.get() or "4"),
        )
    if _failed:
        return

    workspace._replace_working_frame(
        update.dataframe,
        role_overrides={output_column: workspace.column_roles.get(source_column, "signal")},
        focus_column=output_column,
    )
    workspace.notifications.success(f"Created {output_column} using {operation} on {source_column}")
    workspace.signal_filter_name_var.set("")


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

    derived_role = workspace.column_roles.get(source_column, "signal")
    if derived_role == "time":
        derived_role = "signal"
    workspace._replace_working_frame(
        update.dataframe,
        role_overrides={new_column: derived_role},
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
            workspace._render_spectrogram_result(spectrogram_result)
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

    workspace._render_fft_result(result)
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
