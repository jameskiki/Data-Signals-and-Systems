"""Lightweight dataset comparison window for session datasets."""

from __future__ import annotations

import math
import os
import tkinter as tk
from collections.abc import Mapping
from dataclasses import replace
from tkinter import ttk

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from Source.data_ops.summary import build_statistics_frame, summarize_dataframe
from Source.shared.display_format import format_display_value
from Source.shared.notifications import NotificationManager
from Source.shared.plot_options import PlotOptions, PlotStyle
from Source.shared.plot_utils import create_plot_figure
from Source.shared.presentation_shell import PresentationShellMixin


COMPARISON_WINDOW_GEOMETRY = "1280x820"
COMPARISON_SELECTOR_MAX_ITEMS = 300
POSITIVE_DEVIATION_COLOR = "#d62728"
NEGATIVE_DEVIATION_COLOR = "#1f77b4"
DEVIATION_FILL_ALPHA = 0.18


def get_common_columns(
    dataset_paths: list[str],
    data_frames: dict[str, pd.DataFrame],
    *,
    numeric_only: bool = False,
) -> list[str]:
    """Return columns shared by every selected dataset, preserving first-dataset order."""

    if not dataset_paths:
        return []

    first_frame = data_frames[dataset_paths[0]]
    first_columns = _get_frame_columns(first_frame, numeric_only=numeric_only)
    common_columns = set(first_columns)
    for dataset_path in dataset_paths[1:]:
        common_columns.intersection_update(_get_frame_columns(data_frames[dataset_path], numeric_only=numeric_only))
    return [column for column in first_columns if column in common_columns]


def get_numeric_column_availability(
    dataset_paths: list[str],
    data_frames: Mapping[str, pd.DataFrame],
) -> dict[str, int]:
    """Count numeric-column availability while preserving first appearance order."""

    availability: dict[str, int] = {}
    for dataset_path in dataset_paths:
        numeric_column_list = [
            str(column_name)
            for column_name in data_frames[dataset_path].select_dtypes(include="number").columns
        ]
        numeric_columns = set(numeric_column_list)
        for column_name in numeric_column_list:
            availability.setdefault(column_name, 0)
        for column_name in availability:
            if column_name in numeric_columns:
                availability[column_name] += 1
    return availability


def build_numeric_column_labels(
    availability: Mapping[str, int],
    dataset_count: int,
) -> dict[str, str]:
    """Annotate numeric columns that are unavailable in some datasets."""

    return {
        column_name: (
            column_name
            if available_count == dataset_count
            else f"{column_name} ({available_count}/{dataset_count} datasets)"
        )
        for column_name, available_count in availability.items()
    }


def get_missing_column_combinations(
    dataset_paths: list[str],
    data_frames: Mapping[str, pd.DataFrame],
    columns: list[str],
) -> list[tuple[str, str]]:
    """Return selected dataset/channel combinations that cannot be plotted."""

    return [
        (dataset_path, column)
        for dataset_path in dataset_paths
        for column in columns
        if column not in data_frames[dataset_path].columns
    ]


def resolve_default_x_column(
    dataset_paths: list[str],
    data_frames: dict[str, pd.DataFrame],
    dataset_contexts: dict[str, object],
) -> str:
    """Prefer a shared time-role column, otherwise fall back to Index."""

    if not dataset_paths:
        return "Index"

    shared_time_columns: set[str] | None = None
    for dataset_path in dataset_paths:
        dataframe = data_frames[dataset_path]
        context = dataset_contexts.get(dataset_path)
        column_roles = getattr(context, "column_roles", {}) or {}
        time_columns = {
            str(column_name)
            for column_name, role_name in column_roles.items()
            if role_name == "time" and str(column_name) in dataframe.columns
        }
        if shared_time_columns is None:
            shared_time_columns = set(time_columns)
        else:
            shared_time_columns.intersection_update(time_columns)

    if shared_time_columns:
        for column_name in get_common_columns(dataset_paths, data_frames):
            if column_name in shared_time_columns:
                return column_name
    return "Index"


def build_comparison_summary_frame(
    dataset_paths: list[str],
    data_frames: dict[str, pd.DataFrame],
    stats_column: str | None = None,
    *,
    baseline_path: str | None = None,
    include_richer_metrics: bool = False,
) -> pd.DataFrame:
    """Build a compact per-dataset summary frame for the comparison window."""

    base_columns = ["dataset", "rows", "cols", "missing", "mean", "std", "min", "max"]
    richer_columns = ["count", "rms", "peak_to_peak", "deviation_rms", "baseline"]
    if not dataset_paths:
        return pd.DataFrame(columns=base_columns + (richer_columns if include_richer_metrics else []))

    display_labels = build_display_dataset_labels(dataset_paths)
    rows: list[dict[str, object]] = []
    for dataset_path in dataset_paths:
        dataframe = data_frames[dataset_path]
        summary = summarize_dataframe(dataframe, include_details=False)
        row: dict[str, object] = {
            "dataset_path": dataset_path,
            "dataset": display_labels[dataset_path],
            "rows": summary.row_count,
            "cols": summary.column_count,
            "missing": summary.total_missing_count,
        }
        if (
            stats_column
            and stats_column in dataframe.columns
            and pd.api.types.is_numeric_dtype(dataframe[stats_column])
        ):
            stats_frame = build_statistics_frame(dataframe[[stats_column]])
            if stats_column in stats_frame.index:
                stats_row = stats_frame.loc[stats_column]
                row.update(
                    {
                        "mean": stats_row["mean"],
                        "std": stats_row["std"],
                        "min": stats_row["min"],
                        "max": stats_row["max"],
                        "count": stats_row["count"],
                        "rms": stats_row["rms"],
                        "peak_to_peak": stats_row["peak_to_peak"],
                    }
                )
        if include_richer_metrics:
            row.setdefault("count", pd.NA)
            row.setdefault("rms", pd.NA)
            row.setdefault("peak_to_peak", pd.NA)
            row["baseline"] = dataset_path == baseline_path
        rows.append(row)

    summary_frame = pd.DataFrame(rows).set_index("dataset_path")
    for column_name in ("mean", "std", "min", "max"):
        if column_name not in summary_frame.columns:
            summary_frame[column_name] = pd.NA
    if not include_richer_metrics:
        return summary_frame[base_columns]

    for column_name in ("count", "rms", "peak_to_peak"):
        if column_name not in summary_frame.columns:
            summary_frame[column_name] = pd.NA
    summary_frame["deviation_rms"] = pd.NA
    if baseline_path in data_frames and stats_column and stats_column in data_frames[baseline_path]:
        baseline_values = _prepare_numeric_series(data_frames[baseline_path], stats_column)
        for dataset_path in dataset_paths:
            if dataset_path == baseline_path:
                continue
            candidate_values = _prepare_numeric_series(data_frames[dataset_path], stats_column)
            deviation = calculate_difference_series(
                baseline_values,
                candidate_values,
                normalize=False,
                zero_start=False,
            )
            if deviation is not None:
                summary_frame.loc[dataset_path, "deviation_rms"] = float(np.sqrt(np.mean(deviation**2)))
    return summary_frame[base_columns + richer_columns]


