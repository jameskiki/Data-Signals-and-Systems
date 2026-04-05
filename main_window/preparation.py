"""Dataset preparation workflows for the main application."""

import os

from data_ops.frame_ops import select_dataframe_columns, split_dataframe_by_index_ranges
from .datasets import (
    build_virtual_dataset_path,
    collect_source_paths,
    parse_split_ranges,
    project_column_roles,
    refresh_dataset_table,
    register_dataset,
    select_dataset_in_table,
)


def get_selected_column_names(app) -> list[str]:
    """Return the currently selected column names from the main window selector."""

    if not hasattr(app, "_get_selected_column_names"):
        return []
    return app._get_selected_column_names()


def _get_source_column_roles(app, selected_path: str) -> dict[str, str]:
    context = app.dataset_contexts.get(selected_path)
    return dict(context.column_roles) if context is not None else {}


def create_prepared_dataset(app) -> str | None:
    """Create a dataset from the selected dataframe and optional column subset."""

    selected_path = app._get_single_selected_file_path("Select exactly one dataset first")
    if selected_path is None:
        return None

    source_frame = app.data_frames[selected_path]

    # Apply row-range filtering if set
    context = app.dataset_contexts.get(selected_path)
    column_roles = dict(context.column_roles) if context is not None else {}
    prepared_frame = app._get_row_range_filtered_frame(source_frame, column_roles)

    description_parts: list[str] = []

    start_text, end_text = app.get_row_range_for_preparation()
    if start_text or end_text:
        description_parts.append(f"range [{start_text or '0'}:{end_text or 'end'}]")

    selected_columns = get_selected_column_names(app)
    if selected_columns:
        prepared_frame = select_dataframe_columns(prepared_frame, selected_columns)
        description_parts.append(f"kept {len(selected_columns)} column(s)")

    output_name = app.column_output_name_var.get().strip() or "prepared_dataset"
    prepared_path = build_virtual_dataset_path(app.data_frames, selected_path, output_name)
    description = "; ".join(description_parts) or "Prepared dataset"
    register_dataset(
        app,
        prepared_path,
        prepared_frame,
        source_paths=collect_source_paths(app, [selected_path]),
        description=f"{description} from {os.path.basename(selected_path)}",
        column_roles=project_column_roles(_get_source_column_roles(app, selected_path), prepared_frame),
    )
    refresh_dataset_table(app)
    select_dataset_in_table(app, prepared_path)
    app._refresh_dataset_preparation_views()
    return prepared_path


def split_selected_dataset(app, raw_ranges_text: str, prefix: str | None = None) -> list[str]:
    """Split the selected dataset into multiple subframes based on ranges."""

    selected_path = app._get_single_selected_file_path("Select exactly one dataset first")
    if selected_path is None:
        return []

    ranges = parse_split_ranges(raw_ranges_text)
    split_frames = split_dataframe_by_index_ranges(app.data_frames[selected_path], ranges)

    resolved_prefix = (prefix or app.split_prefix_var.get()).strip() or "cycle"
    created_paths: list[str] = []
    for index, ((start_index, end_index), frame) in enumerate(split_frames, start=1):
        suffix = f"{resolved_prefix}_{index:03d}_{start_index}_{end_index}"
        prepared_path = build_virtual_dataset_path(app.data_frames, selected_path, suffix)
        register_dataset(
            app,
            prepared_path,
            frame,
            source_paths=collect_source_paths(app, [selected_path]),
            description=(
                f"Split from {os.path.basename(selected_path)} as {resolved_prefix} {index:03d} "
                f"for rows [{start_index}, {end_index})"
            ),
            column_roles=project_column_roles(_get_source_column_roles(app, selected_path), frame),
        )
        created_paths.append(prepared_path)

    refresh_dataset_table(app)
    if created_paths:
        select_dataset_in_table(app, created_paths[0])
    app._refresh_dataset_preparation_views()
    return created_paths
