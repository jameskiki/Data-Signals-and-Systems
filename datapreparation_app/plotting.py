"""Plot dialog and figure window helpers for the main application."""


import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd
import tkinter as tk
from tkinter import ttk

from Source.shared.plot_options import PlotOptions

class PlotOptionsDialog:
    """Modal dialog for choosing plot columns and axis options."""

    def __init__(self, parent: tk.Tk, df: pd.DataFrame, window_title: str) -> None:
        self.parent = parent
        self.df = df
        self.window_title = window_title
        self.result: PlotOptions | None = None

    def show(self) -> PlotOptions | None:
        cols = list(self.df.columns)
        if not cols:
            return None

        default_xcol = self._detect_default_xcol(cols)
        dialog = tk.Toplevel(self.parent)
        dialog.title(self.window_title + " Options")
        dialog.grab_set()
        dialog.resizable(True, True)

        row = 0
        tk.Label(dialog, text="Select columns to plot:").grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))
        row += 1

        cols_listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=0, height=min(8, len(cols)))
        for col in cols:
            cols_listbox.insert(tk.END, col)
        cols_listbox.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0, 2))
        row += 1

        tk.Label(dialog, text="Select x-axis column:").grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 0))
        row += 1

        xcol_var = tk.StringVar(value=default_xcol)
        ttk.Combobox(dialog, textvariable=xcol_var, values=["Index"] + cols, state="readonly").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
            pady=(0, 2),
        )
        row += 1

        use_subplots_var = tk.BooleanVar(value=True)
        tk.Checkbutton(dialog, text="Subplots", variable=use_subplots_var).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(2, 0)
        )
        row += 1

        def on_ok() -> None:
            selected_indices = cols_listbox.curselection()
            ycols = cols.copy() if not selected_indices else [cols[index] for index in selected_indices]
            xcol = xcol_var.get() if xcol_var.get() in cols or xcol_var.get() == "Index" else default_xcol
            if xcol != "Index":
                ycols = [col for col in ycols if col != xcol]
            if not ycols:
                ycols = [col for col in cols if col != xcol]
            self.result = PlotOptions(
                cols_to_plot=ycols,
                xcol=xcol,
                use_subplots=use_subplots_var.get(),
            )
            dialog.destroy()

        def on_cancel() -> None:
            self.result = None
            dialog.destroy()

        tk.Button(dialog, text="OK", command=on_ok).grid(row=row, column=0, padx=10, pady=8, sticky="e")
        tk.Button(dialog, text="Cancel", command=on_cancel).grid(row=row, column=1, padx=10, pady=8, sticky="w")

        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(1, weight=1)
        dialog.wait_window()
        return self.result

    def _detect_default_xcol(self, cols: list[str]) -> str:
        for col in cols:
            if pd.api.types.is_datetime64_any_dtype(self.df[col]) or any(
                token in col.lower() for token in ["time", "date", "timestamp"]
            ):
                return col
        return "Index"


def show_figure_in_window(root: tk.Tk, figure: plt.Figure, window_title: str, window_geometry: str) -> None:
    """Show a matplotlib figure in a separate Tk window."""

    window = tk.Toplevel(root)
    window.title(window_title)
    window.geometry(window_geometry)
    container = ttk.Frame(window)
    container.pack(fill=tk.BOTH, expand=True)
    canvas = FigureCanvasTkAgg(figure, master=container)
    canvas.draw()
    toolbar = NavigationToolbar2Tk(canvas, container)
    toolbar.update()
    toolbar.pack(side=tk.TOP, fill=tk.X)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)

    resize_job: str | None = None

    def _sync_canvas_size() -> None:
        widget = canvas.get_tk_widget()
        widget.update_idletasks()
        width = max(widget.winfo_width(), 1)
        height = max(widget.winfo_height(), 1)
        dpi = float(figure.get_dpi() or 100.0)
        figure.set_size_inches(width / dpi, height / dpi, forward=True)
        canvas.draw_idle()

    def _on_configure(event: tk.Event) -> None:
        nonlocal resize_job
        if event.widget is not container:
            return
        if resize_job is not None:
            window.after_cancel(resize_job)
        resize_job = window.after(150, _sync_canvas_size)

    container.bind("<Configure>", _on_configure)
    window.after_idle(_sync_canvas_size)

    def _on_close() -> None:
        plt.close(figure)
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", _on_close)
