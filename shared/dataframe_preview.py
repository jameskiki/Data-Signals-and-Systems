"""Shared Tk dataframe preview rendering helpers."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pandas as pd

from .column_roles import get_column_role, get_column_role_cell_colors, get_column_role_colors, get_column_role_label
from .display_format import format_display_value


def render_dataframe_preview(
    container: ttk.Frame,
    dataframe: pd.DataFrame,
    row_limit: int,
    column_roles: dict[str, str] | None = None,
    *,
    layout: str = "pack",
    empty_message: str | None = None,
) -> tk.Canvas | None:
    """Render a scrollable, role-colored preview of the first dataframe rows."""

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

    canvas = tk.Canvas(outer_frame, highlightthickness=0, borderwidth=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    vertical_scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
    vertical_scrollbar.grid(row=0, column=1, sticky="ns")
    horizontal_scrollbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=canvas.xview)
    _place_horizontal_scrollbar(horizontal_scrollbar, layout=layout)
    canvas.configure(yscrollcommand=vertical_scrollbar.set, xscrollcommand=horizontal_scrollbar.set)

    grid_frame = tk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

    _build_preview_cell(grid_frame, 0, 0, "#", "#eef2f6", "#444444", bold=True, anchor="center")
    for column_index, column_name in enumerate(columns, start=1):
        role_name = get_column_role(resolved_roles, column_name)
        background, foreground = get_column_role_colors(role_name)
        header_text = f"{column_name}\n[{get_column_role_label(resolved_roles, column_name)}]"
        _build_preview_cell(grid_frame, 0, column_index, header_text, background, foreground, bold=True, anchor="w")

    formatted_frame = preview_frame.astype(object).where(pd.notna(preview_frame), "")
    for row_index, row_values in enumerate(formatted_frame.itertuples(index=False, name=None), start=1):
        _build_preview_cell(grid_frame, row_index, 0, str(row_index - 1), "#eef2f6", "#444444", anchor="e")
        for column_index, value in enumerate(row_values, start=1):
            column_name = str(preview_frame.columns[column_index - 1])
            role_name = get_column_role(resolved_roles, column_name)
            background, foreground = get_column_role_cell_colors(role_name)
            _build_preview_cell(
                grid_frame,
                row_index,
                column_index,
                format_display_value(value),
                background,
                foreground,
                anchor="w",
            )

    def _sync_scroll_region(_event: tk.Event | None = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _sync_window_size(event: tk.Event) -> None:
        canvas.itemconfigure(window_id, height=max(event.height, grid_frame.winfo_reqheight()))

    grid_frame.bind("<Configure>", _sync_scroll_region)
    canvas.bind("<Configure>", _sync_window_size)
    if layout == "grid":
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
    _sync_scroll_region()
    return canvas


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


def _build_preview_cell(
    grid_frame: tk.Frame,
    row_index: int,
    column_index: int,
    text: str,
    background: str,
    foreground: str,
    bold: bool = False,
    anchor: str = "w",
) -> None:
    font = ("TkDefaultFont", 9, "bold") if bold else ("TkDefaultFont", 9)
    label = tk.Label(
        grid_frame,
        text=text,
        bg=background,
        fg=foreground,
        borderwidth=1,
        relief="solid",
        padx=6,
        pady=4,
        justify=tk.LEFT,
        anchor=anchor,
        font=font,
        wraplength=180,
    )
    label.grid(row=row_index, column=column_index, sticky="nsew")