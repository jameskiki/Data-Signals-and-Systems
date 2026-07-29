"""Benchmark dataprep UI flow: file selection to preview plot visible.

This script simulates selecting one file via the load dialog and measures:
- total time from `load_files()` call to first embedded preview plot render
- number of refresh/preparation/render calls during that period
- additional refreshes shortly after first render (to detect duplicate reloads)
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
import time
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import tkinter as tk

from Source.datapreparation_app import actions, app as app_module, datasets
from Source.datapreparation_app.app import DataPreparationApp
from Source.shared.base_app_shell import BaseAppShell


def run_benchmark(file_path: str, timeout_s: float = 180.0, settle_s: float = 1.5) -> None:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    root = tk.Tk()
    root.withdraw()
    app = DataPreparationApp(root)

    # Keep UI windows from popping in front while still allowing full Tk render flow.
    root.withdraw()

    t0 = 0.0
    first_plot_visible_at: float | None = None

    events: list[tuple[float, str]] = []
    counters = {
        "refresh_dataset_table": 0,
        "select_dataset_in_table": 0,
        "refresh_dataset_preparation_views": 0,
        "refresh_preview_plot": 0,
        "render_embedded_figure": 0,
    }

    def stamp(name: str) -> None:
        now = time.perf_counter()
        if t0 > 0:
            events.append((now - t0, name))

    # Monkeypatch file dialog in datapreparation actions module.
    original_askopenfilenames = actions.filedialog.askopenfilenames

    def fake_askopenfilenames(*_args, **_kwargs):
        stamp("filedialog_return")
        return (file_path,)

    actions.filedialog.askopenfilenames = fake_askopenfilenames

    # Monkeypatch dataset table refresh/select functions.
    original_refresh_dataset_table = datasets.refresh_dataset_table
    original_select_dataset_in_table = datasets.select_dataset_in_table
    original_actions_refresh_dataset_table = actions.refresh_dataset_table
    original_actions_select_dataset_in_table = actions.select_dataset_in_table

    def wrapped_refresh_dataset_table(*args, **kwargs):
        counters["refresh_dataset_table"] += 1
        stamp("refresh_dataset_table")
        return original_refresh_dataset_table(*args, **kwargs)

    def wrapped_select_dataset_in_table(*args, **kwargs):
        counters["select_dataset_in_table"] += 1
        stamp("select_dataset_in_table")
        return original_select_dataset_in_table(*args, **kwargs)

    datasets.refresh_dataset_table = wrapped_refresh_dataset_table
    datasets.select_dataset_in_table = wrapped_select_dataset_in_table
    actions.refresh_dataset_table = wrapped_refresh_dataset_table
    actions.select_dataset_in_table = wrapped_select_dataset_in_table

    # Monkeypatch app-level imported helper function used by _refresh_preview_with_range.
    original_refresh_preview_plot = app_module.refresh_preview_plot

    def wrapped_refresh_preview_plot(*args, **kwargs):
        counters["refresh_preview_plot"] += 1
        stamp("refresh_preview_plot")
        return original_refresh_preview_plot(*args, **kwargs)

    app_module.refresh_preview_plot = wrapped_refresh_preview_plot

    # Monkeypatch embedded render helper.
    original_render_embedded_figure = BaseAppShell._render_embedded_figure

    def wrapped_render_embedded_figure(self, *args, **kwargs):
        nonlocal first_plot_visible_at
        counters["render_embedded_figure"] += 1
        stamp("render_embedded_figure")
        result = original_render_embedded_figure(self, *args, **kwargs)
        if first_plot_visible_at is None and getattr(self, "_preview_plot_canvas", None) is not None:
            first_plot_visible_at = time.perf_counter() - t0
            stamp("first_plot_visible")
        return result

    BaseAppShell._render_embedded_figure = wrapped_render_embedded_figure

    # Wrap bound method on instance for precise call count.
    original_refresh_dataset_preparation_views = app._refresh_dataset_preparation_views

    def wrapped_refresh_dataset_preparation_views(*args, **kwargs):
        counters["refresh_dataset_preparation_views"] += 1
        caller = inspect.stack()[1].function
        stamp(f"refresh_dataset_preparation_views <- {caller}")
        return original_refresh_dataset_preparation_views(*args, **kwargs)

    app._refresh_dataset_preparation_views = wrapped_refresh_dataset_preparation_views  # type: ignore[method-assign]

    try:
        t0 = time.perf_counter()
        stamp("load_files_called")
        app.load_files()

        deadline = t0 + timeout_s
        stable_since: float | None = None
        last_render_count = -1

        while time.perf_counter() < deadline:
            root.update_idletasks()
            root.update()
            time.sleep(0.01)

            if first_plot_visible_at is not None:
                current_render_count = counters["render_embedded_figure"]
                if current_render_count != last_render_count:
                    last_render_count = current_render_count
                    stable_since = time.perf_counter()
                elif stable_since is not None and (time.perf_counter() - stable_since) >= settle_s:
                    break

        total_elapsed = time.perf_counter() - t0

        print("=== Dataprep UI Load-to-Plot Benchmark ===")
        print(f"file={file_path}")
        print(f"file_size_mb={os.path.getsize(file_path)/1_048_576:.2f}")
        print(f"rows_loaded={sum(len(df) for df in app.data_frames.values()):,}")
        print(f"datasets_loaded={len(app.data_frames)}")
        print()
        if first_plot_visible_at is None:
            print(f"first_plot_visible=NOT_REACHED (timeout {timeout_s:.1f}s)")
        else:
            print(f"time_to_first_plot_visible={first_plot_visible_at:.3f}s")
        print(f"total_observation_time={total_elapsed:.3f}s")
        print()
        print("=== Call Counts ===")
        for key, value in counters.items():
            print(f"{key}={value}")
        print()

        print("=== Event Timeline (s from load_files call) ===")
        for t_rel, name in events:
            print(f"{t_rel:8.3f}  {name}")

    finally:
        actions.filedialog.askopenfilenames = original_askopenfilenames
        datasets.refresh_dataset_table = original_refresh_dataset_table
        datasets.select_dataset_in_table = original_select_dataset_in_table
        actions.refresh_dataset_table = original_actions_refresh_dataset_table
        actions.select_dataset_in_table = original_actions_select_dataset_in_table
        app_module.refresh_preview_plot = original_refresh_preview_plot
        BaseAppShell._render_embedded_figure = original_render_embedded_figure

        try:
            app._handle_app_close()
        except Exception:
            traceback.print_exc()
            try:
                root.destroy()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark dataprep load->plot UI path")
    parser.add_argument("file", help="CSV/log file path")
    parser.add_argument("--timeout", type=float, default=180.0, help="Max benchmark time in seconds")
    parser.add_argument("--settle", type=float, default=1.5, help="Stability window after first render")
    args = parser.parse_args()

    run_benchmark(args.file, timeout_s=args.timeout, settle_s=args.settle)


if __name__ == "__main__":
    main()
