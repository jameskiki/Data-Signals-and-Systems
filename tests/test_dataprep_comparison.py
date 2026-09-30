"""Tests for lightweight session-dataset comparison helpers."""

import pandas as pd
import matplotlib.pyplot as plt

from Source.datapreparation_app.comparison import (
    add_overlay_deviation_highlights,
    build_difference_figure,
    build_comparison_summary_frame,
    build_dataset_detail_text,
    build_display_dataset_labels,
    build_numeric_column_labels,
    calculate_subplot_grid,
    filter_visible_dataset_paths,
    get_shared_x_overlap_bounds,
    get_common_columns,
    get_missing_column_combinations,
    get_numeric_column_availability,
    resolve_default_x_column,
    trim_dataframes_to_shared_x_overlap,
)
from Source.datapreparation_app.datasets import DatasetContext
from Source.shared.plot_options import PlotStyle
from Source.shared.demo_catalog import (
    COMPARISON_BASELINE_DEMO,
    COMPARISON_DRIFT_SPIKE_DEMO,
    COMPARISON_GAIN_OFFSET_DEMO,
    create_demo_dataset,
)


def test_get_common_columns_preserves_first_dataset_order() -> None:
    data_frames = {
        "a": pd.DataFrame({"time_s": [0.0], "sensor_a": [1.0], "shared": [2.0]}),
        "b": pd.DataFrame({"shared": [3.0], "time_s": [0.0], "sensor_b": [4.0]}),
    }

    assert get_common_columns(["a", "b"], data_frames) == ["time_s", "shared"]


def test_numeric_column_availability_includes_partial_channels() -> None:
    data_frames = {
        "a": pd.DataFrame({"time_s": [0.0], "shared": [1.0], "only_a": [2.0], "label": ["a"]}),
        "b": pd.DataFrame({"time_s": [0.0], "shared": [3.0], "only_b": [4.0]}),
    }

    availability = get_numeric_column_availability(["a", "b"], data_frames)
    labels = build_numeric_column_labels(availability, dataset_count=2)

    assert availability == {"time_s": 2, "shared": 2, "only_a": 1, "only_b": 1}
    assert labels["shared"] == "shared"
    assert labels["only_a"] == "only_a (1/2 datasets)"
    assert get_missing_column_combinations(["a", "b"], data_frames, ["only_a", "only_b"]) == [
        ("a", "only_b"),
        ("b", "only_a"),
    ]


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

    assert list(summary_frame.columns) == ["dataset", "rows", "cols", "missing", "mean", "std", "min", "max"]
    assert summary_frame.loc["a", "rows"] == 2
    assert summary_frame.loc["a", "mean"] == 2.0
    assert summary_frame.loc["b", "max"] == 6.0


def test_build_comparison_summary_frame_handles_empty_selection() -> None:
    summary_frame = build_comparison_summary_frame([], {}, stats_column=None)

    assert list(summary_frame.columns) == ["dataset", "rows", "cols", "missing", "mean", "std", "min", "max"]
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


def test_filter_visible_dataset_paths_preserves_order_and_defaults_new_paths_visible() -> None:
    visible_paths = filter_visible_dataset_paths(
        ["baseline", "gain_offset", "drift_spike", "new_run"],
        {
            "baseline": True,
            "gain_offset": False,
            "drift_spike": True,
        },
    )

    assert visible_paths == ["baseline", "drift_spike", "new_run"]


def test_calculate_subplot_grid_balances_multiple_channels() -> None:
    assert calculate_subplot_grid(1) == (1, 1)
    assert calculate_subplot_grid(3) == (2, 2)
    assert calculate_subplot_grid(6) == (2, 3)


def test_build_difference_figure_arranges_channels_in_grid() -> None:
    data_frames = {
        "baseline": pd.DataFrame(
            {"time_s": [0.0, 1.0], "a": [1.0, 2.0], "b": [2.0, 3.0], "c": [3.0, 4.0]}
        ),
        "candidate": pd.DataFrame(
            {"time_s": [0.0, 1.0], "a": [1.5, 2.5], "b": [3.0, 4.0], "c": [4.0, 5.0]}
        ),
    }

    figure = build_difference_figure(
        ["baseline", "candidate"],
        data_frames,
        "baseline",
        ["a", "b", "c"],
        x_column="time_s",
        channels_in_grid=True,
    )

    try:
        first_axis, second_axis, third_axis, unused_axis = figure.axes
        assert first_axis.get_position().x0 < second_axis.get_position().x0
        assert first_axis.get_position().y0 == second_axis.get_position().y0
        assert third_axis.get_position().y0 < first_axis.get_position().y0
        assert not unused_axis.get_visible()
        assert first_axis.get_xlabel() == "time_s"
        assert second_axis.get_xlabel() == "time_s"
        assert third_axis.get_xlabel() == "time_s"
    finally:
        plt.close(figure)


