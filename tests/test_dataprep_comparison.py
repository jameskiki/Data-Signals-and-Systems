"""Tests for lightweight session-dataset comparison helpers."""

import pandas as pd

from Source.datapreparation_app.comparison import (
    build_comparison_summary_frame,
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
