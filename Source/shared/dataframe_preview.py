"""Shared Tk dataframe preview rendering helpers."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pandas as pd

from .column_roles import get_column_role_label
from .display_format import format_display_value


def render_dataframe_preview(
    container: ttk.Frame,
    dataframe: pd.DataFrame,
    row_limit: int,
    column_roles: dict[str, str] | None = None,
    *,
    layout: str = "pack",
    empty_message: str | None = None,
) -> ttk.Treeview | None:
    """Render a scrollable preview of the first dataframe rows.

    Uses a single Treeview widget instead of individual Label cells so that only
    one Win32 HWND is allocated regardless of the number of rows or columns.
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

    tree = ttk.Treeview(outer_frame, columns=columns, show="headings", selectmode="none")
    tree.grid(row=0, column=0, sticky="nsew")

    v_scroll = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=tree.yview)
    v_scroll.grid(row=0, column=1, sticky="ns")
    h_scroll = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=tree.xview)
    _place_horizontal_scrollbar(h_scroll, layout=layout)
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    for col_name in columns:
        role_label = get_column_role_label(resolved_roles, col_name)
        tree.heading(col_name, text=f"{col_name} [{role_label}]")
        tree.column(col_name, width=140, minwidth=60, stretch=False)

    formatted_frame = preview_frame.astype(object).where(pd.notna(preview_frame), "")
    for row_values in formatted_frame.itertuples(index=False, name=None):
        tree.insert("", "end", values=tuple(format_display_value(v) for v in row_values))

    if layout == "grid":
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

    return tree


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
