"""Shared Tk dataframe preview rendering helpers."""

from __future__ import annotations

import pathlib
import re
import sys
import tkinter as tk
from tkinter import ttk
from typing import Protocol, cast

import pandas as pd

try:
    from .column_roles import get_column_role_label
    from .column_roles import get_column_role
    from .column_roles import get_column_role_cell_colors
    from .display_format import format_display_value
    from .table_adapter import create_table_adapter
except ImportError:
    workspace_root = pathlib.Path(__file__).resolve().parents[2]
    workspace_root_str = str(workspace_root)
    if workspace_root_str not in sys.path:
        sys.path.insert(0, workspace_root_str)
    from Source.shared.column_roles import get_column_role_label
    from Source.shared.column_roles import get_column_role
    from Source.shared.column_roles import get_column_role_cell_colors
    from Source.shared.display_format import format_display_value
    from Source.shared.table_adapter import create_table_adapter


class _ScrollableWidget(Protocol):
    def grid(self, **kwargs: object) -> object: ...

    def yview(self, *args: object) -> tuple[float, float] | None: ...

    def xview(self, *args: object) -> tuple[float, float] | None: ...

    def configure(self, **kwargs: object) -> object: ...

    def destroy(self) -> None: ...


def render_dataframe_preview(
    container: ttk.Frame,
    dataframe: pd.DataFrame,
    row_limit: int,
    column_roles: dict[str, str] | None = None,
    *,
    layout: str = "pack",
    empty_message: str | None = None,
    backend: str | None = None,
) -> tk.Widget | None:
    """Render a scrollable preview of the first dataframe rows.

    Uses a table widget adapter to support multiple backends (Treeview, tksheet, etc).
    The backend is selected via the optional *backend* override or the
    EVALDATA_TABLE_BACKEND environment variable.
    Defaults to ttk.Treeview for compatibility.
    """

    _clear_container(container)

    preview_frame = dataframe.head(row_limit)
    if preview_frame.empty:
        if empty_message:
            _render_empty_message(container, empty_message, layout=layout)
        return None

    columns = [str(column) for column in preview_frame.columns]
    resolved_roles = column_roles or {}

    outer_frame = ttk.Frame(container)
    _place_outer_frame(container, outer_frame, layout=layout)
    outer_frame.rowconfigure(0, weight=1)
    outer_frame.columnconfigure(0, weight=1)

    # Create adapter and configure widget
    adapter = create_table_adapter(outer_frame, selectmode="none", backend=backend)
    
    # Build column specs with headers and metadata
    column_specs = []
    for col_name in columns:
        role_label = get_column_role_label(resolved_roles, col_name)
        role_name = get_column_role(resolved_roles, col_name)
        role_bg, role_fg = get_column_role_cell_colors(role_name)
        column_specs.append({
            "label": _build_compact_header_label(col_name, role_label),
            "width": 120,
            "minwidth": 60,
            "anchor": "center",
            "heading_anchor": "center",
            "stretch": False,
            "bg": role_bg,
            "fg": role_fg,
        })
    
    adapter.configure_columns(columns, column_specs)

    # Insert data rows
    formatted_frame = preview_frame.astype(object).where(pd.notna(preview_frame), "")
    for row_values in formatted_frame.itertuples(index=False, name=None):
        adapter.insert_row(tuple(format_display_value(v) for v in row_values))

    # Set up scrollbars
    widget = cast(_ScrollableWidget, adapter.get_widget())
    widget.grid(row=0, column=0, sticky="nsew")
    if hasattr(widget, "set_header_height_lines") and any("\n" in spec.get("label", "") for spec in column_specs):
        # tksheet computes header geometry after the widget is laid out.
        # Apply multi-line header height only after grid() so line 2 is visible.
        widget.set_header_height_lines(2, redraw=False)
        if hasattr(widget, "redraw"):
            widget.redraw()
    v_scroll = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=widget.yview)
    v_scroll.grid(row=0, column=1, sticky="ns")
    h_scroll = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=widget.xview)
    _place_horizontal_scrollbar(h_scroll, layout=layout)
    try:
        widget.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    except tk.TclError:
        # Some widgets (for example tksheet) do not expose Tk's
        # -xscrollcommand / -yscrollcommand options and manage scrolling internally.
        v_scroll.destroy()
        h_scroll.destroy()

    if layout == "grid":
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

    return cast(tk.Widget, widget)


def _clear_container(container: ttk.Frame) -> None:
    for widget in container.winfo_children():
        widget.destroy()


def _place_outer_frame(container: ttk.Frame, frame: ttk.Frame, *, layout: str) -> None:
    if layout == "grid":
        frame.grid(row=0, column=0, sticky="nsew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        return
    frame.pack(fill=tk.BOTH, expand=True)


def _place_horizontal_scrollbar(scrollbar: ttk.Scrollbar, *, layout: str) -> None:
    if layout == "grid":
        scrollbar.grid(row=1, column=0, sticky="ew")
        return
    scrollbar.pack(side=tk.BOTTOM, fill=tk.X)


def _render_empty_message(container: ttk.Frame, message: str, *, layout: str) -> None:
    label = ttk.Label(container, text=message, justify=tk.LEFT)
    if layout == "grid":
        label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        container.columnconfigure(0, weight=1)
        return
    label.pack(anchor="w", padx=5, pady=5)


def _build_compact_header_label(column_name: str, role_label: str) -> str:
    """Build a compact multi-line header label.

    If a column name ends with a bracketed suffix (typically units), move the
    suffix to a second line. Otherwise, show the role label on line two.
    """

    match = re.fullmatch(r"\s*(.*?)\s*(\[[^\]]+\])\s*", column_name)
    if match:
        base_name = match.group(1).strip()
        suffix = match.group(2).strip()
        if base_name:
            return f"{base_name}\n{suffix}"
    return f"{column_name}\n[{role_label}]"
