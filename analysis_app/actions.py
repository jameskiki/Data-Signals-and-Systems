"""Action helpers for analysis workspace operations."""

from dataclasses import dataclass

import pandas as pd

from data_ops.filtering import apply_simple_filter, resolve_filtered_column_name
from data_ops.signals import add_derived_column, apply_signal_filter


@dataclass(frozen=True)
class FrameUpdate:
    """A dataframe update plus its history description."""

    dataframe: pd.DataFrame
    history_entry: str


def build_simple_filter_update(
    dataframe: pd.DataFrame,
    active_column: str,
    output_name: str,
    minimum_value: str,
    maximum_value: str,
    keep_missing: bool,
) -> FrameUpdate:
    """Apply a simple filter and return the resulting dataframe update."""

    output_column = resolve_filtered_column_name(active_column, output_name)
    filtered_frame = apply_simple_filter(
        dataframe,
        source_column=active_column,
        new_column=output_column,
        minimum_value=minimum_value,
        maximum_value=maximum_value,
        keep_missing=keep_missing,
    )
    return FrameUpdate(
        dataframe=filtered_frame,
        history_entry=f"Created {output_column} from {active_column} using simple filtering",
    )


def build_signal_filter_update(
    dataframe: pd.DataFrame,
    source_column: str,
    operation: str,
    output_name: str,
    window_size: int,
    alpha: float,
    cutoff_hz: float = 1.0,
    sample_spacing: float = 0.0,
    filter_order: int = 4,
) -> FrameUpdate:
    """Apply a signal filter and return the resulting dataframe update."""

    output_column = resolve_filtered_column_name(source_column, output_name)
    filtered_frame = apply_signal_filter(
        dataframe,
        source_column=source_column,
        operation=operation,
        new_column=output_column,
        window_size=window_size,
        alpha=alpha,
        cutoff_hz=cutoff_hz,
        sample_spacing=sample_spacing,
        filter_order=filter_order,
    )
    return FrameUpdate(
        dataframe=filtered_frame,
        history_entry=f"Created {output_column} using {operation} on {source_column}",
    )


def build_derived_signal_update(
    dataframe: pd.DataFrame,
    source_column: str,
    operation: str,
    new_column: str,
    reference_column: str | None,
    window_size: int,
) -> FrameUpdate:
    """Create a derived signal and return the resulting dataframe update."""

    derived_frame = add_derived_column(
        dataframe,
        operation=operation,
        source_column=source_column,
        new_column=new_column,
        second_column=reference_column,
        window_size=window_size,
    )
    return FrameUpdate(
        dataframe=derived_frame,
        history_entry=f"Created {new_column} using {operation} on {source_column}",
    )


def build_reset_update(original_frame: pd.DataFrame) -> FrameUpdate:
    """Reset the working dataframe to its original state."""

    return FrameUpdate(
        dataframe=original_frame.copy(),
        history_entry="Reset working dataframe to the original loaded state",
    )


def resolve_default_output_names(
    active_column: str,
    filter_output_name: str,
    signal_filter_name: str,
    derived_name: str,
    derived_operation: str,
) -> tuple[str, str, str]:
    """Return default output names while preserving user-provided values."""

    if not active_column:
        return filter_output_name, signal_filter_name, derived_name

    resolved_filter_name = filter_output_name.strip() or resolve_filtered_column_name(active_column, "")
    resolved_signal_name = signal_filter_name.strip() or resolve_filtered_column_name(active_column, "")
    resolved_derived_name = derived_name.strip() or f"{active_column}_{derived_operation.strip()}"
    return resolved_filter_name, resolved_signal_name, resolved_derived_name
