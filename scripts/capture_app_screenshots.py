"""Generate reproducible UI screenshots for the EvalData desktop app.

This script launches the Tkinter app, loads the deterministic demo dataset,
opens key views, and writes screenshots to the requested output directory.
"""

from __future__ import annotations

import argparse
import contextlib
from pathlib import Path
import sys
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Source.datapreparation_app.app import DataPreparationApp
from Source.shared.demo_catalog import CYCLE_VALIDATION_DEMO, SPECTRAL_REFERENCE_DEMO
from Source.shared.plot_options import PlotOptions
from Source.shared.plot_utils import create_plot_figure

try:
    from PIL import Image, ImageDraw, ImageGrab
except ImportError as error:  # pragma: no cover - runtime dependency check
    raise SystemExit(
        "Pillow is required for screenshot capture. Install it with: pip install Pillow"
    ) from error


SPECTRAL_SCREENSHOT_MAX_ROWS = 2500
CYCLE_SCREENSHOT_MAX_ROWS = 1800
CYCLE_SCREENSHOT_MAX_CYCLES = 12


def _focus_capture_window(window: tk.Misc, root: tk.Tk) -> None:
    """Bring one window to the foreground and keep it topmost briefly for capture."""

    window.lift()
    window.focus_force()
    window.attributes("-topmost", True)
    _pump_ui(root, 0.12)


def _pump_ui(root: tk.Tk, seconds: float = 0.2) -> None:
    """Process pending Tk events and wait a short moment for redraw."""

    end_time = time.time() + max(0.0, seconds)
    while time.time() < end_time:
        root.update_idletasks()
        root.update()
        time.sleep(0.02)


def _capture_widget(widget: tk.Misc, output_path: Path, padding: int = 8) -> None:
    """Capture one Tk widget rectangle and save it as a PNG image."""

    image = _grab_widget_image(widget, padding=padding)
    image.save(output_path)


def _grab_widget_image(widget: tk.Misc, padding: int = 8) -> Image.Image:
    """Capture one Tk widget rectangle and return the Pillow image."""

    toplevel = widget.winfo_toplevel()
    root = widget._root()  # tkinter internals: returns the Tk root for this widget
    _focus_capture_window(toplevel, root)
    widget.update_idletasks()
    x0 = widget.winfo_rootx() - padding
    y0 = widget.winfo_rooty() - padding
    x1 = widget.winfo_rootx() + widget.winfo_width() + padding
    y1 = widget.winfo_rooty() + widget.winfo_height() + padding
    return ImageGrab.grab(bbox=(x0, y0, x1, y1), all_screens=True)


def _reset_workspace_for_demo_capture(root: tk.Tk, workspace) -> None:
    """Reset the analysis workspace to the original demo frame before each method capture."""

    workspace._reset_working_data()
    _pump_ui(root, 0.25)


def _set_plot_columns_for_capture(root: tk.Tk, workspace, selected_columns: list[str]) -> None:
    """Force the live plot to show specific columns for demonstrative algorithm captures."""

    available_columns = set(str(column) for column in workspace.session.working_frame.columns)
    resolved_columns = [column for column in selected_columns if column in available_columns]
    if not resolved_columns:
        return

    workspace.plot_x_var.set("Index")
    workspace.plot_subplots_var.set(True)
    numeric_columns = [str(column) for column in workspace.session.working_frame.select_dtypes(include=["number"]).columns]
    workspace._set_plot_y_column_options(numeric_columns, resolved_columns)
    workspace.session.selected_x_column = "Index"
    workspace.session.selected_y_columns = resolved_columns
    workspace.session.use_subplots = True

    # Render the exact columns we want to demonstrate, independent of transient UI menu state.
    plot_options = PlotOptions(
        cols_to_plot=resolved_columns,
        xcol="Index",
        use_subplots=True,
        y_label="Value",
    )
    figure = create_plot_figure(
        plot_options,
        [workspace.session.source_path],
        {workspace.session.source_path: workspace.session.working_frame},
        column_roles=workspace.column_roles,
    )
    workspace._render_plot_figure(figure)
    _pump_ui(root, 0.2)