def _prepare_numeric_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(dataframe[column], errors="coerce").dropna()


def calculate_difference_series(
    baseline: pd.Series,
    candidate: pd.Series,
    *,
    normalize: bool = False,
    zero_start: bool = False,
) -> np.ndarray | None:
    """Return candidate minus baseline on the shared positional sample range."""

    baseline_values = baseline.to_numpy(dtype=float)
    candidate_values = candidate.to_numpy(dtype=float)
    sample_count = min(len(baseline_values), len(candidate_values))
    if sample_count == 0:
        return None
    baseline_values = baseline_values[:sample_count]
    candidate_values = candidate_values[:sample_count]
    if normalize:
        baseline_scale = np.nanmax(np.abs(baseline_values))
        candidate_scale = np.nanmax(np.abs(candidate_values))
        if baseline_scale > 0:
            baseline_values = baseline_values / baseline_scale
        if candidate_scale > 0:
            candidate_values = candidate_values / candidate_scale
    if zero_start:
        baseline_values = baseline_values - baseline_values[0]
        candidate_values = candidate_values - candidate_values[0]
    return candidate_values - baseline_values


def get_shared_x_overlap_bounds(
    dataset_paths: list[str],
    data_frames: Mapping[str, pd.DataFrame],
    x_column: str,
) -> tuple[float, float] | None:
    """Return the finite x range shared by every selected dataset."""

    ranges: list[tuple[float, float]] = []
    for path in dataset_paths:
        x_values, _ = _comparison_x_values(data_frames[path], x_column)
        finite_values = x_values[np.isfinite(x_values)]
        if finite_values.size == 0:
            return None
        ranges.append((float(np.min(finite_values)), float(np.max(finite_values))))
    if not ranges:
        return None
    lower = max(start for start, _ in ranges)
    upper = min(end for _, end in ranges)
    return (lower, upper) if lower <= upper else None


def trim_dataframes_to_shared_x_overlap(
    dataset_paths: list[str],
    data_frames: Mapping[str, pd.DataFrame],
    x_column: str,
) -> dict[str, pd.DataFrame]:
    """Copy and trim selected datasets to their common finite x range."""

    bounds = get_shared_x_overlap_bounds(dataset_paths, data_frames, x_column)
    if bounds is None:
        return {path: data_frames[path].iloc[0:0].copy() for path in dataset_paths}
    lower, upper = bounds
    trimmed_frames: dict[str, pd.DataFrame] = {}
    for path in dataset_paths:
        frame = data_frames[path]
        x_values, _ = _comparison_x_values(frame, x_column)
        mask = np.isfinite(x_values) & (x_values >= lower) & (x_values <= upper)
        trimmed_frames[path] = frame.loc[mask].copy()
    return trimmed_frames


