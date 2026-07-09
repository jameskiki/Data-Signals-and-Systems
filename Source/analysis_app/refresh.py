"""UI refresh helpers for the analysis workspace."""

import os

import numpy as np
import pandas as pd

from .actions import resolve_default_output_names
from Source.shared.display_format import format_data_summary_overview
from Source.shared.column_roles import (
    apply_role_combobox_style,
    get_column_role,
    get_preferred_role_column,
    summarize_column_roles,
)


def refresh_sidebar(workspace) -> None:
    """Refresh dataset summary labels in the sidebar."""

    original_rows, original_columns = workspace.session.original_frame.shape
    working_rows, working_columns = workspace.session.working_frame.shape
    numeric_columns = len(workspace.session.working_frame.select_dtypes(include="number").columns)

    workspace.dataset_label_var.set(os.path.basename(workspace.session.source_path))
    workspace.original_shape_var.set(f"Original shape: {original_rows} rows x {original_columns} columns")
    workspace.working_shape_var.set(f"Working shape: {working_rows} rows x {working_columns} columns")
    workspace.numeric_columns_var.set(f"Numeric columns available: {numeric_columns}")
    workspace.role_summary_var.set(summarize_column_roles(workspace.column_roles))





def refresh_overview(workspace) -> None:
    """Refresh the overview text block."""

    overview_text = format_data_summary_overview(workspace.session.last_summary) if workspace.session.last_summary else ""

    workspace.sidebar_overview_text.config(state="normal")
    workspace.sidebar_overview_text.delete("1.0", "end")
    workspace.sidebar_overview_text.insert("end", overview_text)
    workspace.sidebar_overview_text.config(state="disabled")


def refresh_filter_controls(workspace) -> None:
    """Refresh column-dependent filter and derived-signal controls."""

    columns = [str(column) for column in workspace.session.working_frame.columns]
    numeric_columns = [str(column) for column in workspace.session.working_frame.select_dtypes(include="number").columns]
    workspace.active_column_combo.config(values=numeric_columns or columns)
    preferred_active = get_preferred_role_column(
        workspace.column_roles,
        "output",
        "signal",
        "input",
        available_columns=numeric_columns,
    ) or (numeric_columns[0] if numeric_columns else (columns[0] if columns else ""))
    if preferred_active and workspace.active_column_var.get() not in (numeric_columns or columns):
        workspace.active_column_var.set(preferred_active)

    reference_values = ["Index", *columns]
    workspace.derived_reference_combo.config(values=reference_values)
    if workspace.derived_reference_var.get() not in reference_values:
        workspace.derived_reference_var.set("Index")
    workspace.fft_reference_combo.config(values=reference_values)
    if workspace.fft_reference_var.get() not in reference_values:
        workspace.fft_reference_var.set(get_preferred_role_column(workspace.column_roles, "time", available_columns=columns) or "Index")
    workspace.cycles_reference_combo.config(values=reference_values)
    if workspace.cycle_reference_var.get() not in reference_values:
        workspace.cycle_reference_var.set(get_preferred_role_column(workspace.column_roles, "time", available_columns=columns) or "Index")

    if getattr(workspace, "resample_time_combo", None) is not None:
        workspace.resample_time_combo.config(values=columns)
        if workspace.resample_time_var.get() not in columns:
            workspace.resample_time_var.set(
                get_preferred_role_column(workspace.column_roles, "time", available_columns=columns) or (columns[0] if columns else "")
            )

    if getattr(workspace, "frequency_compare_combo", None) is not None:
        workspace.frequency_compare_combo.config(values=numeric_columns or columns)
        comparison_value = workspace.frequency_compare_var.get()
        preferred_compare = get_preferred_role_column(
            workspace.column_roles,
            "input",
            "signal",
            "output",
            available_columns=[column for column in numeric_columns if column != workspace.active_column_var.get()],
        ) or next((column for column in numeric_columns if column != workspace.active_column_var.get()), "")
        if comparison_value not in numeric_columns:
            comparison_value = preferred_compare
            workspace.frequency_compare_var.set(comparison_value)
        elif comparison_value == workspace.active_column_var.get() and len(numeric_columns) > 1:
            fallback = preferred_compare or comparison_value
            if fallback != comparison_value:
                workspace.frequency_compare_var.set(fallback)

    _apply_default_sample_spacing(workspace, columns)
    _apply_default_analysis_lengths(workspace, numeric_columns)

    set_default_output_names(workspace)
    if hasattr(workspace, "_refresh_frequency_method_controls"):
        workspace._refresh_frequency_method_controls()
    refresh_role_widget_styles(workspace)