def _build_contact_sheet(
    title: str,
    entries: list[tuple[str, Image.Image]],
    output_path: Path,
    columns: int,
) -> None:
    """Compose a labeled contact sheet so many algorithm views fit in one file."""

    if not entries:
        raise RuntimeError(f"No entries provided for contact sheet '{title}'")

    margin = 24
    gap = 18
    title_h = 44
    label_h = 26

    tile_w = max(image.width for _, image in entries)
    tile_h = max(image.height for _, image in entries)
    rows = (len(entries) + columns - 1) // columns

    sheet_w = margin * 2 + columns * tile_w + (columns - 1) * gap
    sheet_h = margin * 2 + title_h + rows * (label_h + tile_h) + (rows - 1) * gap
    canvas = Image.new("RGB", (sheet_w, sheet_h), color=(244, 245, 247))
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, margin), title, fill=(22, 24, 29))

    for index, (label, image) in enumerate(entries):
        row = index // columns
        col = index % columns
        x = margin + col * (tile_w + gap)
        y = margin + title_h + row * (label_h + tile_h + gap)
        draw.rectangle((x, y, x + tile_w, y + label_h - 4), fill=(226, 229, 233), outline=(193, 198, 206))
        draw.text((x + 8, y + 4), label, fill=(33, 37, 43))

        target_x = x + (tile_w - image.width) // 2
        target_y = y + label_h + (tile_h - image.height) // 2
        canvas.paste(image, (target_x, target_y))
        draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), outline=(170, 176, 184), width=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _cancel_pending_after_jobs(root: tk.Tk) -> None:
    """Cancel pending Tk 'after' callbacks before destroying windows."""

    pending_jobs = root.tk.call("after", "info")
    if not pending_jobs:
        return
    if isinstance(pending_jobs, str):
        pending_jobs = (pending_jobs,)
    for job_id in pending_jobs:
        try:
            root.after_cancel(job_id)
        except tk.TclError:
            continue


def _install_tk_exception_filter(root: tk.Tk) -> None:
    """Ignore known teardown-time Tk callback races with destroyed widgets."""

    def _report_callback_exception(exc, value, tb) -> None:
        if exc is tk.TclError and "bad window path name" in str(value):
            return
        traceback.print_exception(exc, value, tb)

    root.report_callback_exception = _report_callback_exception


def _set_active_column_if_available(workspace, column_name: str) -> None:
    options = list(workspace.active_column_combo.cget("values")) if workspace.active_column_combo is not None else []
    if column_name in options:
        workspace.active_column_var.set(column_name)


def _set_frequency_reference_to_time_column(workspace) -> None:
    """Prefer a timestamp-like reference so frequency scaling uses real sample spacing."""

    if getattr(workspace, "fft_reference_combo", None) is None:
        return

    raw_values = list(workspace.fft_reference_combo.cget("values"))
    values = [str(value) for value in raw_values]
    lowered = {value.lower(): value for value in values}

    preferred_names = [
        "time_s",
        "timestamp",
        "time",
        "zeit",
        "zeitstempel",
    ]
    for preferred in preferred_names:
        if preferred in lowered:
            workspace.fft_reference_var.set(lowered[preferred])
            return

    for value in values:
        lowered_value = value.lower()
        if "time" in lowered_value or "stamp" in lowered_value or "zeit" in lowered_value:
            workspace.fft_reference_var.set(value)
            return


