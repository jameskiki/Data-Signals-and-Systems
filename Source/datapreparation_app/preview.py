"""Preview table helpers and plotting compatibility wrappers."""

import tkinter as tk
from tkinter import ttk

import pandas as pd

from Source.shared.dataframe_preview import render_dataframe_preview as render_shared_dataframe_preview

from .plotting import (
    clear_preview_plot,
    get_preview_plot_columns,
    get_selected_preview_plot_columns,
    handle_preview_plot_control_changed,
    refresh_preview_plot,
    refresh_preview_plot_signal_controls,
    refresh_selected_dataset_preview_plot,
)

def refresh_preview_table(app, dataframe: pd.DataFrame, row_limit: int, column_roles: dict[str, str] | None = None) -> None:
    """Render the dataframe head preview table."""

    if app._preview_table_container is None:
        return

    render_shared_dataframe_preview(
        app._preview_table_container,
        dataframe,
        row_limit,
        column_roles,
        layout="grid",
        empty_message="The dataset is empty.",
    )


def clear_preview_table(app, message: str | None = None) -> None:
    """Clear the preview table area and optionally show a message."""

    if app._preview_table_container is None:
        return

    for widget in app._preview_table_container.winfo_children():
        widget.destroy()
    if message:
        ttk.Label(app._preview_table_container, text=message, justify=tk.LEFT).pack(anchor="w", padx=5, pady=5)


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