def _apply_default_sample_spacing(workspace, columns: list[str]) -> None:
    """Infer and set spacing defaults when fields are unset or invalid."""

    time_column = get_preferred_role_column(workspace.column_roles, "time", available_columns=columns)
    if not time_column:
        return

    inferred_spacing = infer_sample_spacing(workspace.session.working_frame, time_column)
    if inferred_spacing is None:
        return

    inferred_text = _format_spacing(inferred_spacing)
    signal_spacing = _parse_positive_float(workspace.signal_filter_spacing_var.get())
    if signal_spacing is None:
        _set_inferred_field(workspace, "signal_filter_spacing", workspace.signal_filter_spacing_var, inferred_text)

    if not _is_user_set(workspace, "fft_sample_spacing"):
        _set_inferred_field(workspace, "fft_sample_spacing", workspace.fft_sample_spacing_var, inferred_text)

    if getattr(workspace, "resample_time_var", None) is None:
        return

    resample_time_column = workspace.resample_time_var.get().strip()
    if not resample_time_column or resample_time_column == "Index":
        return

    if _is_user_set(workspace, "resample_spacing"):
        return

    inferred_resample_spacing = infer_sample_spacing(workspace.session.working_frame, resample_time_column)
    if inferred_resample_spacing is not None:
        _set_inferred_field(
            workspace,
            "resample_spacing",
            workspace.resample_spacing_var,
            _format_spacing(inferred_resample_spacing),
        )


def infer_sample_spacing(dataframe: pd.DataFrame, time_column: str) -> float | None:
    """Infer representative spacing from a time/reference column using median diff."""

    if time_column not in dataframe.columns:
        return None

    reference_series = dataframe[time_column]
    if pd.api.types.is_datetime64_any_dtype(reference_series):
        numeric_reference = reference_series.astype("datetime64[ns]").astype("int64") / 1_000_000_000.0
    else:
        numeric_reference = pd.to_numeric(reference_series, errors="coerce")

    diffs = pd.Series(numeric_reference).diff().dropna()
    if diffs.empty:
        return None

    spacing = float(np.median(np.abs(diffs.to_numpy(dtype=float))))
    if not np.isfinite(spacing) or spacing <= 0:
        return None
    return spacing


def _parse_positive_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _set_inferred_field(workspace, field_name: str, variable, value: str) -> None:
    if hasattr(workspace, "_set_inferred_field_value"):
        workspace._set_inferred_field_value(field_name, variable, value)
        return
    variable.set(value)


def _is_user_set(workspace, field_name: str) -> bool:
    """Return True when the field has been explicitly edited by the user.

    A field is user-set only when it appears in _user_edited_fields — a separate
    set populated only by real user edits (not by inference writes).  A field that
    is in neither set is still at its factory default and should be inferred.
    """
    user_edited = getattr(workspace, "_user_edited_fields", None)
    if user_edited is None:
        return False
    return field_name in user_edited


def _format_spacing(value: float) -> str:
    return f"{value:.6g}"


def _apply_default_analysis_lengths(workspace, numeric_columns: list[str]) -> None:
    """Infer Welch and fixed-cycle lengths when fields are unset or still at factory defaults."""

    active_column = workspace.active_column_var.get().strip()
    if active_column not in numeric_columns:
        return

    series = pd.to_numeric(workspace.session.working_frame[active_column], errors="coerce").dropna()
    sample_count = int(series.size)
    if sample_count < 4:
        return

    welch_text = workspace.welch_segment_length_var.get().strip()
    welch_value = _parse_positive_int(welch_text)
    inferred_welch = infer_welch_segment_length(sample_count)
    if inferred_welch is not None and (welch_value is None or welch_text == "256"):
        _set_inferred_field(
            workspace,
            "welch_segment_length",
            workspace.welch_segment_length_var,
            str(inferred_welch),
        )

    cycle_text = workspace.cycle_length_var.get().strip()
    cycle_value = _parse_positive_int(cycle_text)
    inferred_cycle = infer_cycle_length_samples(series)
    if inferred_cycle is not None and (cycle_value is None or cycle_text == "100"):
        _set_inferred_field(
            workspace,
            "cycle_length",
            workspace.cycle_length_var,
            str(inferred_cycle),
        )


def infer_welch_segment_length(sample_count: int) -> int | None:
    """Infer a practical Welch segment length from available sample count."""

    if sample_count < 4:
        return None

    target = min(256, int(sample_count))
    power = 1
    while power * 2 <= target:
        power *= 2
    if power < 4:
        power = 4
    if power % 2 == 1:
        power -= 1
    return max(4, power)