def test_trim_dataframes_to_shared_x_overlap_trims_every_dataset() -> None:
    data_frames = {
        "baseline": pd.DataFrame({"time_s": [0.0, 1.0, 2.0, 3.0], "signal": [0.0, 1.0, 2.0, 3.0]}),
        "candidate": pd.DataFrame({"time_s": [1.0, 2.0], "signal": [6.0, 7.0]}),
    }

    assert get_shared_x_overlap_bounds(["baseline", "candidate"], data_frames, "time_s") == (1.0, 2.0)
    trimmed = trim_dataframes_to_shared_x_overlap(["baseline", "candidate"], data_frames, "time_s")

    assert trimmed["baseline"]["time_s"].tolist() == [1.0, 2.0]
    assert trimmed["candidate"]["time_s"].tolist() == [1.0, 2.0]


def test_build_difference_figure_aligns_values_on_selected_x_axis() -> None:
    data_frames = {
        "baseline": pd.DataFrame({"time_s": [0.0, 1.0, 2.0, 3.0], "signal": [0.0, 1.0, 2.0, 3.0]}),
        "candidate": pd.DataFrame({"time_s": [1.0, 2.0], "signal": [6.0, 7.0]}),
    }

    figure = build_difference_figure(
        ["baseline", "candidate"],
        data_frames,
        "baseline",
        ["signal"],
        x_column="time_s",
        trim_overlap=True,
        highlight_deviations=True,
    )

    try:
        difference_line = figure.axes[0].lines[0]
        baseline_reference_line = figure.axes[0].lines[1]
        assert difference_line.get_xdata().tolist() == [1.0, 2.0]
        assert difference_line.get_ydata().tolist() == [5.0, 5.0]
        assert baseline_reference_line.get_linestyle() == "--"
        assert baseline_reference_line.get_label() == "Baseline: baseline (zero)"
        assert {collection.get_label() for collection in figure.axes[0].collections} == {
            "Above baseline",
            "Below baseline",
        }
    finally:
        plt.close(figure)


def test_build_difference_figure_marks_channel_missing_from_baseline() -> None:
    data_frames = {
        "baseline": pd.DataFrame({"time_s": [0.0, 1.0], "shared": [1.0, 2.0]}),
        "candidate": pd.DataFrame({"time_s": [0.0, 1.0], "candidate_only": [3.0, 4.0]}),
    }

    figure = build_difference_figure(
        ["baseline", "candidate"],
        data_frames,
        "baseline",
        ["candidate_only"],
        x_column="time_s",
    )

    try:
        axis = figure.axes[0]
        assert not axis.axison
        assert axis.texts[0].get_text() == "Unavailable in baseline"
    finally:
        plt.close(figure)


def test_build_difference_figure_can_hide_all_legends() -> None:
    data_frames = {
        "baseline": pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.0, 2.0]}),
        "candidate": pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.5, 2.5]}),
    }

    figure = build_difference_figure(
        ["baseline", "candidate"],
        data_frames,
        "baseline",
        ["signal"],
        x_column="time_s",
        highlight_deviations=True,
        style=PlotStyle(show_legend=False),
    )

    try:
        assert figure.axes[0].get_legend() is None
    finally:
        plt.close(figure)


def test_add_overlay_deviation_highlights_fills_above_and_below_baseline() -> None:
    data_frames = {
        "baseline": pd.DataFrame({"time_s": [0.0, 1.0, 2.0], "signal": [1.0, 1.0, 1.0]}),
        "candidate": pd.DataFrame({"time_s": [0.0, 1.0, 2.0], "signal": [0.5, 1.5, 0.5]}),
    }
    figure, axis = plt.subplots()

    try:
        add_overlay_deviation_highlights(
            figure,
            ["baseline", "candidate"],
            data_frames,
            "baseline",
            ["signal"],
            x_column="time_s",
            channels_in_grid=False,
        )

        assert {collection.get_label() for collection in axis.collections} == {
            "Above baseline",
            "Below baseline",
        }
    finally:
        plt.close(figure)


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


def test_comparison_demo_set_produces_distinct_baseline_deviations() -> None:
    specs = (
        COMPARISON_BASELINE_DEMO,
        COMPARISON_GAIN_OFFSET_DEMO,
        COMPARISON_DRIFT_SPIKE_DEMO,
    )
    data_frames = {
        spec.key: create_demo_dataset(spec.key)[1]
        for spec in specs
    }

    summary_frame = build_comparison_summary_frame(
        [spec.key for spec in specs],
        data_frames,
        stats_column="measurement",
        baseline_path=COMPARISON_BASELINE_DEMO.key,
        include_richer_metrics=True,
    )

    assert summary_frame.loc[COMPARISON_BASELINE_DEMO.key, "baseline"]
    assert pd.isna(summary_frame.loc[COMPARISON_BASELINE_DEMO.key, "deviation_rms"])
    assert summary_frame.loc[COMPARISON_GAIN_OFFSET_DEMO.key, "deviation_rms"] > 0.4
    assert summary_frame.loc[COMPARISON_DRIFT_SPIKE_DEMO.key, "deviation_rms"] > 0.5
    assert summary_frame.loc[COMPARISON_DRIFT_SPIKE_DEMO.key, "rows"] == 850
