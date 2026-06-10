"""User-triggered operations and workflow logic for datapreparation_app."""
import os
import queue
import threading
from tkinter import filedialog, messagebox
from .demo import DEMO_DATASET_SPECS, INPUT_OUTPUT_DEMO, SPECTRAL_REFERENCE_DEMO, create_demo_dataset
from .data_parser import DataParser
from .datasets import DatasetContext, register_dataset, select_dataset_in_table, refresh_dataset_table, summarize_column_roles, collect_source_paths, build_virtual_dataset_path
from .preparation import create_prepared_dataset as create_prepared_dataset_workflow, split_selected_dataset as split_selected_dataset_workflow
from .plotting import PlotOptionsDialog, show_figure_in_window
from .preview import refresh_preview_table, clear_preview_plot, clear_preview_table, refresh_preview_plot, refresh_preview_plot_signal_controls
from Source.data_ops.io_ops import analyze_selected_dataframes, merge_selected_dataframes, export_clean_dataframes, write_dataframe_csv_with_progress
from Source.shared.plot_utils import create_plot_figure

def load_files(app) -> None:
	files = filedialog.askopenfilenames(filetypes=app.LOG_FILE_TYPES)
	if not files:
		return

	(
		progress_dialog,
		overall_status_var,
		overall_progress_var,
		file_step_status_var,
		file_step_progress_var,
	) = app.create_loading_dialog("Loading Files", len(files))
	load_queue: queue.Queue[tuple[object, ...]] = queue.Queue()
	loaded_file_paths: list[str] = []
	parse_info: list[str] = []
	error_messages: list[str] = []
	worker_done = False
	finalized = False

	def _worker() -> None:
		for index, file_path in enumerate(files, start=1):
			def _on_parse_progress(current: float, total: float, label: str) -> None:
				load_queue.put(("file_progress", index, file_path, current, total, label))

			try:
				dataframe, separator, decimal_marker = DataParser.load_file(file_path, progress_callback=_on_parse_progress)
				load_queue.put(("loaded", index, file_path, separator, decimal_marker, dataframe))
			except Exception as error:
				load_queue.put(("error", index, file_path, str(error)))
		load_queue.put(("done",))

	threading.Thread(target=_worker, daemon=True).start()

	def _finalize_load() -> None:
		nonlocal finalized
		if finalized:
			return
		finalized = True
		app.close_loading_dialog(progress_dialog)
		refresh_dataset_table(app)
		if not loaded_file_paths:
			if error_messages:
				messagebox.showerror("Error", "\n\n".join(error_messages))
			return

		report_text = analyze_selected_dataframes(loaded_file_paths, app.data_frames)
		select_dataset_in_table(app, loaded_file_paths[-1])
		app._refresh_dataset_preparation_views()

		summary_lines = [" | ".join(parse_info), report_text]
		if error_messages:
			summary_lines.extend(["", "Warnings:", *error_messages])
		messagebox.showinfo("Load summary", "\n".join(summary_lines))

	def _poll_load_queue() -> None:
		nonlocal worker_done
		while True:
			try:
				message = load_queue.get_nowait()
			except queue.Empty:
				break

			message_type = message[0]
			if message_type == "loaded":
				_, index, file_path, separator, decimal_marker, dataframe = message
				register_dataset(
					app,
					file_path,
					dataframe,
					source_paths=[file_path],
					description="Loaded source dataset",
				)
				loaded_file_paths.append(file_path)
				parse_info.append(f"{os.path.basename(file_path)}: sep='{separator}', decimal='{decimal_marker}'")
				overall_progress_var.set(float(index))
				overall_status_var.set(f"Loaded {index} of {len(files)}: {os.path.basename(file_path)}")
				file_step_progress_var.set(100.0)
				file_step_status_var.set(f"Done: {os.path.basename(file_path)}")
			elif message_type == "error":
				_, index, file_path, error_text = message
				error_messages.append(f"Failed to load {file_path}: {error_text}")
				overall_status_var.set(f"Skipped {index} of {len(files)}: {os.path.basename(file_path)}")
				file_step_progress_var.set(0.0)
				file_step_status_var.set(f"Failed: {os.path.basename(file_path)}")
			elif message_type == "file_progress":
				_, index, file_path, current, total, label = message
				progress_percent = (float(current) / max(float(total), 1.0)) * 100.0
				file_step_progress_var.set(max(0.0, min(100.0, progress_percent)))
				file_step_status_var.set(f"{os.path.basename(file_path)} | {label}")
				overall_status_var.set(f"Processing {index} of {len(files)}: {os.path.basename(file_path)}")
			elif message_type == "done":
				worker_done = True

		if worker_done:
			_finalize_load()
		else:
			app.root.after(75, _poll_load_queue)

	_poll_load_queue()

def load_demo_test_signal(app) -> None:
	_load_demo_dataset(app, SPECTRAL_REFERENCE_DEMO.key)

def load_demo_input_output_signal(app) -> None:
	_load_demo_dataset(app, INPUT_OUTPUT_DEMO.key)

