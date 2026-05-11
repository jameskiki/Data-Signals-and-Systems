"""User-triggered operations and workflow logic for datapreparation_app."""
import os
from tkinter import filedialog, messagebox
from .demo import DEMO_DATASET_SPECS, INPUT_OUTPUT_DEMO, SPECTRAL_REFERENCE_DEMO, create_demo_dataset
from .data_parser import DataParser
from .datasets import DatasetContext, register_dataset, select_dataset_in_table, refresh_dataset_table, summarize_column_roles, collect_source_paths, build_virtual_dataset_path
from .preparation import create_prepared_dataset as create_prepared_dataset_workflow, split_selected_dataset as split_selected_dataset_workflow
from .plotting import PlotOptionsDialog, show_figure_in_window
from .preview import refresh_preview_table, clear_preview_plot, clear_preview_table, refresh_preview_plot, refresh_preview_plot_signal_controls
from data_ops.io_ops import analyze_selected_dataframes, export_clean_dataframes
from data_ops.models import AnalysisResult
from shared.plot_utils import create_plot_figure

def load_files(app) -> None:
	files = filedialog.askopenfilenames(filetypes=app.LOG_FILE_TYPES)
	loaded_file_paths: list[str] = []
	parse_info: list[str] = []
	for file_path in files:
		try:
			dataframe, separator, decimal_marker = DataParser.load_file(file_path)
			register_dataset(
				app,
				file_path,
				dataframe,
				source_paths=[file_path],
				description="Loaded source dataset",
			)
			loaded_file_paths.append(file_path)
			parse_info.append(f"{os.path.basename(file_path)}: sep='{separator}', decimal='{decimal_marker}'")
		except Exception as error:
			messagebox.showerror("Error", f"Failed to load {file_path}: {error}")

	refresh_dataset_table(app)
	if not loaded_file_paths:
		return

	analysis_result = analyze_selected_dataframes(loaded_file_paths, app.data_frames)
	select_dataset_in_table(app, loaded_file_paths[-1])
	app._refresh_dataset_preparation_views()
	messagebox.showinfo("Load summary", "\n".join([" | ".join(parse_info), analysis_result.report_text]))

def load_demo_test_signal(app) -> None:
	_load_demo_dataset(app, SPECTRAL_REFERENCE_DEMO.key)

def load_demo_input_output_signal(app) -> None:
	_load_demo_dataset(app, INPUT_OUTPUT_DEMO.key)

def load_all_demo_test_signals(app) -> None:
	loaded_paths: list[str] = []
	for spec in DEMO_DATASET_SPECS:
		dataset_path = _load_demo_dataset(app, spec.key, show_message=False)
		loaded_paths.append(dataset_path)

	refresh_dataset_table(app)
	if loaded_paths:
		select_dataset_in_table(app, loaded_paths[-1])
	app._refresh_dataset_preparation_views()
	messagebox.showinfo(
		"Demo/Test Signals Loaded",
		"\n".join(
			[
				f"Loaded {len(loaded_paths)} synthetic validation datasets:",
				*[f"- {os.path.basename(path)}" for path in loaded_paths],
			]
		),
	)

def _load_demo_dataset(app, demo_key: str, show_message: bool = True) -> str:
	spec, dataframe = create_demo_dataset(demo_key)
	demo_source_path = os.path.join(os.getcwd(), spec.basename)
	dataset_path = build_virtual_dataset_path(app.data_frames, demo_source_path, spec.suffix)

	register_dataset(
		app,
		dataset_path,
		dataframe,
		source_paths=[demo_source_path],
		description=spec.description,
		column_roles=spec.column_roles,
	)

	if show_message:
		refresh_dataset_table(app)
		select_dataset_in_table(app, dataset_path)
		app._refresh_dataset_preparation_views()
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

def plot_selected_data(app) -> None:
	selected_file_paths = app._get_multiple_selected_file_paths("Select one or more files first")
	if not selected_file_paths:
		return

	options = PlotOptionsDialog(app.root, app.data_frames[selected_file_paths[0]], app.PLOT_WINDOW_TITLE).show()
	if options is None or not options.cols_to_plot:
		return

	figure = create_plot_figure(
		options,
		selected_file_paths,
		app.data_frames,
		column_roles=(
			app.dataset_contexts.get(selected_file_paths[0], DatasetContext()).column_roles
			if len(selected_file_paths) == 1
			else None
		),
	)
	show_figure_in_window(app.root, figure, app.PLOT_WINDOW_TITLE, app.PLOT_WINDOW_GEOMETRY)

