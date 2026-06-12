"""Rules orchestrator for the analysis workspace.

Reads a resolved ParameterRule from rules.py and applies frame state,
widget enable/disable state, and stale-value correction to the workspace.

All Tk framework coupling lives here; rules.py stays Tk-free.
"""

from .rules import get_rule


# ---------------------------------------------------------------------------
# Public entry points — one per domain
# ---------------------------------------------------------------------------

def apply_frequency_method_rule(workspace) -> None:
    """Show/hide frequency-tab frames and update widget states for the current method."""
    from .state import UI_FREQUENCY_ANALYSIS_METHODS
    analysis_name = workspace.frequency_analysis_var.get().strip() or UI_FREQUENCY_ANALYSIS_METHODS[0]
    rule = get_rule("frequency", analysis_name)
    if rule is None:
        return
    _apply_frame_visibility(workspace, rule.show_frames, rule.hide_frames)
    _apply_widget_states(workspace, rule.enable_widgets, rule.disable_widgets)


def apply_signal_filter_rule(workspace) -> None:
    """Show/hide signal-filter frames and correct stale zero-valued params."""
    operation = workspace.signal_filter_operation_var.get().strip()
    rule = get_rule("signal_filter", operation)
    if rule is None:
        return
    _apply_frame_visibility(workspace, rule.show_frames, rule.hide_frames)
    _correct_stale_positive_values(workspace, rule)


def apply_cycle_method_rule(workspace) -> None:
    """Show/hide cycle-tab frames for the current cycle mode."""
    mode = workspace.cycle_mode_var.get().strip() or "fixed_length"
    rule = get_rule("cycle", mode)
    if rule is None:
        return
    _apply_frame_visibility(workspace, rule.show_frames, rule.hide_frames)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_frame_visibility(
    workspace,
    show_frames: tuple[str, ...],
    hide_frames: tuple[str, ...],
) -> None:
    for frame_name in hide_frames:
        frame = getattr(workspace, frame_name, None)
        if frame is not None:
            frame.grid_remove()
    for frame_name in show_frames:
        frame = getattr(workspace, frame_name, None)
        if frame is not None:
            frame.grid()


def _apply_widget_states(
    workspace,
    enable_widgets: tuple[str, ...],
    disable_widgets: tuple[str, ...],
) -> None:
    for widget_name in disable_widgets:
        widget = getattr(workspace, widget_name, None)
        if widget is not None:
            widget.state(["disabled"])
    for widget_name in enable_widgets:
        widget = getattr(workspace, widget_name, None)
        if widget is not None:
            widget.state(["!disabled"])


# Mapping from rule param name → workspace StringVar attribute name.
# Used for stale-value correction on the signal-filter domain.
_SIGNAL_FILTER_PARAM_TO_VAR: dict[str, str] = {
    "sample_spacing": "signal_filter_spacing_var",
    "cutoff_hz": "signal_filter_cutoff_var",
    "cutoff_hz_high": "signal_filter_cutoff_high_var",
    "filter_order": "signal_filter_order_var",
    "window_size": "signal_filter_window_var",
    "alpha": "signal_filter_alpha_var",
}


def _correct_stale_positive_values(workspace, rule) -> None:
    """Clear any required-positive params that still hold the sentinel zero default.

    When a user switches to a method that needs a positive value and the field
    currently holds "0.0" (the workspace initialisation default), clearing the
    field forces them to enter a valid value rather than silently passing zero
    into the computation.
    """
    for param in rule.required_positive:
        var_name = _SIGNAL_FILTER_PARAM_TO_VAR.get(param)
        if var_name is None:
            continue
        var = getattr(workspace, var_name, None)
        if var is None:
            continue
        try:
            if float(var.get() or "0") <= 0:
                var.set("")
        except (ValueError, TypeError):
            pass