def load_all_demo_test_signals(app) -> None:
	loaded_paths: list[str] = []
	failed_keys: list[str] = []
	for spec in DEMO_DATASET_SPECS:
		try:
			dataset_path = _load_demo_dataset(app, spec.key, show_message=False)
			loaded_paths.append(dataset_path)
		except Exception as error:
			failed_keys.append(f"- {spec.key}: {error}")

	refresh_dataset_table(app)
	if loaded_paths:
		select_dataset_in_table(app, loaded_paths[-1])
	app._refresh_dataset_preparation_views()

	summary_lines = [f"Loaded {len(loaded_paths)} synthetic validation dataset(s):"]
	summary_lines += [f"- {os.path.basename(path)}" for path in loaded_paths]
	if failed_keys:
		summary_lines += ["", f"Failed to load {len(failed_keys)} dataset(s):"]
		summary_lines += failed_keys

	if failed_keys:
		messagebox.showwarning("Demo/Test Signals Loaded (with errors)", "\n".join(summary_lines))
	else:
		messagebox.showinfo("Demo/Test Signals Loaded", "\n".join(summary_lines))

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

	(
		progress_dialog,
		overall_status_var,
		overall_progress_var,
		detail_status_var,
		detail_progress_var,
	) = app.create_loading_dialog(
		"Merging Datasets",
		3,
		overall_label="Overall Merge Progress",
		detail_label="Current Step Progress",
		initial_status="Starting merge...",
		initial_detail_status="Preparing selected datasets...",
	)

	merge_queue: queue.Queue[tuple[object, ...]] = queue.Queue()
	worker_done = False
	finalized = False
	merged_result: object | None = None
	error_message: str | None = None

	def _worker() -> None:
		try:
			merge_queue.put(("merge_started",))
			merged_frame = merge_selected_dataframes(selected_file_paths, app.data_frames)
			merge_queue.put(("merge_done",))

			def _on_write_progress(written_rows: int, total_rows: int) -> None:
				merge_queue.put(("write_progress", written_rows, total_rows))

			write_dataframe_csv_with_progress(
				merged_frame,
				save_path,
				sep=";",
				progress_callback=_on_write_progress,
			)
			merge_queue.put(("write_done",))
			merge_queue.put(("result", merged_frame))
		except OSError as error:
			merge_queue.put(("error", f"Could not write merged file:\n{error}\n\nCheck the path is valid and the file is not open elsewhere."))
		except Exception as error:
			merge_queue.put(("error", str(error)))
		finally:
			merge_queue.put(("done",))

	threading.Thread(target=_worker, daemon=True).start()

	def _finalize_merge() -> None:
		nonlocal finalized
		if finalized:
			return
		finalized = True
		app.close_loading_dialog(progress_dialog)

		if error_message is not None:
			messagebox.showerror("Save Error", error_message)
			return

		if merged_result is None:
			messagebox.showerror("Merge Error", "Merge did not produce a result.")
			return

		merged_frame = merged_result
		register_dataset(
			app,
			save_path,
			merged_frame,
			source_paths=collect_source_paths(app, selected_file_paths),
			description=f"Merged from {len(selected_file_paths)} datasets",
		)
		refresh_dataset_table(app)
		select_dataset_in_table(app, save_path)
		app._refresh_dataset_preparation_views()
		app.notifications.success(f"Merged file saved to: {os.path.basename(save_path)}")

	def _poll_merge_queue() -> None:
		nonlocal worker_done, merged_result, error_message
		while True:
			try:
				message = merge_queue.get_nowait()
			except queue.Empty:
				break

			message_type = message[0]
			if message_type == "merge_started":
				overall_status_var.set("Merging selected dataframes...")
				detail_status_var.set("Building merged dataframe")
				detail_progress_var.set(0.0)
			elif message_type == "merge_done":
				overall_progress_var.set(1.0)
				overall_status_var.set("Merge complete. Writing CSV...")
				detail_status_var.set("Writing merged data to disk")
			elif message_type == "write_progress":
				_, written_rows, total_rows = message
				if total_rows <= 0:
					detail_progress_var.set(100.0)
					detail_status_var.set("Writing rows: 0 / 0")
				else:
					percent = (float(written_rows) / float(total_rows)) * 100.0
					detail_progress_var.set(max(0.0, min(100.0, percent)))
					detail_status_var.set(f"Writing rows: {written_rows:,} / {total_rows:,}")
			elif message_type == "write_done":
				overall_progress_var.set(2.0)
				detail_progress_var.set(100.0)
				detail_status_var.set("CSV write complete")
				overall_status_var.set("Finalizing merged dataset...")
			elif message_type == "result":
				_, merged_result = message
				overall_progress_var.set(3.0)
				overall_status_var.set("Done")
			elif message_type == "error":
				_, error_message = message
			elif message_type == "done":
				worker_done = True

		if worker_done:
			_finalize_merge()
		else:
			app.root.after(75, _poll_merge_queue)

	_poll_merge_queue()

def create_prepared_dataset(app) -> None:
	try:
		prepared_path = create_prepared_dataset_workflow(app)
	except Exception as error:
		messagebox.showerror("Create Dataset Error", str(error))
		return
	if prepared_path is not None:
		app.notifications.success(f"Created dataset: {os.path.basename(prepared_path)}")

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
	app.notifications.success(f"Created {len(created_paths)} subframe dataset(s)")

def open_analysis_workspace(app) -> None:
	selected_path = app._get_single_selected_file_path("Select exactly one file first")
	if selected_path is None:
		return

	from Source.analysis_app.app import AnalysisWorkspace

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
	app.notifications.success(f"Unloaded {len(selected_file_paths)} file(s)")

def export_clean_data(app) -> None:
	if not app.data_frames:
		messagebox.showwarning("Warning", "No data loaded")
		return

	output_dir = filedialog.askdirectory(title="Select output directory")
	if not output_dir:
		return

	exported_count = export_clean_dataframes(app.data_frames, output_dir)
	app.notifications.success(f"Exported {exported_count} files")

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

	app._set_role_editor_column("", update_var=True)
	app._set_role_editor_value("", update_var=True)
	app._refresh_dataset_preparation_views()
	app.notifications.success(f"Role '{role_name}' applied to column '{column_name}'")
