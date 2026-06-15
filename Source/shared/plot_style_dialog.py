"""Reusable plot-style dialog for all Tk apps in this project."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk


def open_plot_style_dialog(owner, root_window: tk.Misc, on_apply: Callable[[], None]) -> None:
    """Open a non-modal plot-style dialog for an app-like owner object."""

    existing = getattr(owner, "_style_dialog", None)
    if existing is not None:
        try:
            existing.lift()
            existing.focus_force()
            return
        except tk.TclError:
            pass

    legend_locations = [
        "best", "upper right", "upper left", "lower right", "lower left",
        "upper center", "lower center", "center left", "center right", "center",
    ]
    markers = ["o", "s", "^", "v", "D", "+", "x", ".", "None"]
    font_families = ["sans-serif", "serif", "monospace"]

    style_vars = owner.style_vars

    dialog = tk.Toplevel(root_window)
    dialog.title("Plot Style")
    dialog.resizable(False, False)
    owner._style_dialog = dialog

    def _on_close() -> None:
        style_vars.save_to_file()
        owner._style_dialog = None
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", _on_close)

    pad = {"padx": 8, "pady": 4}
    content = ttk.Frame(dialog, padding=10)
    content.pack(fill=tk.BOTH, expand=True)

    check_row = ttk.Frame(content)
    check_row.grid(row=0, column=0, columnspan=2, sticky="w", **pad)
    ttk.Checkbutton(check_row, text="Grid", variable=style_vars.show_grid).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Checkbutton(check_row, text="Subgrid", variable=style_vars.show_subgrid).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Checkbutton(check_row, text="Legend", variable=style_vars.show_legend).pack(side=tk.LEFT)

    ttk.Separator(content, orient=tk.HORIZONTAL).grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))
    ttk.Label(content, text="Grid alpha").grid(row=2, column=0, sticky="w", padx=8, pady=2)
    ttk.Scale(content, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=style_vars.grid_alpha, length=200).grid(
        row=2,
        column=1,
        sticky="ew",
        padx=8,
        pady=2,
    )
    ttk.Label(content, text="Subgrid alpha").grid(row=3, column=0, sticky="w", padx=8, pady=2)
    ttk.Scale(content, from_=0.0, to=1.0, orient=tk.HORIZONTAL, variable=style_vars.subgrid_alpha, length=200).grid(
        row=3,
        column=1,
        sticky="ew",
        padx=8,
        pady=2,
    )

    ttk.Separator(content, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))
    vcmd_float = (dialog.register(lambda value: _validate_float(value, 0.1, 50.0)), "%P")
    ttk.Label(content, text="Line width").grid(row=5, column=0, sticky="w", padx=8, pady=2)
    ttk.Spinbox(
        content,
        from_=0.1,
        to=10.0,
        increment=0.1,
        width=8,
        textvariable=style_vars.line_width,
        validate="focusout",
        validatecommand=vcmd_float,
    ).grid(row=5, column=1, sticky="w", padx=8, pady=2)
    ttk.Label(content, text="Marker size").grid(row=6, column=0, sticky="w", padx=8, pady=2)
    ttk.Spinbox(
        content,
        from_=0.5,
        to=20.0,
        increment=0.5,
        width=8,
        textvariable=style_vars.marker_size,
        validate="focusout",
        validatecommand=vcmd_float,
    ).grid(row=6, column=1, sticky="w", padx=8, pady=2)

    ttk.Separator(content, orient=tk.HORIZONTAL).grid(row=7, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))
    vcmd_int = (dialog.register(lambda value: _validate_int(value, 4, 32)), "%P")
    for row_offset, (label, var) in enumerate(
        [
            ("Title fontsize", style_vars.title_fontsize),
            ("Label fontsize", style_vars.label_fontsize),
            ("Tick fontsize", style_vars.tick_fontsize),
            ("Legend fontsize", style_vars.legend_fontsize),
        ]
    ):
        ttk.Label(content, text=label).grid(row=8 + row_offset, column=0, sticky="w", padx=8, pady=2)
        ttk.Spinbox(
            content,
            from_=4,
            to=32,
            increment=1,
            width=8,
            textvariable=var,
            validate="focusout",
            validatecommand=vcmd_int,
        ).grid(row=8 + row_offset, column=1, sticky="w", padx=8, pady=2)

    ttk.Separator(content, orient=tk.HORIZONTAL).grid(row=12, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))
    ttk.Label(content, text="Font family").grid(row=13, column=0, sticky="w", padx=8, pady=2)
    ttk.Combobox(content, textvariable=style_vars.font_family, values=font_families, state="readonly", width=14).grid(
        row=13,
        column=1,
        sticky="w",
        padx=8,
        pady=2,
    )
    ttk.Label(content, text="Marker").grid(row=14, column=0, sticky="w", padx=8, pady=2)
    ttk.Combobox(content, textvariable=style_vars.marker, values=markers, state="readonly", width=14).grid(
        row=14,
        column=1,
        sticky="w",
        padx=8,
        pady=2,
    )
    ttk.Label(content, text="Legend position").grid(row=15, column=0, sticky="w", padx=8, pady=2)
    ttk.Combobox(
        content,
        textvariable=style_vars.legend_location,
        values=legend_locations,
        state="readonly",
        width=14,
    ).grid(row=15, column=1, sticky="w", padx=8, pady=2)

    ttk.Separator(content, orient=tk.HORIZONTAL).grid(row=16, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
    btn_row = ttk.Frame(content)
    btn_row.grid(row=17, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 4))

    def _apply() -> None:
        style_vars.save_to_file()
        on_apply()

    ttk.Button(btn_row, text="Reset to Defaults", command=style_vars.reset_to_defaults).pack(side=tk.LEFT)
    ttk.Button(btn_row, text="Apply", command=_apply).pack(side=tk.RIGHT)
    ttk.Button(btn_row, text="Close", command=_on_close).pack(side=tk.RIGHT, padx=(0, 6))

    content.columnconfigure(1, weight=1)


def _validate_float(value: str, lo: float, hi: float) -> bool:
    """Spinbox focusout validator for float input in [lo, hi]."""

    try:
        return lo <= float(value) <= hi
    except (ValueError, TypeError):
        return False


def _validate_int(value: str, lo: int, hi: int) -> bool:
    """Spinbox focusout validator for integer input in [lo, hi]."""

    try:
        return lo <= int(value) <= hi
    except (ValueError, TypeError):
        return False