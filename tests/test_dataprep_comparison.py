"""Tests for lightweight session-dataset comparison helpers."""

import pandas as pd

from Source.datapreparation_app.comparison import (
    build_comparison_summary_frame,
    build_dataset_detail_text,
    build_display_dataset_labels,
    get_common_columns,
    resolve_default_x_column,
)
from Source.datapreparation_app.datasets import DatasetContext


def test_get_common_columns_preserves_first_dataset_order() -> None:
    data_frames = {
        "a": pd.DataFrame({"time_s": [0.0], "sensor_a": [1.0], "shared": [2.0]}),
        "b": pd.DataFrame({"shared": [3.0], "time_s": [0.0], "sensor_b": [4.0]}),
    }

    assert get_common_columns(["a", "b"], data_frames) == ["time_s", "shared"]


def test_resolve_default_x_column_prefers_shared_time_role() -> None:
    data_frames = {
        "a": pd.DataFrame({"time_s": [0.0], "sensor": [1.0]}),
        "b": pd.DataFrame({"time_s": [0.0], "sensor": [2.0]}),
    }
    dataset_contexts = {
        "a": DatasetContext(column_roles={"time_s": "time", "sensor": "signal"}),
        "b": DatasetContext(column_roles={"time_s": "time", "sensor": "signal"}),
    }

    assert resolve_default_x_column(["a", "b"], data_frames, dataset_contexts) == "time_s"


def test_build_comparison_summary_frame_includes_selected_column_statistics() -> None:
    data_frames = {
        "a": pd.DataFrame({"time_s": [0.0, 1.0], "sensor": [1.0, 3.0]}),
        "b": pd.DataFrame({"time_s": [0.0, 1.0], "sensor": [2.0, 6.0]}),
    }

    summary_frame = build_comparison_summary_frame(["a", "b"], data_frames, stats_column="sensor")

    assert list(summary_frame.columns) == ["rows", "cols", "missing", "mean", "std", "min", "max"]
    assert summary_frame.loc["a", "rows"] == 2
    assert summary_frame.loc["a", "mean"] == 2.0
    assert summary_frame.loc["b", "max"] == 6.0


def test_build_comparison_summary_frame_handles_empty_selection() -> None:
    summary_frame = build_comparison_summary_frame([], {}, stats_column=None)

    assert list(summary_frame.columns) == ["rows", "cols", "missing", "mean", "std", "min", "max"]
    assert summary_frame.empty


def test_build_display_dataset_labels_deduplicates_matching_basenames() -> None:
    labels = build_display_dataset_labels(
        [
            "/tmp/run_a/shared.csv",
            "/tmp/run_b/shared.csv",
            "/tmp/run_c/unique.csv",
        ]
    )

    assert labels["/tmp/run_a/shared.csv"] == "shared.csv (1)"
    assert labels["/tmp/run_b/shared.csv"] == "shared.csv (2)"
    assert labels["/tmp/run_c/unique.csv"] == "unique.csv"


def test_build_dataset_detail_text_includes_lineage_and_notes() -> None:
    data_frames = {
        "/tmp/run_a/shared.csv": pd.DataFrame({"time_s": [0.0, 1.0], "sensor": [1.0, 2.0]}),
    }
    dataset_contexts = {
        "/tmp/run_a/shared.csv": DatasetContext(
            source_paths=["/tmp/raw/input.csv"],
            description="Published from analysis workspace",
            column_roles={"time_s": "time", "sensor": "signal"},
        )
    }

    detail_text = build_dataset_detail_text("/tmp/run_a/shared.csv", data_frames, dataset_contexts)

    assert "Dataset: shared.csv" in detail_text
    assert "Rows: 2" in detail_text
    assert "Lineage: input.csv" in detail_text
    assert "Notes: Published from analysis workspace" in detail_text
