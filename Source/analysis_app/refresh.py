"""UI refresh helpers for the analysis workspace."""

import os

from .actions import resolve_default_output_names
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

    overview_text = workspace.session.last_summary.overview_text if workspace.session.last_summary else ""

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

    set_default_output_names(workspace)
    if hasattr(workspace, "_refresh_frequency_method_controls"):
        workspace._refresh_frequency_method_controls()
    refresh_role_widget_styles(workspace)


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