def _set_frequency_compare_column(workspace) -> None:
    """Prefer a real signal/input comparison column and avoid time/index columns."""

    if getattr(workspace, "frequency_compare_combo", None) is None:
        return

    compare_values = [str(value) for value in workspace.frequency_compare_combo.cget("values")]
    if not compare_values:
        return

    active_column = workspace.active_column_var.get().strip()
    role_candidates = [
        column_name
        for column_name, role_name in getattr(workspace, "column_roles", {}).items()
        if role_name in {"input", "signal", "output"}
    ]
    preferred_names = [
        "clean_signal",
        "actuator_input",
        "delayed_input",
        "response_signal",
        *role_candidates,
    ]

    for candidate in preferred_names:
        if candidate in compare_values and candidate != active_column:
            workspace.frequency_compare_var.set(candidate)
            return

    for candidate in compare_values:
        lowered_candidate = candidate.lower()
        if candidate == active_column:
            continue
        if lowered_candidate == "index" or "time" in lowered_candidate or "stamp" in lowered_candidate or "zeit" in lowered_candidate:
            continue
        workspace.frequency_compare_var.set(candidate)
        return

    for candidate in compare_values:
        if candidate != active_column:
            workspace.frequency_compare_var.set(candidate)
            return


def _shorten_dataset_for_screenshots(
    app: DataPreparationApp,
    dataset_path: str,
    *,
    max_rows: int,
    max_cycles: int | None = None,
) -> None:
    """Trim loaded demo data so screenshots emphasize readable local behavior."""

    dataframe = app.data_frames.get(dataset_path)
    if dataframe is None or dataframe.empty:
        return

    shortened = dataframe
    if max_cycles is not None and "true_cycle_index" in dataframe.columns:
        cycle_ids = [int(cycle_id) for cycle_id in dataframe["true_cycle_index"].dropna().unique()]
        cycle_ids.sort()
        if len(cycle_ids) > max_cycles:
            max_cycle_id = cycle_ids[max_cycles - 1]
            shortened = dataframe[dataframe["true_cycle_index"] <= max_cycle_id]

    if len(shortened) > max_rows:
        shortened = shortened.iloc[:max_rows]

    if len(shortened) == len(dataframe):
        return

    shortened = shortened.reset_index(drop=True).copy()
    if "time_s" in shortened.columns:
        first_time = float(shortened["time_s"].iloc[0])
        shortened["time_s"] = shortened["time_s"] - first_time
    app.data_frames[dataset_path] = shortened


def _capture_filtering_sheet(root: tk.Tk, workspace, output_path: Path) -> None:
    workspace.notebook.select(workspace.filter_tab)
    _set_active_column_if_available(workspace, "measured_signal")
    filter_subtabs = _find_notebook_with_tab_names(
        workspace.filter_tab,
        {"Signal Processing", "Resample", "Simple Filtering"},
    )

    entries: list[tuple[str, Image.Image]] = []

    _reset_workspace_for_demo_capture(root, workspace)
    workspace.notebook.select(workspace.filter_tab)
    _select_notebook_tab_by_prefix(filter_subtabs, "Simple Filtering")
    workspace.filter_min_var.set("0.15")
    workspace.filter_max_var.set("")
    output_column = "measured_signal_simple_demo"
    workspace.filter_output_name_var.set(output_column)
    workspace._apply_filter()
    _set_plot_columns_for_capture(root, workspace, ["measured_signal", output_column])
    _pump_ui(root, 0.25)
    entries.append(("simple_filter", _grab_widget_image(workspace.window)))

    signal_ops = [
        "moving_average",
        "median",
        "exponential_smoothing",
        "high_pass",
        "butterworth_lowpass",
        "butterworth_highpass",
        "butterworth_bandpass",
    ]
    for operation in signal_ops:
        _reset_workspace_for_demo_capture(root, workspace)
        _set_active_column_if_available(workspace, "measured_signal")
        workspace.notebook.select(workspace.filter_tab)
        _select_notebook_tab_by_prefix(filter_subtabs, "Signal Processing")
        workspace.signal_filter_operation_var.set(operation)
        output_column = f"measured_signal_{operation}_demo"
        workspace.signal_filter_name_var.set(output_column)
        workspace.signal_filter_spacing_var.set("0.002")
        workspace.signal_filter_window_var.set("21")
        workspace.signal_filter_alpha_var.set("0.2")
        workspace.signal_filter_cutoff_var.set("10.0")
        workspace.signal_filter_cutoff_high_var.set("40.0")
        workspace.signal_filter_order_var.set("4")
        workspace._apply_signal_filter()
        _set_plot_columns_for_capture(root, workspace, ["measured_signal", output_column])
        _pump_ui(root, 0.25)
        entries.append((operation, _grab_widget_image(workspace.window)))

    _reset_workspace_for_demo_capture(root, workspace)
    workspace.notebook.select(workspace.filter_tab)
    _select_notebook_tab_by_prefix(filter_subtabs, "Resample")
    workspace.resample_time_var.set("time_s")
    workspace.resample_spacing_var.set("0.001")
    workspace._apply_resample()
    _set_plot_columns_for_capture(root, workspace, ["measured_signal", "clean_signal"])
    _pump_ui(root, 0.25)
    entries.append(("resample_to_uniform", _grab_widget_image(workspace.window)))

    _build_contact_sheet(
        "Filtering Algorithms (Simple + Signal Processing)",
        entries,
        output_path,
        columns=2,
    )


