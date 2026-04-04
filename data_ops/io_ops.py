"""Multi-dataframe analysis and export helpers."""

import os
from collections.abc import Sequence

import pandas as pd

from .models import AnalysisResult, DataFrameMap
from .summary import summarize_dataframe


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
) -> AnalysisResult:
    """Build a text analysis summary and merged dataframe for the selected files."""

    merged = merge_selected_dataframes(selected_paths, data_frames)
    summary = summarize_dataframe(merged)
    file_summary = ", ".join(f"{os.path.basename(path)}:{len(data_frames[path])}" for path in selected_paths)
    info_lines = [f"Files {len(selected_paths)} | {file_summary}", summary.overview_text]
    return AnalysisResult(report_text="\n".join(info_lines), merged_frame=merged)


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
