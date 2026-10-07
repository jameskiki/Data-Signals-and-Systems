"""Multi-dataframe analysis and export helpers."""

import os
import re
import json
from collections.abc import Mapping
from collections.abc import Sequence
from collections.abc import Callable

import pandas as pd

from .models import DataFrameMap
from .summary import summarize_dataframe
from Source.shared.display_format import format_data_summary_overview


INVALID_FILENAME_PREFIX_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
PARQUET_EXTENSIONS = {".parquet", ".pq"}
PARQUET_ROLE_METADATA_KEY = b"evaldata.column_roles"
DATAFRAME_ROLE_ATTR = "evaldata_column_roles"


def is_parquet_path(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in PARQUET_EXTENSIONS


def read_dataframe_parquet(path: str) -> pd.DataFrame:
    """Read typed Parquet data and optional EvalData column roles."""

    import pyarrow.parquet as pq

    table = pq.read_table(path)
    metadata = table.schema.metadata or {}
    dataframe = table.to_pandas()
    if PARQUET_ROLE_METADATA_KEY in metadata:
        roles = json.loads(metadata[PARQUET_ROLE_METADATA_KEY].decode("utf-8"))
        if not isinstance(roles, dict) or not all(
            isinstance(column, str) and isinstance(role, str)
            for column, role in roles.items()
        ):
            raise ValueError("Invalid EvalData column-role metadata in Parquet file.")
        dataframe.attrs[DATAFRAME_ROLE_ATTR] = roles
    return dataframe


def write_dataframe_with_progress(
    dataframe: pd.DataFrame,
    output_path: str,
    sep: str = ";",
    chunk_size: int = 100_000,
    progress_callback: Callable[[int, int], None] | None = None,
    *,
    column_roles: Mapping[str, str] | None = None,
) -> None:
    """Write CSV or compressed Parquet according to the output extension."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if not is_parquet_path(output_path):
        write_dataframe_csv_with_progress(
            dataframe, output_path, sep, chunk_size, progress_callback,
        )
        return

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(dataframe, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    if column_roles is not None:
        roles = {column: role for column, role in column_roles.items() if column in dataframe.columns}
        metadata[PARQUET_ROLE_METADATA_KEY] = json.dumps(roles).encode("utf-8")
    table = table.replace_schema_metadata(metadata)
    total_rows = len(dataframe)
    with pq.ParquetWriter(output_path, table.schema, compression="snappy") as writer:
        if total_rows == 0:
            writer.write_table(table)
            if progress_callback is not None:
                progress_callback(0, 0)
        else:
            for start in range(0, total_rows, chunk_size):
                end = min(start + chunk_size, total_rows)
                writer.write_table(table.slice(start, end - start))
                if progress_callback is not None:
                    progress_callback(end, total_rows)


def validate_export_filename_prefix(filename_prefix: str) -> str:
    """Return a normalized filename prefix or raise for invalid input."""

    normalized_prefix = filename_prefix.strip()
    if not normalized_prefix:
        raise ValueError("Enter a filename prefix.")
    if INVALID_FILENAME_PREFIX_PATTERN.search(normalized_prefix):
        raise ValueError('The filename prefix cannot contain < > : " / \\ | ? * or control characters.')
    if normalized_prefix.endswith((".", " ")):
        raise ValueError("The filename prefix cannot end with a dot or space.")
    return normalized_prefix


def build_export_filenames(
    file_paths: Sequence[str],
    filename_prefix: str,
    file_format: str = "csv",
) -> dict[str, str]:
    """Build unique dataset filenames from a custom prefix and source names."""

    if file_format not in {"csv", "parquet"}:
        raise ValueError("Export format must be csv or parquet.")
    normalized_prefix = validate_export_filename_prefix(filename_prefix)
    stem_counts: dict[str, int] = {}
    filenames: dict[str, str] = {}
    for file_path in file_paths:
        source_stem = os.path.splitext(os.path.basename(file_path))[0] or "dataset"
        stem_counts[source_stem] = stem_counts.get(source_stem, 0) + 1
        duplicate_suffix = f"_{stem_counts[source_stem]}" if stem_counts[source_stem] > 1 else ""
        filenames[file_path] = f"{normalized_prefix}_{source_stem}{duplicate_suffix}.{file_format}"
    return filenames


def merge_selected_dataframes(
    selected_paths: Sequence[str],
    data_frames: DataFrameMap,
) -> pd.DataFrame:
    """Merge selected dataframes into a single dataframe."""

    dfs = [data_frames[path] for path in selected_paths]
    return pd.concat(dfs, ignore_index=True, sort=False)


def analyze_selected_dataframes(
    selected_paths: Sequence[str],
    data_frames: DataFrameMap,
) -> str:
    """Build a text analysis summary for the selected files."""

    merged = merge_selected_dataframes(selected_paths, data_frames)
    summary = summarize_dataframe(merged, include_details=False)
    file_summary = ", ".join(f"{os.path.basename(path)}:{len(data_frames[path])}" for path in selected_paths)
    return "\n".join([f"Files {len(selected_paths)} | {file_summary}", format_data_summary_overview(summary)])


def export_clean_dataframes(
    data_frames: DataFrameMap,
    output_dir: str,
    sep: str = ";",
    *,
    filename_prefix: str = "clean",
    file_format: str = "csv",
    column_roles_by_path: Mapping[str, Mapping[str, str]] | None = None,
) -> int:
    """Export `dropna()` versions of the supplied dataframes with custom names."""

    filenames = build_export_filenames(list(data_frames), filename_prefix, file_format)
    for file_path, df in data_frames.items():
        clean_df = df.dropna()
        output_file = os.path.join(output_dir, filenames[file_path])
        write_dataframe_with_progress(
            clean_df,
            output_file,
            sep=sep,
            column_roles=(column_roles_by_path or {}).get(file_path),
        )
    return len(data_frames)


def write_dataframe_csv_with_progress(
    dataframe: pd.DataFrame,
    output_path: str,
    sep: str = ";",
    chunk_size: int = 100_000,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Write dataframe to CSV in chunks and report row-level progress."""

    total_rows = int(len(dataframe))
    if total_rows == 0:
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            dataframe.to_csv(fh, sep=sep, index=False)
        if progress_callback is not None:
            progress_callback(0, 0)
        return

    # Without a progress callback there is no need to slice the dataframe into
    # chunks; write it in a single shot through one file handle.
    if progress_callback is None:
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            dataframe.to_csv(fh, sep=sep, index=False)
        return

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        for start in range(0, total_rows, chunk_size):
            end = min(start + chunk_size, total_rows)
            dataframe.iloc[start:end].to_csv(
                fh,
                sep=sep,
                index=False,
                header=start == 0,
            )
            progress_callback(end, total_rows)
