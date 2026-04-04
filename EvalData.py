"""
EvalData.py

Main GUI application for dataset parsing, structural preparation, plotting, and analysis.
"""

import os

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analysis_workspace import AnalysisWorkspace
from data_ops.io_ops import analyze_selected_dataframes, export_clean_dataframes
from data_ops.models import AnalysisResult
from data_ops.summary import summarize_dataframe
from data_parser import DataParser
from evaldata_demo import (
    DEMO_DATASET_SPECS,
    INPUT_OUTPUT_DEMO,
    SPECTRAL_REFERENCE_DEMO,
    create_demo_dataset,
)
from evaldata_datasets import (
    DatasetContext,
    apply_literal_role_combobox_style,
    apply_role_combobox_style,
    build_virtual_dataset_path,
    colorize_listbox_by_role,
    collect_source_paths,
    format_source_paths,
    get_available_column_roles,
    get_column_role_cell_colors,
    infer_column_roles,
    parse_split_ranges,
    refresh_dataset_table,
    register_dataset,
    select_dataset_in_table,
    summarize_column_roles,
)
from evaldata_layout import build_main_ui
from evaldata_plotting import PlotOptionsDialog, show_figure_in_window
from evaldata_preparation import (
    create_prepared_dataset as create_prepared_dataset_workflow,
    split_selected_dataset as split_selected_dataset_workflow,
)
from evaldata_preview import (
    clear_preview_plot,
    clear_preview_table,
    configure_preview_plot_scales,
    get_preview_plot_columns,
    get_preview_plot_range,
    handle_preview_plot_control_changed,
    handle_preview_plot_end_slider_changed,
    handle_preview_plot_start_slider_changed,
    refresh_preview_plot,
    refresh_preview_plot_signal_controls,
    refresh_preview_table,
    refresh_selected_dataset_preview_plot,
    reset_preview_plot_controls,
    sync_preview_plot_scales_from_entries,
)
from plot_utils import create_plot_figure


APP_TITLE = "Dataset Preparation and Analysis"
WINDOW_GEOMETRY = "1000x900"
PLOT_WINDOW_TITLE = "Plot"
PLOT_WINDOW_GEOMETRY = "900x600"
LOG_FILE_TYPES = [("Log files", "*.txt *.csv *.log"), ("All files", "*.*")]
PREVIEW_ROW_LIMIT = 200
PREVIEW_PLOT_MAX_COLUMNS = 3
PREVIEW_PLOT_FIGURE_SIZE = (7.4, 3.4)