def _prepare_finite_xy(x_values: np.ndarray, y_values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    count = min(len(x_values), len(y_values))
    x_values = np.asarray(x_values[:count], dtype=float)
    y_values = np.asarray(y_values[:count], dtype=float)
    finite_mask = np.isfinite(x_values) & np.isfinite(y_values)
    x_values = x_values[finite_mask]
    y_values = y_values[finite_mask]
    if x_values.size == 0:
        return x_values, y_values
    order = np.argsort(x_values, kind="stable")
    return x_values[order], y_values[order]


def calculate_subplot_grid(item_count: int) -> tuple[int, int]:
    """Return a compact row/column grid for the requested subplot count."""

    if item_count < 1:
        raise ValueError("item_count must be at least 1")
    column_count = math.ceil(math.sqrt(item_count))
    row_count = math.ceil(item_count / column_count)
    return row_count, column_count


def align_comparison_series(
    baseline_frame: pd.DataFrame,
    candidate_frame: pd.DataFrame,
    column: str,
    x_column: str,
    bounds: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Align baseline and candidate values on the candidate x samples."""

    baseline_x, _ = _comparison_x_values(baseline_frame, x_column)
    candidate_x, _ = _comparison_x_values(candidate_frame, x_column)
    baseline_y = pd.to_numeric(baseline_frame[column], errors="coerce").to_numpy(dtype=float)
    candidate_y = pd.to_numeric(candidate_frame[column], errors="coerce").to_numpy(dtype=float)
    baseline_x_values, baseline_values = _prepare_finite_xy(baseline_x, baseline_y)
    candidate_x_values, candidate_values = _prepare_finite_xy(candidate_x, candidate_y)
    if baseline_x_values.size == 0 or candidate_x_values.size == 0:
        return None

    if x_column == "Index":
        count = min(len(baseline_values), len(candidate_values))
        x_values = candidate_x_values[:count]
        baseline_values = baseline_values[:count]
        candidate_values = candidate_values[:count]
        if bounds is not None:
            lower, upper = bounds
            mask = (x_values >= lower) & (x_values <= upper)
            x_values = x_values[mask]
            baseline_values = baseline_values[mask]
            candidate_values = candidate_values[mask]
        return x_values, baseline_values, candidate_values

    lower = max(float(baseline_x_values[0]), float(candidate_x_values[0]))
    upper = min(float(baseline_x_values[-1]), float(candidate_x_values[-1]))
    if bounds is not None:
        lower = max(lower, bounds[0])
        upper = min(upper, bounds[1])
    if lower > upper:
        return None
    candidate_mask = (candidate_x_values >= lower) & (candidate_x_values <= upper)
    x_values = candidate_x_values[candidate_mask]
    candidate_values = candidate_values[candidate_mask]
    if x_values.size == 0:
        return None
    unique_baseline_x, unique_indices = np.unique(baseline_x_values, return_index=True)
    baseline_values = np.interp(x_values, unique_baseline_x, baseline_values[unique_indices])
    return x_values, baseline_values, candidate_values


def _fill_signed_deviation(
    axis,
    x_values: np.ndarray,
    reference_values: np.ndarray,
    candidate_values: np.ndarray,
    *,
    add_labels: bool,
) -> None:
    positive_mask = candidate_values >= reference_values
    negative_mask = candidate_values < reference_values
    axis.fill_between(
        x_values,
        reference_values,
        candidate_values,
        where=positive_mask,
        interpolate=True,
        color=POSITIVE_DEVIATION_COLOR,
        alpha=DEVIATION_FILL_ALPHA,
        label="Above baseline" if add_labels else "_nolegend_",
    )
    axis.fill_between(
        x_values,
        reference_values,
        candidate_values,
        where=negative_mask,
        interpolate=True,
        color=NEGATIVE_DEVIATION_COLOR,
        alpha=DEVIATION_FILL_ALPHA,
        label="Below baseline" if add_labels else "_nolegend_",
    )


def add_overlay_deviation_highlights(
    figure: plt.Figure,
    dataset_paths: list[str],
    data_frames: Mapping[str, pd.DataFrame],
    baseline_path: str,
    columns: list[str],
    *,
    x_column: str,
    channels_in_grid: bool,
    style: PlotStyle | None = None,
) -> None:
    """Fill signed areas between each visible candidate and the baseline."""

    if baseline_path not in data_frames:
        return
    resolved_style = style or PlotStyle()
    baseline_frame = data_frames[baseline_path]
    labeled_axes: set[int] = set()
    for column_index, column in enumerate(columns):
        axis_index = column_index if channels_in_grid else 0
        axis = figure.axes[axis_index]
        if column not in baseline_frame.columns:
            continue
        for path in dataset_paths:
            if path == baseline_path or column not in data_frames[path].columns:
                continue
            aligned = align_comparison_series(
                baseline_frame,
                data_frames[path],
                column,
                x_column,
            )
            if aligned is None:
                continue
            x_values, baseline_values, candidate_values = aligned
            _fill_signed_deviation(
                axis,
                x_values,
                baseline_values,
                candidate_values,
                add_labels=axis_index not in labeled_axes,
            )
            labeled_axes.add(axis_index)
        if axis_index in labeled_axes and resolved_style.show_legend:
            axis.legend(
                fontsize=resolved_style.legend_fontsize,
                loc=resolved_style.legend_location,
            )


def build_difference_figure(
    dataset_paths: list[str],
    data_frames: dict[str, pd.DataFrame],
    baseline_path: str,
    columns: list[str],
    *,
    x_column: str = "Index",
    normalize: bool = False,
    zero_start: bool = False,
    trim_overlap: bool = False,
    channels_in_grid: bool = False,
    highlight_deviations: bool = False,
    style: PlotStyle | None = None,
) -> plt.Figure:
    """Build candidate-minus-baseline curves for the selected common signals."""

    if baseline_path not in data_frames:
        raise ValueError("The selected baseline dataset is no longer available.")
    resolved_style = style or PlotStyle()
    if channels_in_grid:
        row_count, column_count = calculate_subplot_grid(len(columns))
        figure, axes = plt.subplots(
            row_count,
            column_count,
            squeeze=False,
            figsize=(6 * column_count, 4 * row_count),
        )
    else:
        row_count, column_count = len(columns), 1
        figure, axes = plt.subplots(
            row_count,
            column_count,
            squeeze=False,
            figsize=(10, max(4, 3.5 * len(columns))),
        )
    baseline_frame = data_frames[baseline_path]
    shared_bounds = (
        get_shared_x_overlap_bounds(dataset_paths, data_frames, x_column)
        if trim_overlap
        else None
    )
    for index, column in enumerate(columns):
        axis = axes[index // column_count][index % column_count]
        highlights_labeled = False
        if column not in baseline_frame.columns:
            axis.set_title(column)
            axis.text(
                0.5,
                0.5,
                "Unavailable in baseline",
                ha="center",
                va="center",
                transform=axis.transAxes,
            )
            axis.set_axis_off()
            continue
        for path in dataset_paths:
            if path == baseline_path or column not in data_frames[path].columns:
                continue
            candidate_frame = data_frames[path]
            aligned = align_comparison_series(
                baseline_frame,
                candidate_frame,
                column,
                x_column,
                shared_bounds,
            )
            if aligned is None:
                continue
            x_values, baseline_values, candidate_values = aligned
            difference = calculate_difference_series(
                pd.Series(baseline_values),
                pd.Series(candidate_values),
                normalize=normalize,
                zero_start=zero_start,
            )
            if difference is not None:
                axis.plot(x_values[:len(difference)], difference, label=os.path.basename(path))
                if highlight_deviations:
                    zero_values = np.zeros(len(difference), dtype=float)
                    _fill_signed_deviation(
                        axis,
                        x_values[:len(difference)],
                        zero_values,
                        difference,
                        add_labels=not highlights_labeled,
                    )
                    highlights_labeled = True
        axis.set_title(column)
        axis.set_ylabel("Candidate - baseline")
        axis.grid(True, alpha=0.3)
        axis.axhline(
            0.0,
            color="black",
            linewidth=1.0,
            linestyle="--",
            label=f"Baseline: {os.path.basename(baseline_path)} (zero)",
        )
        if resolved_style.show_legend:
            axis.legend(
                fontsize=resolved_style.legend_fontsize,
                loc=resolved_style.legend_location,
            )
        axis.set_xlabel("Index" if x_column == "Index" else x_column)
    for unused_index in range(len(columns), row_count * column_count):
        axes[unused_index // column_count][unused_index % column_count].set_visible(False)
    figure.suptitle("Difference Comparison")
    figure.tight_layout()
    return figure


def _comparison_x_values(dataframe: pd.DataFrame, x_column: str) -> tuple[np.ndarray, str]:
    if x_column == "Index" or x_column not in dataframe.columns:
        return np.arange(len(dataframe), dtype=float), "Index"
    return pd.to_numeric(dataframe[x_column], errors="coerce").to_numpy(dtype=float), x_column


def build_display_dataset_labels(dataset_paths: list[str]) -> dict[str, str]:
    """Return unique display labels while keeping short basenames when possible."""

    basename_counts: dict[str, int] = {}
    for dataset_path in dataset_paths:
        basename = os.path.basename(dataset_path)
        basename_counts[basename] = basename_counts.get(basename, 0) + 1

    duplicate_counters: dict[str, int] = {}
    labels: dict[str, str] = {}
    for dataset_path in dataset_paths:
        basename = os.path.basename(dataset_path)
        if basename_counts[basename] == 1:
            labels[dataset_path] = basename
            continue
        duplicate_counters[basename] = duplicate_counters.get(basename, 0) + 1
        labels[dataset_path] = f"{basename} ({duplicate_counters[basename]})"
    return labels


def filter_visible_dataset_paths(
    dataset_paths: list[str],
    visibility_by_path: Mapping[str, bool],
) -> list[str]:
    """Return datasets enabled for plotting, preserving comparison order."""

    return [path for path in dataset_paths if visibility_by_path.get(path, True)]


class ComparisonWindow(PresentationShellMixin):
    """Comparison workspace for overlaying and summarizing session datasets."""

    def __init__(
        self,
        parent: tk.Misc,
        dataset_paths: list[str],
        data_frames: dict[str, pd.DataFrame],
        dataset_contexts: dict[str, object],
        *,
        default_style: PlotStyle | None = None,
        on_close=None,
        on_open_dataset=None,
    ) -> None:
        self.parent = parent
        self.dataset_paths = [dataset_path for dataset_path in dataset_paths if dataset_path in data_frames]
        self.data_frames = data_frames
        self.dataset_contexts = dataset_contexts
        self.notifications = NotificationManager()
        self.default_style = default_style or PlotStyle()
        self.on_close = on_close
        self.on_open_dataset = on_open_dataset

        self.window = tk.Toplevel(parent)
        self.window.title("Dataset Comparison")
        self.window.geometry(COMPARISON_WINDOW_GEOMETRY)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.x_column_var = tk.StringVar(value=resolve_default_x_column(self.dataset_paths, data_frames, dataset_contexts))
        common_numeric_columns = get_common_columns(self.dataset_paths, data_frames, numeric_only=True)
        default_summary_column = common_numeric_columns[0] if common_numeric_columns else ""
        self.summary_column_var = tk.StringVar(value=default_summary_column)
        self.baseline_path_var = tk.StringVar(value=self.dataset_paths[0] if self.dataset_paths else "")
        self.plot_mode_var = tk.StringVar(value="Overlay")
        self.normalize_var = tk.BooleanVar(value=False)
        self.zero_start_var = tk.BooleanVar(value=False)
        self.trim_overlap_var = tk.BooleanVar(value=False)
        self.channels_in_grid_var = tk.BooleanVar(value=False)
        self.highlight_deviations_var = tk.BooleanVar(value=False)
        self.show_legend_var = tk.BooleanVar(value=self.default_style.show_legend)
        self.plot_column_summary_var = tk.StringVar(value="No common numeric channels")
        self.dataset_visibility_summary_var = tk.StringVar(value="")
        self.comparison_status_var = tk.StringVar(value="")
        self.selected_dataset_detail_var = tk.StringVar(value="Select a dataset row for details.")
        self._plot_column_selector_button: ttk.Menubutton | None = None
        self._plot_column_selector_menu: tk.Menu | None = None
        self._plot_column_selector_vars: dict[str, tk.BooleanVar] = {}
        self._plot_column_labels: dict[str, str] = {}
        self._plot_column_hidden_count = 0
        self._dataset_visibility_vars: dict[str, tk.BooleanVar] = {}
        self._plot_columns_initialized = False
        self._summary_item_to_dataset_path: dict[str, str] = {}

        self._plot_figure: plt.Figure | None = None
        self._plot_canvas = None
        self._plot_toolbar = None
        self._summary_tree: ttk.Treeview | None = None

        self._build_ui()
        self._refresh_column_controls()
        self._update_comparison_view()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.window, padding=8)
        container.pack(fill=tk.BOTH, expand=True)

        controls = ttk.LabelFrame(container, text="Comparison Controls", padding=8)
        controls.pack(fill=tk.X)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        ttk.Label(
            controls,
            text=f"Comparing {len(self.dataset_paths)} datasets from the current session registry.",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 8))
        self._status_label = ttk.Label(
            controls,
            textvariable=self.comparison_status_var,
            wraplength=920,
            justify=tk.LEFT,
        )
        self._status_label.grid(row=6, column=0, columnspan=4, sticky="w", padx=5, pady=(2, 0))

        ttk.Label(controls, text="Shared X-axis").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.x_column_combo = ttk.Combobox(controls, textvariable=self.x_column_var, state="readonly")
        self.x_column_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.x_column_combo.bind("<<ComboboxSelected>>", lambda *_args: self._update_comparison_view())

        ttk.Label(controls, text="Summary column").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.summary_column_combo = ttk.Combobox(controls, textvariable=self.summary_column_var, state="readonly")
        self.summary_column_combo.grid(row=1, column=3, sticky="ew", padx=5, pady=5)
        self.summary_column_combo.bind("<<ComboboxSelected>>", lambda *_args: self._update_comparison_view())

        ttk.Label(controls, text="Mode").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        mode_combo = ttk.Combobox(
            controls,
            textvariable=self.plot_mode_var,
            values=["Overlay", "Difference (candidate - baseline)"],
            state="readonly",
        )
        mode_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        mode_combo.bind("<<ComboboxSelected>>", lambda *_args: self._update_comparison_view())
        ttk.Label(controls, text="Baseline").grid(row=2, column=2, sticky="w", padx=5, pady=5)
        self.baseline_combo = ttk.Combobox(controls, textvariable=self.baseline_path_var, state="readonly")
        self.baseline_combo.grid(row=2, column=3, sticky="ew", padx=5, pady=5)
        self.baseline_combo.bind("<<ComboboxSelected>>", lambda *_args: self._update_comparison_view())

        ttk.Label(controls, text="Signals").grid(row=3, column=0, sticky="nw", padx=5, pady=5)
        selector_row = ttk.Frame(controls)
        selector_row.grid(row=3, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        selector_row.columnconfigure(0, weight=1)

        self._plot_column_selector_button = ttk.Menubutton(
            selector_row,
            textvariable=self.plot_column_summary_var,
            direction="below",
        )
        self._plot_column_selector_button.grid(row=0, column=0, sticky="ew")
        self._plot_column_selector_menu = tk.Menu(self._plot_column_selector_button, tearoff=0)
        self._plot_column_selector_button.configure(menu=self._plot_column_selector_menu)
        self._plot_column_selector_button.state(["disabled"])

        actions = ttk.Frame(selector_row)
        actions.grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(actions, text="All", width=6, command=self._select_all_plot_columns).pack(side=tk.LEFT)
        ttk.Button(actions, text="None", width=6, command=self._clear_plot_columns).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(actions, text="Refresh", command=self._refresh_from_session).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(actions, text="Open In Analysis", command=self._open_selected_dataset_in_analysis).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(actions, text="Update", command=self._update_comparison_view).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(controls, text="Datasets").grid(row=4, column=0, sticky="nw", padx=5, pady=5)
        dataset_selector_row = ttk.Frame(controls)
        dataset_selector_row.grid(row=4, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        dataset_selector_row.columnconfigure(0, weight=1)
        self._dataset_visibility_button = ttk.Menubutton(
            dataset_selector_row,
            textvariable=self.dataset_visibility_summary_var,
            direction="below",
        )
        self._dataset_visibility_button.grid(row=0, column=0, sticky="ew")
        self._dataset_visibility_menu = tk.Menu(self._dataset_visibility_button, tearoff=0)
        self._dataset_visibility_button.configure(menu=self._dataset_visibility_menu)
        dataset_actions = ttk.Frame(dataset_selector_row)
        dataset_actions.grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Button(dataset_actions, text="All", width=6, command=self._show_all_datasets).pack(side=tk.LEFT)
        ttk.Button(dataset_actions, text="None", width=6, command=self._hide_all_datasets).pack(side=tk.LEFT, padx=(6, 0))

        options = ttk.Frame(controls)
        options.grid(row=5, column=1, columnspan=3, sticky="w", padx=5, pady=(0, 5))
        ttk.Checkbutton(options, text="Normalize amplitude", variable=self.normalize_var, command=self._update_comparison_view).pack(side=tk.LEFT)
        ttk.Checkbutton(options, text="Zero-start", variable=self.zero_start_var, command=self._update_comparison_view).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Checkbutton(options, text="Trim to overlap", variable=self.trim_overlap_var, command=self._update_comparison_view).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Checkbutton(
            options,
            text="Channels in grid",
            variable=self.channels_in_grid_var,
            command=self._update_comparison_view,
        ).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Checkbutton(
            options,
            text="Highlight deviations",
            variable=self.highlight_deviations_var,
            command=self._update_comparison_view,
        ).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Checkbutton(
            options,
            text="Show legend",
            variable=self.show_legend_var,
            command=self._update_comparison_view,
        ).pack(side=tk.LEFT, padx=(10, 0))

        content_pane = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        content_pane.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.plot_frame = ttk.LabelFrame(content_pane, text="Overlay Plot", padding=5)
        summary_frame = ttk.LabelFrame(content_pane, text="Summary", padding=5)
        content_pane.add(self.plot_frame, weight=3)
        content_pane.add(summary_frame, weight=2)

        self.plot_container = ttk.Frame(self.plot_frame)
        self.plot_container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            summary_frame,
            text="Rows/cols/missing always reflect the full dataset. RMS and peak-to-peak use the selected summary column. Uncheck datasets to hide them from the plot.",
            wraplength=320,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=5, pady=(0, 6))
        ttk.Label(
            summary_frame,
            textvariable=self.selected_dataset_detail_var,
            wraplength=320,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=5, pady=(0, 6))
        self.summary_container = ttk.Frame(summary_frame)
        self.summary_container.pack(fill=tk.BOTH, expand=True)

    def close(self) -> None:
        if self._plot_figure is not None:
            plt.close(self._plot_figure)
            self._plot_figure = None
        self.window.destroy()
        if self.on_close is not None:
            self.on_close(self)

    def _refresh_column_controls(self) -> None:
        if self.baseline_path_var.get() not in self.dataset_paths and self.dataset_paths:
            self.baseline_path_var.set(self.dataset_paths[0])
        baseline_values = [path for path in self.dataset_paths if path in self.data_frames]
        self.baseline_combo.config(values=baseline_values)
        common_columns = get_common_columns(self.dataset_paths, self.data_frames)
        common_numeric_columns = get_common_columns(self.dataset_paths, self.data_frames, numeric_only=True)
        numeric_availability = get_numeric_column_availability(self.dataset_paths, self.data_frames)
        numeric_columns = list(numeric_availability)
        self._plot_column_labels = build_numeric_column_labels(
            numeric_availability,
            len(self.dataset_paths),
        )
        x_values = ["Index", *common_columns]
        self.x_column_combo.config(values=x_values)
        if self.x_column_var.get() not in x_values:
            self.x_column_var.set(resolve_default_x_column(self.dataset_paths, self.data_frames, self.dataset_contexts))

        self.summary_column_combo.config(values=["", *common_numeric_columns])
        if self.summary_column_var.get() not in ("", *common_numeric_columns):
            self.summary_column_var.set(common_numeric_columns[0] if common_numeric_columns else "")

        default_selected = self._get_selected_plot_columns()
        if not self._plot_columns_initialized and not default_selected and numeric_columns:
            default_selected = numeric_columns[:1]
        self._plot_column_selector_vars, self._plot_column_hidden_count = self._build_checkbutton_selector_menu(
            menu=self._plot_column_selector_menu,
            button=self._plot_column_selector_button,
            items=numeric_columns,
            selected_items=default_selected,
            max_items=COMPARISON_SELECTOR_MAX_ITEMS,
            get_colors=lambda _name: ("white", "black"),
            on_changed=self._handle_plot_column_selection_changed,
            on_select_all=self._select_all_plot_columns,
            on_clear_selection=self._clear_plot_columns,
            hidden_label="signals",
            item_labels=self._plot_column_labels,
        )
        self._plot_columns_initialized = True
        self._update_plot_column_summary()
        self._refresh_visibility_controls()

    def _refresh_visibility_controls(self) -> None:
        self._dataset_visibility_menu.delete(0, tk.END)
        old_values = self._dataset_visibility_vars
        self._dataset_visibility_vars = {}
        display_labels = build_display_dataset_labels(self.dataset_paths)
        for path in self.dataset_paths:
            old_variable = old_values.get(path)
            variable = tk.BooleanVar(value=old_variable.get() if old_variable is not None else True)
            self._dataset_visibility_vars[path] = variable
            self._dataset_visibility_menu.add_checkbutton(
                label=display_labels[path],
                variable=variable,
                command=self._handle_dataset_visibility_changed,
            )
        self._update_dataset_visibility_summary()

    def _handle_dataset_visibility_changed(self) -> None:
        self._update_dataset_visibility_summary()
        self._update_comparison_view()

    def _update_dataset_visibility_summary(self) -> None:
        visible_count = sum(variable.get() for variable in self._dataset_visibility_vars.values())
        self.dataset_visibility_summary_var.set(
            f"{visible_count} of {len(self.dataset_paths)} datasets shown"
        )

    def _get_visible_dataset_paths(self) -> list[str]:
        visibility_by_path = {
            path: variable.get()
            for path, variable in self._dataset_visibility_vars.items()
        }
        return filter_visible_dataset_paths(self.dataset_paths, visibility_by_path)

    def _show_all_datasets(self) -> None:
        self._set_all_datasets_visible(True)

    def _hide_all_datasets(self) -> None:
        self._set_all_datasets_visible(False)

    def _set_all_datasets_visible(self, visible: bool) -> None:
        for variable in self._dataset_visibility_vars.values():
            variable.set(visible)
        self._handle_dataset_visibility_changed()

    def _handle_plot_column_selection_changed(self, *_args: object) -> None:
        self._update_plot_column_summary()

    def _update_plot_column_summary(self) -> None:
        visible_count = len(self._plot_column_selector_vars)
        self.plot_column_summary_var.set(
            self.format_selector_summary(
                self._get_selected_plot_columns(),
                visible_count=visible_count,
                hidden_count=self._plot_column_hidden_count,
                empty_text="No common numeric channels",
                choose_text="Choose signals",
            )
        )

    def _get_selected_plot_columns(self) -> list[str]:
        return self.get_selected_selector_items(self._plot_column_selector_vars)

    def _select_all_plot_columns(self) -> None:
        self.set_selector_items_state(self._plot_column_selector_vars, True)
        self._update_plot_column_summary()

    def _clear_plot_columns(self) -> None:
        self.set_selector_items_state(self._plot_column_selector_vars, False)
        self._update_plot_column_summary()

    def _update_comparison_view(self) -> None:
        self._filter_existing_dataset_paths()
        if len(self.dataset_paths) < 2:
            self._clear_plot()
            self._clear_summary_tree()
            self.selected_dataset_detail_var.set("At least two compared datasets must remain available in the session.")
            self._update_status_text()
            return
        selected_columns = self._get_selected_plot_columns()
        visible_paths = self._get_visible_dataset_paths()
        difference_mode = self.plot_mode_var.get().startswith("Difference")
        if difference_mode:
            baseline_path = self.baseline_path_var.get()
            visible_candidates = [path for path in visible_paths if path != baseline_path]
            if not visible_candidates:
                self._clear_plot()
                self._render_summary_tree()
                self._update_status_text("No candidate datasets are visible. Select at least one candidate in the Datasets selector.")
                return
            if baseline_path not in visible_paths:
                visible_paths = [baseline_path, *visible_paths]
        if not selected_columns:
            self._clear_plot()
            self._render_summary_tree()
            if get_numeric_column_availability(self.dataset_paths, self.data_frames):
                self.notifications.warning("Select at least one numeric signal")
            self._update_status_text()
            return

        if not visible_paths:
            self._clear_plot()
            self._render_summary_tree()
            self._update_status_text("No datasets are visible. Select at least one dataset in the Datasets selector.")
            return
        plot_style = replace(
            self.default_style,
            show_legend=self.show_legend_var.get(),
        )
        if difference_mode:
            self.plot_frame.configure(text="Difference Plot")
            figure = build_difference_figure(
                visible_paths,
                self.data_frames,
                self.baseline_path_var.get(),
                selected_columns,
                x_column=self.x_column_var.get().strip() or "Index",
                normalize=self.normalize_var.get(),
                zero_start=self.zero_start_var.get(),
                trim_overlap=self.trim_overlap_var.get(),
                channels_in_grid=self.channels_in_grid_var.get(),
                highlight_deviations=self.highlight_deviations_var.get(),
                style=plot_style,
            )
        else:
            self.plot_frame.configure(text="Overlay Plot")
            display_paths = list(visible_paths)
            baseline_path = self.baseline_path_var.get()
            if self.highlight_deviations_var.get() and baseline_path not in display_paths:
                display_paths.insert(0, baseline_path)
            plot_frames = self._build_display_frames(display_paths, selected_columns)
            _, grid_column_count = calculate_subplot_grid(len(selected_columns))
            figure = create_plot_figure(
                PlotOptions(
                    cols_to_plot=selected_columns,
                    xcol=self.x_column_var.get().strip() or "Index",
                    use_subplots=self.channels_in_grid_var.get(),
                    title="Session Dataset Comparison",
                    y_label="Value",
                    subplot_columns=grid_column_count,
                    style=plot_style,
                ),
                visible_paths,
                plot_frames,
                column_roles=None,
                dataset_line_styles={self.baseline_path_var.get(): "--"},
            )
            if self.highlight_deviations_var.get():
                add_overlay_deviation_highlights(
                    figure,
                    visible_paths,
                    plot_frames,
                    self.baseline_path_var.get(),
                    selected_columns,
                    x_column=self.x_column_var.get().strip() or "Index",
                    channels_in_grid=self.channels_in_grid_var.get(),
                    style=plot_style,
                )
        self._render_embedded_figure(
            figure=figure,
            figure_attr="_plot_figure",
            canvas_attr="_plot_canvas",
            toolbar_attr="_plot_toolbar",
            container=self.plot_container,
            root_window=self.window,
            draw_idle_on_reuse=False,
            clear_container_before_create=True,
        )
        self._render_summary_tree()
        self._update_status_text()

    def _build_display_frames(self, paths: list[str], columns: list[str]) -> dict[str, pd.DataFrame]:
        """Apply display-only signal transforms without changing session datasets."""

        source_frames: Mapping[str, pd.DataFrame] = self.data_frames
        if self.trim_overlap_var.get():
            source_frames = trim_dataframes_to_shared_x_overlap(
                paths,
                self.data_frames,
                self.x_column_var.get().strip() or "Index",
            )
        frames: dict[str, pd.DataFrame] = {}
        for path in paths:
            frame = source_frames[path].copy()
            for column in columns:
                if column not in frame.columns:
                    continue
                values = pd.to_numeric(frame[column], errors="coerce")
                if self.normalize_var.get():
                    scale = values.abs().max()
                    if pd.notna(scale) and scale > 0:
                        values = values / scale
                if self.zero_start_var.get() and not values.dropna().empty:
                    values = values - values.dropna().iloc[0]
                frame[column] = values
            frames[path] = frame
        return frames

    def _clear_plot(self) -> None:
        self.plot_frame.configure(text="Plot")
        if self._plot_figure is not None:
            plt.close(self._plot_figure)
            self._plot_figure = None
        self._plot_canvas = None
        self._plot_toolbar = None
        for widget in self.plot_container.winfo_children():
            widget.destroy()

    def _render_summary_tree(self) -> None:
        for widget in self.summary_container.winfo_children():
            widget.destroy()

        self._summary_item_to_dataset_path = {}
        summary_frame = build_comparison_summary_frame(
            self.dataset_paths,
            self.data_frames,
            stats_column=self.summary_column_var.get().strip() or None,
            baseline_path=self.baseline_path_var.get(),
            include_richer_metrics=True,
        )
        columns = [
            "dataset", "baseline", "rows", "cols", "missing", "count",
            "mean", "std", "min", "max", "rms", "peak_to_peak", "deviation_rms",
        ]
        tree = ttk.Treeview(self.summary_container, columns=columns, show="headings", selectmode="browse")
        tree.grid(row=0, column=0, sticky="nsew")
        vertical_scrollbar = ttk.Scrollbar(self.summary_container, orient=tk.VERTICAL, command=tree.yview)
        vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar = ttk.Scrollbar(self.summary_container, orient=tk.HORIZONTAL, command=tree.xview)
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        self.summary_container.columnconfigure(0, weight=1)
        self.summary_container.rowconfigure(0, weight=1)
        tree.configure(yscrollcommand=vertical_scrollbar.set, xscrollcommand=horizontal_scrollbar.set)
        tree.bind("<<TreeviewSelect>>", self._handle_summary_tree_selection_changed)

        headings = {
            "dataset": "Dataset",
            "baseline": "Baseline",
            "rows": "Rows",
            "cols": "Cols",
            "missing": "Missing",
            "count": "Count",
            "mean": "Mean",
            "std": "Std",
            "rms": "RMS",
            "peak_to_peak": "Peak-to-peak",
            "deviation_rms": "Deviation RMS",
            "min": "Min",
            "max": "Max",
        }
        widths = {
            "dataset": 180,
            "baseline": 65,
            "rows": 70,
            "cols": 60,
            "missing": 70,
            "count": 70,
            "mean": 80,
            "std": 80,
            "rms": 80,
            "peak_to_peak": 100,
            "deviation_rms": 100,
            "min": 80,
            "max": 80,
        }
        for column_name in columns:
            anchor = tk.W if column_name == "dataset" else tk.E
            tree.heading(column_name, text=headings[column_name])
            tree.column(column_name, width=widths[column_name], minwidth=widths[column_name], anchor=anchor, stretch=column_name == "dataset")

        for dataset_path, row in summary_frame.iterrows():
            item_id = tree.insert(
                "",
                tk.END,
                values=[
                    row["dataset"],
                    "Yes" if row["baseline"] else "",
                    format_display_value(row["rows"]),
                    format_display_value(row["cols"]),
                    format_display_value(row["missing"]),
                    format_display_value(row["count"]),
                    format_display_value(row["mean"]),
                    format_display_value(row["std"]),
                    format_display_value(row["min"]),
                    format_display_value(row["max"]),
                    format_display_value(row["rms"]),
                    format_display_value(row["peak_to_peak"]),
                    format_display_value(row["deviation_rms"]),
                ],
            )
            self._summary_item_to_dataset_path[item_id] = dataset_path
        self._summary_tree = tree
        if self._summary_item_to_dataset_path:
            first_item = next(iter(self._summary_item_to_dataset_path))
            tree.selection_set(first_item)
            self._update_selected_dataset_detail(self._summary_item_to_dataset_path[first_item])

    def _clear_summary_tree(self) -> None:
        for widget in self.summary_container.winfo_children():
            widget.destroy()
        self._summary_tree = None
        self._summary_item_to_dataset_path = {}

    def _refresh_from_session(self) -> None:
        self._filter_existing_dataset_paths(notify_missing=True)
        self._refresh_column_controls()
        self._update_comparison_view()

    def _filter_existing_dataset_paths(self, *, notify_missing: bool = False) -> None:
        existing_paths = [path for path in self.dataset_paths if path in self.data_frames]
        removed_paths = [path for path in self.dataset_paths if path not in self.data_frames]
        if notify_missing and removed_paths:
            self.notifications.warning(
                "Some comparison datasets are no longer present in the session",
                details="\n".join(removed_paths),
            )
        self.dataset_paths = existing_paths

    def _update_status_text(self, extra: str = "") -> None:
        numeric_availability = get_numeric_column_availability(self.dataset_paths, self.data_frames)
        common_columns = get_common_columns(self.dataset_paths, self.data_frames)
        diagnostic = ""
        if not numeric_availability:
            diagnostic = " No numeric columns are available."
        elif self.x_column_var.get() != "Index" and self.x_column_var.get() not in common_columns:
            diagnostic = " The selected time column is not shared by every dataset."
        elif self.x_column_var.get() != "Index" and not self._has_shared_x_overlap():
            diagnostic = " The selected x/time ranges have too little overlap."
        elif self.plot_mode_var.get().startswith("Difference"):
            baseline_path = self.baseline_path_var.get()
            visible_candidates = [path for path in self._get_visible_dataset_paths() if path != baseline_path]
            if not visible_candidates:
                diagnostic = " Difference mode needs at least one visible candidate."
        selected_columns = self._get_selected_plot_columns()
        visible_paths = self._get_visible_dataset_paths()
        missing_combinations = get_missing_column_combinations(
            visible_paths,
            self.data_frames,
            selected_columns,
        )
        omitted_text = ""
        if missing_combinations:
            examples = ", ".join(
                f"{os.path.basename(path)}: {column}"
                for path, column in missing_combinations[:3]
            )
            more_count = len(missing_combinations) - 3
            more_suffix = f", +{more_count} more" if more_count else ""
            omitted_text = (
                f" Omitted {len(missing_combinations)} unavailable dataset/channel "
                f"combination(s): {examples}{more_suffix}."
            )
        self.comparison_status_var.set(
            f"Comparing {len(self.dataset_paths)} session datasets. "
            f"Use the Datasets selector to hide datasets without removing them from the session. "
            f"Refresh re-reads the current session data. {extra}{diagnostic}{omitted_text}"
        )

    def _has_shared_x_overlap(self) -> bool:
        return get_shared_x_overlap_bounds(
            self.dataset_paths,
            self.data_frames,
            self.x_column_var.get(),
        ) is not None

    def _handle_summary_tree_selection_changed(self, _event: tk.Event | None = None) -> None:
        selected_path = self._get_selected_summary_dataset_path()
        if selected_path is None:
            self.selected_dataset_detail_var.set("Select a dataset row for details.")
            return
        self._update_selected_dataset_detail(selected_path)

    def _get_selected_summary_dataset_path(self) -> str | None:
        if self._summary_tree is None:
            return None
        selection = self._summary_tree.selection()
        if not selection:
            return None
        return self._summary_item_to_dataset_path.get(selection[0])

    def _update_selected_dataset_detail(self, dataset_path: str) -> None:
        self.selected_dataset_detail_var.set(build_dataset_detail_text(dataset_path, self.data_frames, self.dataset_contexts))

    def _open_selected_dataset_in_analysis(self) -> None:
        selected_path = self._get_selected_summary_dataset_path()
        if selected_path is None:
            self.notifications.warning("Select a dataset row first")
            return
        if self.on_open_dataset is None:
            self.notifications.warning("Opening the selected dataset in analysis is unavailable here")
            return
        self.on_open_dataset(selected_path)


def _get_frame_columns(dataframe: pd.DataFrame, *, numeric_only: bool) -> list[str]:
    columns = dataframe.select_dtypes(include="number").columns if numeric_only else dataframe.columns
    return [str(column_name) for column_name in columns]


def build_dataset_detail_text(
    dataset_path: str,
    data_frames: dict[str, pd.DataFrame],
    dataset_contexts: dict[str, object],
) -> str:
    """Build a compact dataset detail block for the comparison sidebar."""

    dataframe = data_frames.get(dataset_path)
    context = dataset_contexts.get(dataset_path)
    source_paths = getattr(context, "source_paths", [dataset_path]) if context is not None else [dataset_path]
    description = getattr(context, "description", "") if context is not None else ""
    row_text = f"Rows: {len(dataframe)}" if dataframe is not None else "Rows: n/a"
    column_text = f"Cols: {len(dataframe.columns)}" if dataframe is not None else "Cols: n/a"
    source_text = ", ".join(os.path.basename(path) for path in source_paths)
    parts = [
        f"Dataset: {os.path.basename(dataset_path)}",
        row_text,
        column_text,
        f"Session path: {dataset_path}",
        f"Lineage: {source_text}",
    ]
    if description:
        parts.append(f"Notes: {description}")
    return "\n".join(parts)