def infer_cycle_length_samples(series: pd.Series) -> int | None:
    """Infer cycle length in samples from dominant spectral period of one signal."""

    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    sample_count = int(values.size)
    if sample_count < 8:
        return None

    centered = values - np.nanmean(values)
    if not np.isfinite(centered).all() or np.allclose(centered, 0.0):
        return None

    window = np.hanning(sample_count)
    amplitudes = np.abs(np.fft.rfft(centered * window))
    if amplitudes.size <= 2:
        return None
    amplitudes[0] = 0.0

    dominant_index = int(np.argmax(amplitudes))
    if dominant_index <= 0:
        return None

    background = np.median(amplitudes[1:])
    if not np.isfinite(background):
        return None
    if amplitudes[dominant_index] < max(1e-12, 3.0 * background):
        return None

    period_samples = int(round(sample_count / dominant_index))
    if period_samples < 2:
        return None
    return min(period_samples, sample_count // 2)


def _parse_positive_int(value: str) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def refresh_plot_controls(workspace) -> None:
    """Refresh plot axis and series selection controls."""

    columns = [str(column) for column in workspace.session.working_frame.columns]
    x_values = ["Index", *columns]
    workspace.plot_x_combo.config(values=x_values)
    if workspace.plot_x_var.get() not in x_values:
        workspace.plot_x_var.set(get_preferred_role_column(workspace.column_roles, "time", available_columns=columns) or "Index")
    workspace.session.selected_x_column = workspace.plot_x_var.get()
    workspace.plot_subplots_var.set(workspace.session.use_subplots)

    numeric_columns = list(workspace.session.working_frame.select_dtypes(include="number").columns)
    numeric_column_names = [str(column) for column in numeric_columns]

    selected_columns = [column for column in workspace.session.selected_y_columns if column in numeric_column_names]
    if not selected_columns and numeric_column_names:
        preferred_active = workspace.active_column_var.get() if workspace.active_column_var.get() in numeric_column_names else None
        selected_columns = [preferred_active] if preferred_active else []
        active_role = get_column_role(workspace.column_roles, preferred_active) if preferred_active else "metadata"
        companion_columns = [column for column in numeric_column_names if column != preferred_active]
        companion_role_order = ("output", "signal", "input") if active_role == "input" else ("input", "signal", "output")
        preferred_companion = get_preferred_role_column(
            workspace.column_roles,
            *companion_role_order,
            available_columns=companion_columns,
        )
        if preferred_companion and preferred_companion not in selected_columns:
            selected_columns.append(preferred_companion)
        if not selected_columns:
            selected_columns = numeric_column_names[: min(2, len(numeric_column_names))]
    workspace._set_plot_y_column_options(numeric_column_names, selected_columns)
    workspace.session.selected_y_columns = [str(column) for column in selected_columns]
    refresh_role_widget_styles(workspace)


def refresh_role_widget_styles(workspace) -> None:
    """Apply role-aware colors to key selection widgets."""

    apply_role_combobox_style(workspace.active_column_combo, workspace.column_roles, workspace.active_column_var.get().strip())
    apply_role_combobox_style(workspace.plot_x_combo, workspace.column_roles, workspace.plot_x_var.get().strip())
    apply_role_combobox_style(
        workspace.derived_reference_combo,
        workspace.column_roles,
        workspace.derived_reference_var.get().strip(),
    )
    apply_role_combobox_style(workspace.fft_reference_combo, workspace.column_roles, workspace.fft_reference_var.get().strip())
    apply_role_combobox_style(workspace.cycles_reference_combo, workspace.column_roles, workspace.cycle_reference_var.get().strip())
    apply_role_combobox_style(
        workspace.frequency_compare_combo,
        workspace.column_roles,
        workspace.frequency_compare_var.get().strip(),
    )


def set_default_output_names(workspace) -> None:
    """Set default output names without overwriting user-provided values."""

    filter_name, signal_name, derived_name = resolve_default_output_names(
        active_column=workspace.active_column_var.get().strip(),
        filter_output_name=workspace.filter_output_name_var.get(),
        signal_filter_name=workspace.signal_filter_name_var.get(),
        derived_name=workspace.derived_name_var.get(),
        derived_operation=workspace.derived_operation_var.get(),
    )
    workspace.filter_output_name_var.set(filter_name)
    workspace.signal_filter_name_var.set(signal_name)
    workspace.derived_name_var.set(derived_name)