def _capture_derived_sheet(root: tk.Tk, workspace, output_path: Path) -> None:
    workspace.notebook.select(workspace.derived_tab)
    _set_active_column_if_available(workspace, "measured_signal")

    operations = [
        "delta",
        "ratio",
        "rolling_mean",
        "derivative",
        "normalized",
        "detrend",
        "integrate",
        "rms_envelope",
        "hilbert_envelope",
    ]
    entries: list[tuple[str, Image.Image]] = []
    for operation in operations:
        _reset_workspace_for_demo_capture(root, workspace)
        _set_active_column_if_available(workspace, "measured_signal")
        workspace.notebook.select(workspace.derived_tab)
        workspace.derived_operation_var.set(operation)
        output_column = f"measured_signal_{operation}_demo"
        workspace.derived_name_var.set(output_column)
        workspace.derived_reference_var.set("time_s")
        workspace.derived_window_var.set("21")
        workspace._apply_derived_signal()
        _set_plot_columns_for_capture(root, workspace, ["measured_signal", output_column])
        _pump_ui(root, 0.25)
        entries.append((operation, _grab_widget_image(workspace.window)))

    _build_contact_sheet(
        "Derived Signal Algorithms",
        entries,
        output_path,
        columns=3,
    )


def _capture_frequency_sheet(root: tk.Tk, workspace, output_path: Path) -> None:
    _reset_workspace_for_demo_capture(root, workspace)
    workspace.notebook.select(workspace.frequency_tab)
    _set_active_column_if_available(workspace, "measured_signal")
    _set_frequency_reference_to_time_column(workspace)
    _set_frequency_compare_column(workspace)

    methods = [
        "FFT Amplitude",
        "Welch PSD",
        "Transfer Estimate",
        "Coherence",
        "Spectrogram",
    ]
    entries: list[tuple[str, Image.Image]] = []
    for method in methods:
        workspace.notebook.select(workspace.frequency_tab)
        workspace.frequency_analysis_var.set(method)
        _pump_ui(root, 0.2)
        workspace._compute_fft()
        _pump_ui(root, 0.7)
        entries.append((method.lower().replace(" ", "_"), _grab_widget_image(workspace.window)))

    _build_contact_sheet(
        "Frequency Algorithms",
        entries,
        output_path,
        columns=2,
    )


