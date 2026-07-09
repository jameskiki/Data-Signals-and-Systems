"""Multi-dataframe analysis and export helpers."""

import os
from collections.abc import Sequence
from collections.abc import Callable

import pandas as pd

from .models import DataFrameMap
from .summary import summarize_dataframe
from Source.shared.display_format import format_data_summary_overview


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
) -> int:
    """Export `dropna()` versions of all loaded dataframes to the target directory."""

    for file_path, df in data_frames.items():
        clean_df = df.dropna()
        output_file = os.path.join(output_dir, f"clean_{os.path.basename(file_path)}")
        clean_df.to_csv(output_file, sep=sep, index=False)
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
