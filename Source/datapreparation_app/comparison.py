"""Lightweight dataset comparison window for session datasets."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import matplotlib.pyplot as plt
import pandas as pd

from Source.data_ops.summary import build_statistics_frame, summarize_dataframe
from Source.shared.display_format import format_display_value
from Source.shared.notifications import NotificationManager
from Source.shared.plot_options import PlotOptions, PlotStyle
from Source.shared.plot_utils import create_plot_figure
from Source.shared.presentation_shell import PresentationShellMixin


COMPARISON_WINDOW_GEOMETRY = "1280x820"
COMPARISON_SELECTOR_MAX_ITEMS = 300


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
) -> pd.DataFrame:
    """Build a compact per-dataset summary frame for the comparison window."""

    if not dataset_paths:
        return pd.DataFrame(columns=["dataset", "rows", "cols", "missing", "mean", "std", "min", "max"])

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
                    }
                )
        rows.append(row)

    summary_frame = pd.DataFrame(rows).set_index("dataset_path")
    for column_name in ("mean", "std", "min", "max"):
        if column_name not in summary_frame.columns:
            summary_frame[column_name] = pd.NA
    return summary_frame[["dataset", "rows", "cols", "missing", "mean", "std", "min", "max"]]


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
        self.plot_column_summary_var = tk.StringVar(value="No common numeric channels")
        self.comparison_status_var = tk.StringVar(value="")
        self.selected_dataset_detail_var = tk.StringVar(value="Select a dataset row for details.")
        self._plot_column_selector_button: ttk.Menubutton | None = None
        self._plot_column_selector_menu: tk.Menu | None = None
        self._plot_column_selector_vars: dict[str, tk.BooleanVar] = {}
        self._plot_column_hidden_count = 0
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
        ttk.Label(
            controls,
            textvariable=self.comparison_status_var,
            wraplength=920,
            justify=tk.LEFT,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=5, pady=(2, 0))

        ttk.Label(controls, text="Shared X-axis").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.x_column_combo = ttk.Combobox(controls, textvariable=self.x_column_var, state="readonly")
        self.x_column_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.x_column_combo.bind("<<ComboboxSelected>>", lambda *_args: self._update_comparison_view())

        ttk.Label(controls, text="Summary column").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.summary_column_combo = ttk.Combobox(controls, textvariable=self.summary_column_var, state="readonly")
        self.summary_column_combo.grid(row=1, column=3, sticky="ew", padx=5, pady=5)
        self.summary_column_combo.bind("<<ComboboxSelected>>", lambda *_args: self._update_comparison_view())

        ttk.Label(controls, text="Signals").grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        selector_row = ttk.Frame(controls)
        selector_row.grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
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

        content_pane = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        content_pane.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        plot_frame = ttk.LabelFrame(content_pane, text="Overlay Plot", padding=5)
        summary_frame = ttk.LabelFrame(content_pane, text="Summary", padding=5)
        content_pane.add(plot_frame, weight=3)
        content_pane.add(summary_frame, weight=2)

        self.plot_container = ttk.Frame(plot_frame)
        self.plot_container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            summary_frame,
            text="Rows/cols/missing always reflect the full dataset. Mean/std/min/max use the selected summary column.",
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
        common_columns = get_common_columns(self.dataset_paths, self.data_frames)
        common_numeric_columns = get_common_columns(self.dataset_paths, self.data_frames, numeric_only=True)
        x_values = ["Index", *common_columns]
        self.x_column_combo.config(values=x_values)
        if self.x_column_var.get() not in x_values:
            self.x_column_var.set(resolve_default_x_column(self.dataset_paths, self.data_frames, self.dataset_contexts))

        self.summary_column_combo.config(values=["", *common_numeric_columns])
        if self.summary_column_var.get() not in ("", *common_numeric_columns):
            self.summary_column_var.set(common_numeric_columns[0] if common_numeric_columns else "")

        default_selected = self._get_selected_plot_columns()
        if not default_selected and common_numeric_columns:
            default_selected = common_numeric_columns[:1]
        self._plot_column_selector_vars, self._plot_column_hidden_count = self._build_checkbutton_selector_menu(
            menu=self._plot_column_selector_menu,
            button=self._plot_column_selector_button,
            items=common_numeric_columns,
            selected_items=default_selected,
            max_items=COMPARISON_SELECTOR_MAX_ITEMS,
            get_colors=lambda _name: ("white", "black"),
            on_changed=self._handle_plot_column_selection_changed,
            on_select_all=self._select_all_plot_columns,
            on_clear_selection=self._clear_plot_columns,
            hidden_label="signals",
        )
        self._update_plot_column_summary()

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
            self._render_summary_tree()
            self.selected_dataset_detail_var.set("At least two compared datasets must remain available in the session.")
            self._update_status_text()
            return
        selected_columns = self._get_selected_plot_columns()
        if not selected_columns:
            self._clear_plot()
            self._render_summary_tree()
            if get_common_columns(self.dataset_paths, self.data_frames, numeric_only=True):
                self.notifications.warning("Select at least one shared numeric signal")
            self._update_status_text()
            return

        figure = create_plot_figure(
            PlotOptions(
                cols_to_plot=selected_columns,
                xcol=self.x_column_var.get().strip() or "Index",
                use_subplots=False,
                title="Session Dataset Comparison",
                y_label="Value",
                style=self.default_style,
            ),
            self.dataset_paths,
            self.data_frames,
            column_roles=None,
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

    def _clear_plot(self) -> None:
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
        )
        columns = ["dataset", "rows", "cols", "missing", "mean", "std", "min", "max"]
        tree = ttk.Treeview(self.summary_container, columns=columns, show="headings", selectmode="browse")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.summary_container, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.bind("<<TreeviewSelect>>", self._handle_summary_tree_selection_changed)

        headings = {
            "dataset": "Dataset",
            "rows": "Rows",
            "cols": "Cols",
            "missing": "Missing",
            "mean": "Mean",
            "std": "Std",
            "min": "Min",
            "max": "Max",
        }
        widths = {
            "dataset": 180,
            "rows": 70,
            "cols": 60,
            "missing": 70,
            "mean": 80,
            "std": 80,
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
                    format_display_value(row["rows"]),
                    format_display_value(row["cols"]),
                    format_display_value(row["missing"]),
                    format_display_value(row["mean"]),
                    format_display_value(row["std"]),
                    format_display_value(row["min"]),
                    format_display_value(row["max"]),
                ],
            )
            self._summary_item_to_dataset_path[item_id] = dataset_path
        self._summary_tree = tree
        if self._summary_item_to_dataset_path:
            first_item = next(iter(self._summary_item_to_dataset_path))
            tree.selection_set(first_item)
            self._update_selected_dataset_detail(self._summary_item_to_dataset_path[first_item])

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

    def _update_status_text(self) -> None:
        self.comparison_status_var.set(
            f"Comparing {len(self.dataset_paths)} session datasets. "
            f"Session flow: selected datasets -> comparison view. "
            f"Use Refresh to re-read the current session data for these dataset paths. "
            f"Publish creates a new dataset entry in the main window; reopen comparison to include newly published datasets."
        )

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