def _capture_cycles_sheet(root: tk.Tk, workspace, output_path: Path) -> None:
    _reset_workspace_for_demo_capture(root, workspace)
    workspace.notebook.select(workspace.cycles_tab)
    _set_active_column_if_available(workspace, "cycle_process")
    if workspace.cycles_reference_combo is not None:
        cycle_ref_values = list(workspace.cycles_reference_combo.cget("values"))
        if cycle_ref_values:
            workspace.cycle_reference_var.set("Index" if "Index" in cycle_ref_values else cycle_ref_values[0])

    modes = [
        "fixed_length",
        "rising_edge",
        "zero_crossing",
        "peak",
    ]
    entries: list[tuple[str, Image.Image]] = []
    for mode in modes:
        _reset_workspace_for_demo_capture(root, workspace)
        workspace.notebook.select(workspace.cycles_tab)
        workspace.cycle_mode_var.set(mode)
        workspace.cycle_max_cycles_var.set("")
        if mode == "rising_edge":
            _set_active_column_if_available(workspace, "cycle_process")
            if workspace.cycles_reference_combo is not None:
                workspace.cycle_reference_var.set("cycle_process")
            workspace.cycle_threshold_var.set("4.5")
            workspace.cycle_length_var.set("120")
        elif mode == "zero_crossing":
            _set_active_column_if_available(workspace, "cycle_process")
            if workspace.cycles_reference_combo is not None:
                workspace.cycle_reference_var.set("cycle_reference_zero")
            workspace.cycle_length_var.set("120")
        elif mode == "peak":
            _set_active_column_if_available(workspace, "cycle_process")
            if workspace.cycles_reference_combo is not None:
                workspace.cycle_reference_var.set("cycle_process")
            workspace.cycle_prominence_var.set("0.2")
            workspace.cycle_length_var.set("120")
        else:
            workspace.cycle_length_var.set("144")
        _pump_ui(root, 0.2)
        workspace._compute_cycle_analysis()
        _pump_ui(root, 0.6)
        entries.append((mode, _grab_widget_image(workspace.window)))

    _build_contact_sheet(
        "Cycle Algorithms",
        entries,
        output_path,
        columns=2,
    )


def _capture_cycles_workspace_raw(root: tk.Tk, workspace, output_path: Path) -> None:
    _reset_workspace_for_demo_capture(root, workspace)
    workspace.notebook.select(workspace.cycles_tab)
    _set_active_column_if_available(workspace, "cycle_process")
    _set_active_column_if_available(workspace, "trigger_pulse")
    if workspace.cycles_reference_combo is not None:
        cycle_ref_values = list(workspace.cycles_reference_combo.cget("values"))
        if "trigger_pulse" in cycle_ref_values:
            workspace.cycle_reference_var.set("trigger_pulse")
    _pump_ui(root, 0.3)
    _capture_widget(workspace.window, output_path)


def _iter_widgets(widget: tk.Misc):
    yield widget
    for child in widget.winfo_children():
        yield from _iter_widgets(child)


def _find_preview_notebook(app: DataPreparationApp) -> ttk.Notebook:
    """Locate the preview notebook that contains Plot and Table tabs."""

    for widget in _iter_widgets(app.root):
        if not isinstance(widget, ttk.Notebook):
            continue
        tab_names = {widget.tab(tab_id, "text") for tab_id in widget.tabs()}
        if "Plot" in tab_names and any(name.startswith("Table") for name in tab_names):
            return widget
    raise RuntimeError("Could not locate preview notebook for table screenshot")


def _find_notebook_with_tab_names(root_widget: tk.Misc, required_names: set[str]) -> ttk.Notebook:
    """Find a ttk.Notebook that contains all required tab names."""

    for widget in _iter_widgets(root_widget):
        if not isinstance(widget, ttk.Notebook):
            continue
        tab_names = {widget.tab(tab_id, "text") for tab_id in widget.tabs()}
        if required_names.issubset(tab_names):
            return widget
    raise RuntimeError(f"Could not locate notebook with tabs: {sorted(required_names)}")


def _select_notebook_tab_by_prefix(notebook: ttk.Notebook, tab_prefix: str) -> None:
    for tab_id in notebook.tabs():
        tab_text = notebook.tab(tab_id, "text")
        if tab_text.startswith(tab_prefix):
            notebook.select(tab_id)
            return
    raise RuntimeError(f"Could not find notebook tab starting with '{tab_prefix}'")