class DataAnalysisApp:
    """Tkinter application for data parsing and structural preparation."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_GEOMETRY)

        self.data_frames: dict[str, pd.DataFrame] = {}
        self.dataset_contexts: dict[str, DatasetContext] = {}
        self._analysis_workspaces: list[AnalysisWorkspace] = []
        self._preview_plot_figure: plt.Figure | None = None
        self._preview_plot_canvas: FigureCanvasTkAgg | None = None

        self.selected_dataset_var = tk.StringVar(value="No dataset selected")
        self.dataset_shape_var = tk.StringVar(value="Select exactly one dataset for preparation")
        self.dataset_source_var = tk.StringVar(value="")
        self.dataset_note_var = tk.StringVar(value="")

        self.column_output_name_var = tk.StringVar()
        self.column_selection_summary_var = tk.StringVar(value="No dataset selected")
        self.role_editor_column_var = tk.StringVar(value="")
        self.role_editor_value_var = tk.StringVar(value="metadata")
        self.split_prefix_var = tk.StringVar(value="cycle")
        self.preview_plot_signal_summary_var = tk.StringVar(value="No dataset selected")
        self.preview_plot_start_var = tk.StringVar(value="0")
        self.preview_plot_end_var = tk.StringVar()
        self.preview_plot_start_scale_var = tk.DoubleVar(value=0)
        self.preview_plot_end_scale_var = tk.DoubleVar(value=1)
        self.preview_plot_range_summary_var = tk.StringVar(value="Output range: -")

        self._preview_table_container: ttk.Frame | None = None
        self._preview_plot_container: ttk.Frame | None = None
        self._preview_plot_signal_selector_button: ttk.Menubutton | None = None
        self._preview_plot_signal_selector_menu: tk.Menu | None = None
        self._preview_plot_signal_vars: dict[str, tk.BooleanVar] = {}
        self._preview_plot_signal_selector_sync_in_progress = False
        self._preview_plot_start_scale: tk.Scale | None = None
        self._preview_plot_end_scale: tk.Scale | None = None
        self._preview_plot_scale_sync_in_progress = False
        self.dataset_table: ttk.Treeview | None = None
        self.role_editor_column_combo: ttk.Combobox | None = None
        self.role_editor_value_combo: ttk.Combobox | None = None
        self._column_selector_button: ttk.Menubutton | None = None
        self._column_selector_menu: tk.Menu | None = None
        self._column_selection_vars: dict[str, tk.BooleanVar] = {}
        self._split_ranges_text: tk.Text | None = None

        build_main_ui(self, PREVIEW_ROW_LIMIT)
        self.role_editor_column_var.trace_add("write", self._handle_role_editor_column_changed)
        self.role_editor_value_var.trace_add("write", self._handle_role_editor_value_changed)
        self._refresh_dataset_preparation_views()

    def load_files(self) -> None:
        files = filedialog.askopenfilenames(filetypes=LOG_FILE_TYPES)
        loaded_file_paths: list[str] = []
        parse_info: list[str] = []
        for file_path in files:
            try:
                dataframe, separator, decimal_marker = DataParser.load_file(file_path)
                register_dataset(
                    self,
                    file_path,
                    dataframe,
                    source_paths=[file_path],
                    description="Loaded source dataset",
                )
                loaded_file_paths.append(file_path)
                parse_info.append(f"{os.path.basename(file_path)}: sep='{separator}', decimal='{decimal_marker}'")
            except Exception as error:
                messagebox.showerror("Error", f"Failed to load {file_path}: {error}")

        refresh_dataset_table(self)
        if not loaded_file_paths:
            return

        analysis_result = analyze_selected_dataframes(loaded_file_paths, self.data_frames)
        select_dataset_in_table(self, loaded_file_paths[-1])
        self._refresh_dataset_preparation_views()
        messagebox.showinfo("Load summary", "\n".join([" | ".join(parse_info), analysis_result.report_text]))

    def load_demo_test_signal(self) -> None:
        self._load_demo_dataset(SPECTRAL_REFERENCE_DEMO.key)

    def load_demo_input_output_signal(self) -> None:
        self._load_demo_dataset(INPUT_OUTPUT_DEMO.key)

    def load_all_demo_test_signals(self) -> None:
        loaded_paths: list[str] = []
        for spec in DEMO_DATASET_SPECS:
            dataset_path = self._load_demo_dataset(spec.key, show_message=False)
            loaded_paths.append(dataset_path)

        refresh_dataset_table(self)
        if loaded_paths:
            select_dataset_in_table(self, loaded_paths[-1])
        self._refresh_dataset_preparation_views()
        messagebox.showinfo(
            "Demo/Test Signals Loaded",
            "\n".join(
                [
                    f"Loaded {len(loaded_paths)} synthetic validation datasets:",
                    *[f"- {os.path.basename(path)}" for path in loaded_paths],
                ]
            ),
        )

    def _load_demo_dataset(self, demo_key: str, show_message: bool = True) -> str:
        spec, dataframe = create_demo_dataset(demo_key)
        demo_source_path = os.path.join(os.getcwd(), spec.basename)
        dataset_path = build_virtual_dataset_path(self.data_frames, demo_source_path, spec.suffix)

        register_dataset(
            self,
            dataset_path,
            dataframe,
            source_paths=[demo_source_path],
            description=spec.description,
            column_roles=spec.column_roles,
        )

        if show_message:
            refresh_dataset_table(self)
            select_dataset_in_table(self, dataset_path)
            self._refresh_dataset_preparation_views()
            messagebox.showinfo(
                "Demo/Test Signal Loaded",
                "\n".join(
                    [
                        f"Created synthetic validation dataset:\n{os.path.basename(dataset_path)}",
                        "",
                        spec.summary,
                        "",
                        f"Rows: {len(dataframe)}",
                    ]
                ),
            )
        return dataset_path

    def plot_selected_data(self) -> None:
        selected_file_paths = self._get_selected_file_paths("Select one or more files first")
        if not selected_file_paths:
            return

        options = PlotOptionsDialog(self.root, self.data_frames[selected_file_paths[0]], PLOT_WINDOW_TITLE).show()
        if options is None or not options.cols_to_plot:
            return

        figure = create_plot_figure(
            selected_file_paths,
            self.data_frames,
            options.cols_to_plot,
            options.xcol,
            use_subplots=options.use_subplots,
            column_roles=(
                self.dataset_contexts.get(selected_file_paths[0], DatasetContext()).column_roles
                if len(selected_file_paths) == 1
                else None
            ),
        )
        self.render_figure_in_window(figure)

    def render_figure_in_window(self, figure: plt.Figure) -> None:
        show_figure_in_window(self.root, figure, PLOT_WINDOW_TITLE, PLOT_WINDOW_GEOMETRY)

    def merge_selected_files(self) -> None:
        selected_file_paths = self._get_selected_file_paths("Select one or more files first")
        if not selected_file_paths:
            return
        if len(selected_file_paths) < 2:
            messagebox.showwarning("Warning", "Select at least two files to merge")
            return

        analysis_result: AnalysisResult = analyze_selected_dataframes(selected_file_paths, self.data_frames)
        save_path = filedialog.asksaveasfilename(
            title="Save merged CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not save_path:
            return

        register_dataset(
            self,
            save_path,
            analysis_result.merged_frame.copy(),
            source_paths=collect_source_paths(self, selected_file_paths),
            description=f"Merged from {len(selected_file_paths)} datasets",
        )
        analysis_result.merged_frame.to_csv(save_path, sep=";", index=False)
        refresh_dataset_table(self)
        select_dataset_in_table(self, save_path)
        self._refresh_dataset_preparation_views()
        messagebox.showinfo("Saved", f"Merged file saved to:\n{save_path}")

    def create_prepared_dataset(self) -> None:
        try:
            prepared_path = create_prepared_dataset_workflow(self)
        except Exception as error:
            messagebox.showerror("Create Dataset Error", str(error))
            return
        if prepared_path is not None:
            messagebox.showinfo("Prepared Dataset", f"Created dataset:\n{os.path.basename(prepared_path)}")

    def split_selected_dataset(self) -> None:
        try:
            created_paths = split_selected_dataset_workflow(self)
        except Exception as error:
            messagebox.showerror("Split Error", str(error))
            return
        messagebox.showinfo("Split Complete", f"Created {len(created_paths)} subframe dataset(s)")

    def open_analysis_workspace(self) -> None:
        selected_path = self._get_single_selected_file_path("Select exactly one file first")
        if selected_path is None:
            return

        workspace = AnalysisWorkspace(
            self.root,
            selected_path,
            self.data_frames[selected_path],
            column_roles=self.dataset_contexts.get(selected_path, DatasetContext()).column_roles,
            dataset_description=self.dataset_contexts.get(selected_path, DatasetContext()).description,
            on_close=self._on_analysis_workspace_closed,
        )
        self._analysis_workspaces.append(workspace)

    def unload_selected_files(self) -> None:
        selected_file_paths = self._get_selected_file_paths("Select one or more files to unload")
        if not selected_file_paths:
            return

        for path in selected_file_paths:
            self.data_frames.pop(path, None)
            self.dataset_contexts.pop(path, None)

        refresh_dataset_table(self)
        self._refresh_dataset_preparation_views()
        messagebox.showinfo("Unloaded", f"Unloaded {len(selected_file_paths)} file(s)")

    def export_clean_data(self) -> None:
        if not self.data_frames:
            messagebox.showwarning("Warning", "No data loaded")
            return

        output_dir = filedialog.askdirectory(title="Select output directory")
        if not output_dir:
            return

        exported_count = export_clean_dataframes(self.data_frames, output_dir)
        messagebox.showinfo("Success", f"Exported {exported_count} files")

    def _refresh_dataset_preparation_views(self) -> None:
        selected_path = self._get_single_selected_file_path()
        if selected_path is None:
            self._clear_preparation_views()
            return

        dataframe = self.data_frames[selected_path]
        context = self.dataset_contexts.get(selected_path, DatasetContext(source_paths=[selected_path], description=""))

        self.selected_dataset_var.set(os.path.basename(selected_path))
        self.dataset_shape_var.set(f"Shape: {dataframe.shape[0]} rows x {dataframe.shape[1]} columns")
        self.dataset_source_var.set(format_source_paths(context.source_paths))
        note_parts = [part for part in [context.description, summarize_column_roles(context.column_roles)] if part]
        self.dataset_note_var.set("\n".join(note_parts))
        self._refresh_role_editor(dataframe, context.column_roles)
        refresh_preview_table(self, dataframe, PREVIEW_ROW_LIMIT, context.column_roles)
        self._refresh_dataset_controls(dataframe)
        refresh_selected_dataset_preview_plot(self, PREVIEW_PLOT_FIGURE_SIZE, PREVIEW_PLOT_MAX_COLUMNS)

    def _clear_preparation_views(self) -> None:
        message = "Select exactly one dataset to preview or structurally prepare it."
        self.selected_dataset_var.set("No dataset selected")
        self.dataset_shape_var.set(message)
        self.dataset_source_var.set("")
        self.dataset_note_var.set("")
        self._clear_role_editor()
        clear_preview_plot(self, message)
        clear_preview_table(self, message)
        configure_preview_plot_scales(self, 1)
        self._clear_preview_plot_signal_selector()
        self._clear_column_selector()
        self.preview_plot_range_summary_var.set("Output range: -")

    def _refresh_dataset_controls(self, dataframe: pd.DataFrame) -> None:
        if self._column_selector_menu is None:
            return

        selected_path = self._get_single_selected_file_path()

        columns = [str(column) for column in dataframe.columns]
        self._populate_column_selector(
            columns,
            self.dataset_contexts.get(selected_path or "", DatasetContext()).column_roles,
        )

        refresh_preview_plot_signal_controls(
            self,
            dataframe,
            PREVIEW_PLOT_MAX_COLUMNS,
            self.dataset_contexts.get(selected_path or "", DatasetContext()).column_roles,
        )

        if not self.column_output_name_var.get().strip():
            self.column_output_name_var.set("prepared_dataset")

        row_count = len(dataframe)
        self._sync_preview_plot_scales_from_entries(row_count)
        self._update_range_summaries()

    def _update_range_summaries(self) -> None:
        selected_path = self._get_single_selected_file_path()
        if selected_path is None or selected_path not in self.data_frames:
            self.preview_plot_range_summary_var.set("Output range: -")
            return

        row_count = len(self.data_frames[selected_path])
        try:
            plot_start, plot_end = get_preview_plot_range(self, row_count)
            self.preview_plot_range_summary_var.set(
                f"Output range: [{plot_start}, {plot_end})  width {plot_end - plot_start}"
            )
        except ValueError:
            self.preview_plot_range_summary_var.set("Output range: invalid")

    def _populate_column_selector(self, columns: list[str], column_roles: dict[str, str]) -> None:
        if self._column_selector_menu is None or self._column_selector_button is None:
            return

        self._column_selection_vars = {}
        self._column_selector_menu.delete(0, tk.END)

        if not columns:
            self._clear_column_selector()
            return

        self._column_selector_menu.add_command(label="Select all", command=self._select_all_columns)
        self._column_selector_menu.add_command(label="Clear selection", command=self._clear_selected_columns)
        self._column_selector_menu.add_separator()

        for column_name in columns:
            variable = tk.BooleanVar(value=False)
            variable.trace_add("write", self._handle_column_selector_changed)
            self._column_selection_vars[column_name] = variable
            background, foreground = self._get_column_selector_colors(column_name, column_roles)
            self._column_selector_menu.add_checkbutton(
                label=column_name,
                variable=variable,
                onvalue=True,
                offvalue=False,
                background=background,
                foreground=foreground,
                activebackground=background,
                activeforeground=foreground,
                selectcolor=background,
            )

        self._column_selector_button.state(["!disabled"])
        self._update_column_selection_summary()

    def _clear_column_selector(self) -> None:
        self._column_selection_vars = {}
        if self._column_selector_menu is not None:
            self._column_selector_menu.delete(0, tk.END)
        if self._column_selector_button is not None:
            self._column_selector_button.state(["disabled"])
        self.column_selection_summary_var.set("No columns available")

    def _set_preview_plot_signal_options(
        self,
        columns: list[str],
        column_roles: dict[str, str],
        max_columns: int,
    ) -> None:
        if self._preview_plot_signal_selector_menu is None or self._preview_plot_signal_selector_button is None:
            return

        self._preview_plot_signal_vars = {}
        self._preview_plot_signal_selector_menu.delete(0, tk.END)

        if not columns:
            self._clear_preview_plot_signal_selector()
            return

        self._preview_plot_signal_selector_menu.add_command(label="Select all", command=self._select_all_preview_plot_signals)
        self._preview_plot_signal_selector_menu.add_command(label="Clear selection", command=self._clear_selected_preview_plot_signals)
        self._preview_plot_signal_selector_menu.add_separator()

        selected_columns = set(columns[:max_columns])
        self._preview_plot_signal_selector_sync_in_progress = True
        for column_name in columns:
            variable = tk.BooleanVar(value=column_name in selected_columns)
            variable.trace_add("write", self._handle_preview_plot_signal_selector_changed)
            self._preview_plot_signal_vars[column_name] = variable
            background, foreground = self._get_column_selector_colors(column_name, column_roles)
            self._preview_plot_signal_selector_menu.add_checkbutton(
                label=column_name,
                variable=variable,
                onvalue=True,
                offvalue=False,
                background=background,
                foreground=foreground,
                activebackground=background,
                activeforeground=foreground,
                selectcolor=background,
            )
        self._preview_plot_signal_selector_sync_in_progress = False

        self._preview_plot_signal_selector_button.state(["!disabled"])
        self._update_preview_plot_signal_summary()

    def _clear_preview_plot_signal_selector(self) -> None:
        self._preview_plot_signal_vars = {}
        if self._preview_plot_signal_selector_menu is not None:
            self._preview_plot_signal_selector_menu.delete(0, tk.END)
        if self._preview_plot_signal_selector_button is not None:
            self._preview_plot_signal_selector_button.state(["disabled"])
        self.preview_plot_signal_summary_var.set("No channels available")

    def _handle_preview_plot_signal_selector_changed(self, *_args: object) -> None:
        self._update_preview_plot_signal_summary()
        if not self._preview_plot_signal_selector_sync_in_progress:
            self._handle_preview_plot_control_changed()

    def _update_preview_plot_signal_summary(self) -> None:
        selected_columns = self._get_selected_preview_plot_columns_from_selector()
        if not self._preview_plot_signal_vars:
            self.preview_plot_signal_summary_var.set("No channels available")
            return
        if not selected_columns:
            self.preview_plot_signal_summary_var.set("Choose channels")
            return
        if len(selected_columns) <= 2:
            self.preview_plot_signal_summary_var.set(", ".join(selected_columns))
            return
        shown_columns = ", ".join(selected_columns[:2])
        self.preview_plot_signal_summary_var.set(
            f"{len(selected_columns)} selected: {shown_columns}, +{len(selected_columns) - 2}"
        )

    def _select_all_preview_plot_signals(self) -> None:
        self._preview_plot_signal_selector_sync_in_progress = True
        for variable in self._preview_plot_signal_vars.values():
            variable.set(True)
        self._preview_plot_signal_selector_sync_in_progress = False
        self._update_preview_plot_signal_summary()
        self._handle_preview_plot_control_changed()

    def _clear_selected_preview_plot_signals(self) -> None:
        self._preview_plot_signal_selector_sync_in_progress = True
        for variable in self._preview_plot_signal_vars.values():
            variable.set(False)
        self._preview_plot_signal_selector_sync_in_progress = False
        self._update_preview_plot_signal_summary()
        self._handle_preview_plot_control_changed()

    def _get_selected_preview_plot_columns_from_selector(self) -> list[str]:
        return [column for column, variable in self._preview_plot_signal_vars.items() if variable.get()]

    def _handle_column_selector_changed(self, *_args: object) -> None:
        self._update_column_selection_summary()

    def _update_column_selection_summary(self) -> None:
        selected_columns = self._get_selected_column_names()
        if not self._column_selection_vars:
            self.column_selection_summary_var.set("No columns available")
            return
        if not selected_columns:
            self.column_selection_summary_var.set("Choose columns")
            return
        if len(selected_columns) <= 2:
            self.column_selection_summary_var.set(", ".join(selected_columns))
            return
        shown_columns = ", ".join(selected_columns[:2])
        self.column_selection_summary_var.set(f"{len(selected_columns)} selected: {shown_columns}, +{len(selected_columns) - 2}")

    def _select_all_columns(self) -> None:
        for variable in self._column_selection_vars.values():
            variable.set(True)
        self._update_column_selection_summary()

    def _clear_selected_columns(self) -> None:
        for variable in self._column_selection_vars.values():
            variable.set(False)
        self._update_column_selection_summary()

    def _get_column_selector_colors(self, column_name: str, column_roles: dict[str, str]) -> tuple[str, str]:
        if not column_name:
            return ("#f8fafc", "#111111")
        if column_name not in column_roles:
            return ("#f8fafc", "#111111")
        return get_column_role_cell_colors(column_roles.get(column_name, "metadata"))

    def _handle_file_selection_changed(self, _event: tk.Event | None = None) -> None:
        self._refresh_dataset_preparation_views()

    def _refresh_role_editor(self, dataframe: pd.DataFrame, column_roles: dict[str, str]) -> None:
        if self.role_editor_column_combo is None or self.role_editor_value_combo is None:
            return

        columns = [str(column) for column in dataframe.columns]
        self.role_editor_column_combo.configure(values=columns)
        self.role_editor_value_combo.configure(values=get_available_column_roles())

        selected_column = self.role_editor_column_var.get().strip()
        if selected_column not in columns:
            selected_column = columns[0] if columns else ""
            self.role_editor_column_var.set(selected_column)

        selected_role = column_roles.get(selected_column, "metadata") if selected_column else "metadata"
        if self.role_editor_value_var.get().strip() != selected_role:
            self.role_editor_value_var.set(selected_role)

        self._refresh_role_editor_styles(column_roles)

    def _clear_role_editor(self) -> None:
        if self.role_editor_column_combo is not None:
            self.role_editor_column_combo.configure(values=[])
        if self.role_editor_value_combo is not None:
            self.role_editor_value_combo.configure(values=get_available_column_roles())
        self.role_editor_column_var.set("")
        self.role_editor_value_var.set("metadata")
        self._refresh_role_editor_styles({})

    def _refresh_role_editor_styles(self, column_roles: dict[str, str]) -> None:
        apply_role_combobox_style(self.role_editor_column_combo, column_roles, self.role_editor_column_var.get().strip())
        apply_literal_role_combobox_style(self.role_editor_value_combo, self.role_editor_value_var.get().strip() or "metadata")

    def _handle_role_editor_column_changed(self, *_args: object) -> None:
        selected_path = self._get_single_selected_file_path()
        if selected_path is None:
            self._refresh_role_editor_styles({})
            return
        context = self.dataset_contexts.get(selected_path, DatasetContext())
        column_name = self.role_editor_column_var.get().strip()
        if column_name:
            self.role_editor_value_var.set(context.column_roles.get(column_name, "metadata"))
        self._refresh_role_editor_styles(context.column_roles)

    def _handle_role_editor_value_changed(self, *_args: object) -> None:
        selected_path = self._get_single_selected_file_path()
        context = self.dataset_contexts.get(selected_path, DatasetContext()) if selected_path else DatasetContext()
        self._refresh_role_editor_styles(context.column_roles)

    def apply_selected_column_role(self) -> None:
        selected_path = self._get_single_selected_file_path("Select exactly one dataset first")
        if selected_path is None:
            return

        column_name = self.role_editor_column_var.get().strip()
        role_name = self.role_editor_value_var.get().strip()
        if not column_name or not role_name:
            messagebox.showwarning("Warning", "Select a column and a role first")
            return

        context = self.dataset_contexts.get(selected_path)
        if context is None:
            return

        context.column_roles[column_name] = role_name
        self._propagate_role_updates(selected_path, context.column_roles)
        self._refresh_dataset_preparation_views()

    def reinfer_selected_dataset_roles(self) -> None:
        selected_path = self._get_single_selected_file_path("Select exactly one dataset first")
        if selected_path is None:
            return

        context = self.dataset_contexts.get(selected_path)
        dataframe = self.data_frames.get(selected_path)
        if context is None or dataframe is None:
            return

        context.column_roles = infer_column_roles(dataframe)
        self._propagate_role_updates(selected_path, context.column_roles)
        self._refresh_dataset_preparation_views()

    def _propagate_role_updates(self, dataset_path: str, column_roles: dict[str, str]) -> None:
        for workspace in self._analysis_workspaces:
            if workspace.session.source_path != dataset_path:
                continue
            workspace.column_roles = dict(column_roles)
            workspace._refresh_all_views()
            workspace._refresh_live_plot()

    def _get_selected_file_paths(self, warning_message: str | None = None) -> list[str]:
        if self.dataset_table is None:
            return []

        selection = self.dataset_table.selection()
        if not selection:
            if warning_message:
                messagebox.showwarning("Warning", warning_message)
            return []

        selected_paths: list[str] = []
        for item_id in selection:
            dataset_path = self.dataset_table.set(item_id, "dataset")
            if dataset_path in self.data_frames:
                selected_paths.append(dataset_path)
        return selected_paths

    def _get_single_selected_file_path(self, warning_message: str | None = None) -> str | None:
        selected_file_paths = self._get_selected_file_paths(warning_message)
        if not selected_file_paths:
            return None
        if len(selected_file_paths) != 1:
            if warning_message:
                messagebox.showwarning("Warning", warning_message)
            return None
        return selected_file_paths[0]

    def _refresh_file_listbox(self) -> None:
        refresh_dataset_table(self)

    def _get_selected_column_names(self) -> list[str]:
        return [column for column, variable in self._column_selection_vars.items() if variable.get()]

    def _select_file_in_listbox(self, file_path: str) -> None:
        select_dataset_in_table(self, file_path)

    def _refresh_preview_plot(self, dataframe: pd.DataFrame) -> None:
        selected_path = self._get_single_selected_file_path()
        refresh_preview_plot(
            self,
            dataframe,
            PREVIEW_PLOT_FIGURE_SIZE,
            PREVIEW_PLOT_MAX_COLUMNS,
            self.dataset_contexts.get(selected_path or "", DatasetContext()).column_roles,
        )

    def _refresh_preview_plot_signal_controls(self, dataframe: pd.DataFrame) -> None:
        selected_path = self._get_single_selected_file_path()
        refresh_preview_plot_signal_controls(
            self,
            dataframe,
            PREVIEW_PLOT_MAX_COLUMNS,
            self.dataset_contexts.get(selected_path or "", DatasetContext()).column_roles,
        )

    def _refresh_selected_dataset_preview_plot(self) -> None:
        refresh_selected_dataset_preview_plot(self, PREVIEW_PLOT_FIGURE_SIZE, PREVIEW_PLOT_MAX_COLUMNS)

    def _reset_preview_plot_controls(self) -> None:
        reset_preview_plot_controls(self, PREVIEW_PLOT_FIGURE_SIZE, PREVIEW_PLOT_MAX_COLUMNS)

    def _handle_preview_plot_control_changed(self, _event: tk.Event | None = None) -> None:
        handle_preview_plot_control_changed(self, PREVIEW_PLOT_FIGURE_SIZE, PREVIEW_PLOT_MAX_COLUMNS)

    def _handle_preview_plot_start_slider_changed(self, value: str) -> None:
        handle_preview_plot_start_slider_changed(self, value, PREVIEW_PLOT_FIGURE_SIZE, PREVIEW_PLOT_MAX_COLUMNS)

    def _handle_preview_plot_end_slider_changed(self, value: str) -> None:
        handle_preview_plot_end_slider_changed(self, value, PREVIEW_PLOT_FIGURE_SIZE, PREVIEW_PLOT_MAX_COLUMNS)

    def _configure_preview_plot_scales(self, row_count: int) -> None:
        configure_preview_plot_scales(self, row_count)

    def _sync_preview_plot_scales_from_entries(self, row_count: int) -> None:
        sync_preview_plot_scales_from_entries(self, row_count)

    def _get_preview_plot_range(self, row_count: int) -> tuple[int, int]:
        return get_preview_plot_range(self, row_count)

    def _get_selected_preview_plot_columns(self, dataframe: pd.DataFrame) -> list[str]:
        from evaldata_preview import get_selected_preview_plot_columns

        return get_selected_preview_plot_columns(self, dataframe, PREVIEW_PLOT_MAX_COLUMNS)

    def _clear_preview_plot(self, message: str | None = None) -> None:
        clear_preview_plot(self, message)

    def _refresh_preview_table(self, dataframe: pd.DataFrame) -> None:
        selected_path = self._get_single_selected_file_path()
        column_roles = self.dataset_contexts.get(selected_path, DatasetContext()).column_roles if selected_path else {}
        refresh_preview_table(self, dataframe, PREVIEW_ROW_LIMIT, column_roles)

    def _clear_preview_table(self, message: str | None = None) -> None:
        clear_preview_table(self, message)

    def _on_analysis_workspace_closed(self, workspace: AnalysisWorkspace) -> None:
        if workspace in self._analysis_workspaces:
            self._analysis_workspaces.remove(workspace)

    @staticmethod
    def _get_preview_plot_columns(dataframe: pd.DataFrame) -> list[str]:
        return get_preview_plot_columns(dataframe)

    @staticmethod
    def _format_source_paths(source_paths: list[str]) -> str:
        return format_source_paths(source_paths)

    @staticmethod
    def _parse_split_ranges(raw_text: str) -> list[tuple[int, int]]:
        return parse_split_ranges(raw_text)


def main() -> None:
    root = tk.Tk()
    DataAnalysisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()