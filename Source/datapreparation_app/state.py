from dataclasses import dataclass, field


APP_TITLE = "Dataset Preparation and Analysis"
WINDOW_GEOMETRY = "1000x900"
PLOT_WINDOW_TITLE = "Plot"
PLOT_WINDOW_GEOMETRY = "900x600"
LOG_FILE_TYPES = [("Log files", "*.txt *.csv *.log"), ("All files", "*.*")]
PREVIEW_ROW_LIMIT = 200
PREVIEW_PLOT_MAX_COLUMNS = 3
PREVIEW_PLOT_FIGURE_SIZE = (7.4, 3.4)


@dataclass
class DataPreparationSession:
	"""Mutable workflow state for the dataset preparation window."""

	selected_dataset_path: str | None = None
	output_dataset_name: str = ""
	selected_columns: list[str] = field(default_factory=list)
	column_selection_summary: str = "No dataset selected"
	role_editor_column: str = ""
	role_editor_value: str = "metadata"
	split_prefix: str = "cycle"
	selected_preview_plot_columns: list[str] = field(default_factory=list)
	preview_plot_signal_summary: str = "No dataset selected"
	row_range_start: str = ""
	row_range_end: str = ""
	row_range_label: str = "Row index"