@contextlib.contextmanager
def _silence_messageboxes():
    """Prevent modal dialogs from interrupting automated screenshot runs."""

    original_showinfo = messagebox.showinfo
    original_showwarning = messagebox.showwarning
    original_showerror = messagebox.showerror
    messagebox.showinfo = lambda *args, **kwargs: None
    messagebox.showwarning = lambda *args, **kwargs: None
    messagebox.showerror = lambda *args, **kwargs: None
    try:
        yield
    finally:
        messagebox.showinfo = original_showinfo
        messagebox.showwarning = original_showwarning
        messagebox.showerror = original_showerror


def generate_screenshots(output_dir: Path) -> list[Path]:
    """Run the app and capture a compact screenshot set covering all algorithms."""

    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    with _silence_messageboxes():
        root = tk.Tk()
        _install_tk_exception_filter(root)
        app = DataPreparationApp(root)
        root.geometry("1280x920+0+0")
        _focus_capture_window(root, root)
        _pump_ui(root, 0.4)

        dataset_path = app._load_demo_dataset(SPECTRAL_REFERENCE_DEMO.key, show_message=True)
        _shorten_dataset_for_screenshots(
            app,
            dataset_path,
            max_rows=SPECTRAL_SCREENSHOT_MAX_ROWS,
        )
        app._select_file_in_listbox(dataset_path)
        _pump_ui(root, 0.6)

        main_window_path = output_dir / "main-window.png"
        _capture_widget(root, main_window_path)
        saved_paths.append(main_window_path)

        app.open_analysis_workspace()
        if not app._analysis_workspaces:
            raise RuntimeError("Analysis workspace did not open")
        workspace = app._analysis_workspaces[-1]
        workspace.window.geometry("1220x900+0+0")
        _focus_capture_window(workspace.window, root)
        _pump_ui(root, 0.5)

        filtering_sheet_path = output_dir / "algorithms-filtering.png"
        _capture_filtering_sheet(root, workspace, filtering_sheet_path)
        saved_paths.append(filtering_sheet_path)

        derived_sheet_path = output_dir / "algorithms-derived-signals.png"
        _capture_derived_sheet(root, workspace, derived_sheet_path)
        saved_paths.append(derived_sheet_path)

        frequency_sheet_path = output_dir / "algorithms-frequency.png"
        _capture_frequency_sheet(root, workspace, frequency_sheet_path)
        saved_paths.append(frequency_sheet_path)

        for workspace in list(app._analysis_workspaces):
            workspace.close()
        _pump_ui(root, 0.1)
        _cancel_pending_after_jobs(root)

        cycle_dataset_path = app._load_demo_dataset(CYCLE_VALIDATION_DEMO.key, show_message=True)
        _shorten_dataset_for_screenshots(
            app,
            cycle_dataset_path,
            max_rows=CYCLE_SCREENSHOT_MAX_ROWS,
            max_cycles=CYCLE_SCREENSHOT_MAX_CYCLES,
        )
        app._select_file_in_listbox(cycle_dataset_path)
        _pump_ui(root, 0.6)

        app.open_analysis_workspace()
        if not app._analysis_workspaces:
            raise RuntimeError("Cycle analysis workspace did not open")
        workspace = app._analysis_workspaces[-1]
        workspace.window.geometry("900x900+0+0")
        _focus_capture_window(workspace.window, root)
        _pump_ui(root, 0.5)

        raw_cycles_path = output_dir / "cycles-workspace-raw.png"
        _capture_cycles_workspace_raw(root, workspace, raw_cycles_path)
        saved_paths.append(raw_cycles_path)

        cycles_sheet_path = output_dir / "algorithms-cycles.png"
        _capture_cycles_sheet(root, workspace, cycles_sheet_path)
        saved_paths.append(cycles_sheet_path)

        for workspace in list(app._analysis_workspaces):
            workspace.close()
        _pump_ui(root, 0.1)
        _cancel_pending_after_jobs(root)
        root.destroy()

    return saved_paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture EvalData app screenshots automatically")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/images/overview"),
        help="Directory where screenshot PNG files are written",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    saved_paths = generate_screenshots(args.output_dir)
    print("Saved screenshots:")
    for path in saved_paths:
        print(f"- {path.as_posix()}")


if __name__ == "__main__":
    main()