def merge_selected_files(app) -> None:
	selected_file_paths = app._get_multiple_selected_file_paths("Select files to merge")
	if not selected_file_paths:
		return
	if len(selected_file_paths) < 2:
		messagebox.showwarning("Warning", "Select at least two files to merge")
		return

	save_path = filedialog.asksaveasfilename(
		title="Save merged CSV",
		defaultextension=".csv",
		filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
	)
	if not save_path:
		return

	analysis_result: AnalysisResult = analyze_selected_dataframes(selected_file_paths, app.data_frames)
	register_dataset(
		app,
		save_path,
		analysis_result.merged_frame,
		source_paths=collect_source_paths(app, selected_file_paths),
		description=f"Merged from {len(selected_file_paths)} datasets",
	)
	try:
		analysis_result.merged_frame.to_csv(save_path, sep=";", index=False)
	except OSError as error:
		messagebox.showerror("Save Error", f"Could not write merged file:\n{error}\n\nCheck the path is valid and the file is not open elsewhere.")
		return
	refresh_dataset_table(app)
	select_dataset_in_table(app, save_path)
	app._refresh_dataset_preparation_views()
	messagebox.showinfo("Saved", f"Merged file saved to:\n{save_path}")

def create_prepared_dataset(app) -> None:
	try:
		prepared_path = create_prepared_dataset_workflow(app)
	except Exception as error:
		messagebox.showerror("Create Dataset Error", str(error))
		return
	if prepared_path is not None:
		messagebox.showinfo("Prepared Dataset", f"Created dataset:\n{os.path.basename(prepared_path)}")

def split_selected_dataset(app) -> None:
	split_options = app._prompt_split_subframes_options()
	if split_options is None:
		return

	try:
		created_paths = split_selected_dataset_workflow(
			app,
			prefix=split_options["prefix"],
			raw_ranges_text=split_options["ranges_text"],
		)
	except Exception as error:
		messagebox.showerror("Split Error", str(error))
		return
	messagebox.showinfo("Split Complete", f"Created {len(created_paths)} subframe dataset(s)")

def open_analysis_workspace(app) -> None:
	selected_path = app._get_single_selected_file_path("Select exactly one file first")
	if selected_path is None:
		return

	from analysis_app import AnalysisWorkspace

	workspace = AnalysisWorkspace(
		app.root,
		selected_path,
		app.data_frames[selected_path],
		column_roles=app.dataset_contexts.get(selected_path, DatasetContext()).column_roles,
		dataset_description=app.dataset_contexts.get(selected_path, DatasetContext()).description,
		on_close=app._on_analysis_workspace_closed,
	)
	app._analysis_workspaces.append(workspace)

def unload_selected_files(app) -> None:
	selected_file_paths = app._get_multiple_selected_file_paths("Select files to unload")
	if not selected_file_paths:
		return

	for path in selected_file_paths:
		app.data_frames.pop(path, None)
		app.dataset_contexts.pop(path, None)

	refresh_dataset_table(app)
	app._refresh_dataset_preparation_views()
	messagebox.showinfo("Unloaded", f"Unloaded {len(selected_file_paths)} file(s)")

def export_clean_data(app) -> None:
	if not app.data_frames:
		messagebox.showwarning("Warning", "No data loaded")
		return

	output_dir = filedialog.askdirectory(title="Select output directory")
	if not output_dir:
		return

	exported_count = export_clean_dataframes(app.data_frames, output_dir)
	messagebox.showinfo("Success", f"Exported {exported_count} files")

def apply_selected_column_role(app) -> None:
	selected_path = app._get_single_selected_file_path("Select exactly one dataset first")
	if selected_path is None:
		return

	column_name = app.session.role_editor_column.strip()
	role_name = app.session.role_editor_value.strip()
	if not column_name or not role_name:
		messagebox.showwarning("Warning", "Select a column and a role first")
		return

	context = app.dataset_contexts.get(selected_path)
	if context is None:
		return

	context.column_roles[column_name] = role_name
