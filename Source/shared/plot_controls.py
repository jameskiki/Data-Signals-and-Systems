"""Reusable Tk control builders for shared plot families."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable


@dataclass(frozen=True)
class TimeSeriesPlotControls:
    """Widget references returned by the shared time-series control builder."""

    frame: ttk.Frame
    x_combo: ttk.Combobox
    y_selector_button: ttk.Menubutton
    y_selector_menu: tk.Menu
    subplots_checkbutton: ttk.Checkbutton
    update_button: ttk.Button


def build_time_series_plot_controls(
    parent: tk.Misc,
    *,
    x_variable: tk.StringVar,
    y_summary_variable: tk.StringVar,
    subplots_variable: tk.BooleanVar,
    on_select_all: Callable[[], object],
    on_clear_selection: Callable[[], object],
    on_update: Callable[[], object],
) -> TimeSeriesPlotControls:
    """Build the canonical X/Y/layout controls for a time-series plot."""

    controls = ttk.Frame(parent)
    controls.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
    controls.columnconfigure(1, weight=1)

    ttk.Label(controls, text="X-axis").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    x_combo = ttk.Combobox(controls, textvariable=x_variable, state="readonly")
    x_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Y columns").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
    selector_row = ttk.Frame(controls)
    selector_row.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    selector_row.columnconfigure(0, weight=1)

    y_selector_button = ttk.Menubutton(
        selector_row,
        textvariable=y_summary_variable,
        direction="below",
    )
    y_selector_button.grid(row=0, column=0, sticky="ew")
    y_selector_menu = tk.Menu(y_selector_button, tearoff=0)
    y_selector_button.configure(menu=y_selector_menu)
    y_selector_button.state(["disabled"])

    selector_actions = ttk.Frame(selector_row)
    selector_actions.grid(row=0, column=1, sticky="e", padx=(8, 0))
    ttk.Button(selector_actions, text="All", width=6, command=on_select_all).pack(side=tk.LEFT)
    ttk.Button(selector_actions, text="None", width=6, command=on_clear_selection).pack(
        side=tk.LEFT,
        padx=(6, 0),
    )

    subplots_checkbutton = ttk.Checkbutton(controls, text="Subplots", variable=subplots_variable)
    subplots_checkbutton.grid(row=2, column=0, sticky="w", padx=5, pady=5)
    update_button = ttk.Button(controls, text="Update Plot", command=on_update)
    update_button.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    return TimeSeriesPlotControls(
        frame=controls,
        x_combo=x_combo,
        y_selector_button=y_selector_button,
        y_selector_menu=y_selector_menu,
        subplots_checkbutton=subplots_checkbutton,
        update_button=update_button,
    )
