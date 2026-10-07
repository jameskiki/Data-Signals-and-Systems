"""Shared CSV and Parquet export dialogs."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


DATASET_SAVE_FILE_TYPES = [
    ("CSV files", "*.csv"),
    ("Parquet files", "*.parquet"),
    ("All files", "*.*"),
]


def complete_dataset_save_path(path: str, selected_type: str) -> str:
    """Honor explicit extensions, adding the selected format only when absent."""

    if not path or os.path.splitext(path)[1]:
        return path
    extension = ".parquet" if selected_type == "Parquet files" else ".csv"
    return path + extension


def ask_dataset_save_path(parent: tk.Misc, title: str) -> str:
    selected_type = tk.StringVar(master=parent, value="CSV files")
    path = filedialog.asksaveasfilename(
        parent=parent,
        title=title,
        defaultextension="",
        filetypes=DATASET_SAVE_FILE_TYPES,
        typevariable=selected_type,
    )
    completed_path = complete_dataset_save_path(path, selected_type.get())
    if completed_path != path and os.path.exists(completed_path):
        if not messagebox.askyesno(
            "Confirm overwrite", f"Replace existing file?\n{completed_path}", parent=parent,
        ):
            return ""
    return completed_path


class DatasetExportFormatDialog(simpledialog.Dialog):
    """Select the format for a batch of dataset exports."""

    result: str | None = None

    def body(self, master):
        ttk.Label(master, text="Export format:").grid(row=0, column=0, padx=8, pady=8)
        self.format_var = tk.StringVar(master=master, value="csv")
        selector = ttk.Combobox(
            master, textvariable=self.format_var, values=("csv", "parquet"), state="readonly",
        )
        selector.grid(row=0, column=1, padx=8, pady=8)
        return selector

    def apply(self) -> None:
        self.result = self.format_var.get()
