"""Shared semantic column-role helpers used across the UI."""

from __future__ import annotations

import pandas as pd


COLUMN_ROLE_LABELS = {
    "time": "TIME",
    "signal": "SIGNAL",
    "metadata": "META",
}

COLUMN_ROLE_COLORS = {
    "time": ("#dbeafe", "#111111"),
    "signal": ("#f3e5f5", "#111111"),
    "metadata": ("#eceff1", "#111111"),
}

COLUMN_ROLE_PRIORITY = {
    "signal": 0,
    "metadata": 1,
    "time": 2,
}

COLUMN_ROLE_NAMES = list(COLUMN_ROLE_LABELS.keys())


def infer_column_roles(dataframe: pd.DataFrame, preferred_roles: dict[str, str] | None = None) -> dict[str, str]:
    """Infer lightweight semantic roles for dataframe columns."""

    preferred_roles = preferred_roles or {}
    column_roles: dict[str, str] = {}
    for column in dataframe.columns:
        column_name = str(column)
        if preferred_roles.get(column_name) in COLUMN_ROLE_NAMES:
            column_roles[column_name] = preferred_roles[column_name]
            continue
        column_roles[column_name] = _infer_column_role(column_name, dataframe[column])
    return column_roles


def project_column_roles(column_roles: dict[str, str], dataframe: pd.DataFrame) -> dict[str, str]:
    """Project stored roles onto a derived dataframe, re-inferring only new columns."""

    available_columns = {str(column) for column in dataframe.columns}
    preserved_roles = {str(column): role for column, role in column_roles.items() if str(column) in available_columns}
    return infer_column_roles(dataframe, preserved_roles)


def update_projected_column_roles(
    column_roles: dict[str, str],
    dataframe: pd.DataFrame,
    role_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Project roles to a new dataframe and apply any explicit role overrides."""

    updated_roles = project_column_roles(column_roles, dataframe)
    for column_name, role_name in (role_overrides or {}).items():
        if str(column_name) in dataframe.columns and role_name in COLUMN_ROLE_NAMES:
            updated_roles[str(column_name)] = role_name
    return updated_roles


def summarize_column_roles(column_roles: dict[str, str]) -> str:
    """Return a compact human-readable summary of stored column roles."""

    if not column_roles:
        return ""

    time_column = get_preferred_role_column(column_roles, "time")
    signal_columns = [column for column, role in column_roles.items() if role == "signal"]
    metadata_count = sum(1 for role in column_roles.values() if role == "metadata")

    summary_parts: list[str] = []
    if time_column:
        summary_parts.append(f"time={time_column}")
    if signal_columns:
        shown_signals = ", ".join(signal_columns[:3])
        if len(signal_columns) > 3:
            shown_signals += f", +{len(signal_columns) - 3} more"
        summary_parts.append(f"signals={shown_signals}")
    if metadata_count:
        summary_parts.append(f"metadata={metadata_count}")
    return "Categories: " + " | ".join(summary_parts)


def get_preferred_role_column(
    column_roles: dict[str, str],
    *roles: str,
    available_columns: list[str] | None = None,
) -> str | None:
    """Return the first column matching any preferred role and availability filter."""

    available_set = set(available_columns) if available_columns is not None else None
    for role in roles:
        for column, column_role in column_roles.items():
            if column_role != role:
                continue
            if available_set is not None and column not in available_set:
                continue
            return column
    return None


def get_column_role(column_roles: dict[str, str], column_name: str) -> str:
    """Return the stored role for one column, defaulting to metadata."""

    role = column_roles.get(str(column_name), "metadata")
    return role if role in COLUMN_ROLE_NAMES else "metadata"


def get_transformed_column_role(column_roles: dict[str, str], source_column: str) -> str:
    """Return the role inherited by a column produced from one source column."""

    source_role = get_column_role(column_roles, source_column)
    return "signal" if source_role == "time" else source_role


def get_column_role_label(column_roles: dict[str, str], column_name: str) -> str:
    """Return a short human-readable role label for one column."""

    role = get_column_role(column_roles, column_name)
    return COLUMN_ROLE_LABELS.get(role, role.upper())


def get_role_label(role: str) -> str:
    """Return the human-readable label for one role name."""

    return COLUMN_ROLE_LABELS.get(role, role.upper())


def get_available_column_roles() -> list[str]:
    """Return the supported semantic column role names in UI order."""

    return list(COLUMN_ROLE_NAMES)


def get_column_role_colors(role: str) -> tuple[str, str]:
    """Return background and foreground colors for one role."""

    return COLUMN_ROLE_COLORS.get(role, COLUMN_ROLE_COLORS["metadata"])


def get_column_role_cell_colors(role: str) -> tuple[str, str]:
    """Return a lighter color pair for table cell fills."""

    background, foreground = get_column_role_colors(role)
    return _lighten_hex(background, 0.72), foreground


def sort_columns_by_role(columns: list[str], column_roles: dict[str, str]) -> list[str]:
    """Sort columns by semantic role before falling back to name."""

    return sorted(
        [str(column) for column in columns],
        key=lambda column_name: (
            COLUMN_ROLE_PRIORITY.get(get_column_role(column_roles, column_name), len(COLUMN_ROLE_PRIORITY)),
            column_name.lower(),
        ),
    )


def infer_non_time_column_role(series: pd.Series) -> str:
    """Infer a signal or metadata role without considering time semantics."""

    return "signal" if pd.api.types.is_numeric_dtype(series) else "metadata"


def _lighten_hex(color: str, factor: float) -> str:
    color = color.lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    red = int(red + (255 - red) * factor)
    green = int(green + (255 - green) * factor)
    blue = int(blue + (255 - blue) * factor)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _infer_column_role(column_name: str, series: pd.Series) -> str:
    normalized_name = column_name.strip().lower()

    if pd.api.types.is_datetime64_any_dtype(series):
        return "time"
    if any(token in normalized_name for token in ("time", "timestamp", "datetime", "date")):
        return "time"
    if any(token in normalized_name for token in ("temp", "temperature", "phase", "marker", "status", "label", "id")):
        return "metadata"
    if pd.api.types.is_numeric_dtype(series):
        return "signal"
    return "metadata"