"""Tests for data_ops.frame_ops – structural dataframe operations."""

import numpy as np
import pandas as pd
import pytest

from Source.data_ops.frame_ops import (
    keep_dataframe_index_ranges,
    normalize_index_range,
    resample_to_uniform,
    select_dataframe_columns,
    split_dataframe_by_index_ranges,
)


# ── Column operations ────────────────────────────────────────────────


class TestSelectColumns:
    def test_keeps_only_requested(self, two_column_df):
        result = select_dataframe_columns(two_column_df, ["sensor_a"])
        assert list(result.columns) == ["sensor_a"]

    def test_preserves_order(self, two_column_df):
        result = select_dataframe_columns(two_column_df, ["sensor_b", "time_s"])
        assert list(result.columns) == ["sensor_b", "time_s"]

    def test_unknown_column_raises(self, two_column_df):
        with pytest.raises(KeyError):
            select_dataframe_columns(two_column_df, ["nonexistent"])

    def test_empty_selection_raises(self, two_column_df):
        with pytest.raises(ValueError):
            select_dataframe_columns(two_column_df, [])


class TestNormalizeIndexRange:
    def test_basic(self):
        start, end = normalize_index_range(100, 10, 50)
        assert start == 10
        assert end == 50

    def test_clamps_end(self):
        start, end = normalize_index_range(100, 10, 200)
        assert end == 100

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            normalize_index_range(100, -1, 50)

    def test_inverted_range_raises(self):
        with pytest.raises(ValueError, match="end must be greater"):
            normalize_index_range(100, 50, 10)


# ── Split ────────────────────────────────────────────────────────────


class TestSplitByIndexRanges:
    def test_produces_correct_count(self, linear_ramp):
        ranges = [(0, 100), (200, 400), (500, 700)]
        result = split_dataframe_by_index_ranges(linear_ramp, ranges)
        assert len(result) == 3

    def test_empty_raises(self, linear_ramp):
        with pytest.raises(ValueError):
            split_dataframe_by_index_ranges(linear_ramp, [])


class TestKeepIndexRanges:
    def test_concatenates_requested_ranges(self, linear_ramp):
        result = keep_dataframe_index_ranges(linear_ramp, [(0, 3), (5, 8)])

        assert len(result) == 6
        assert result.index.tolist() == list(range(6))
        expected_time_values = linear_ramp.iloc[[0, 1, 2, 5, 6, 7]]["time_s"].tolist()
        assert result["time_s"].tolist() == pytest.approx(expected_time_values)

    def test_empty_ranges_raise(self, linear_ramp):
        with pytest.raises(ValueError):
            keep_dataframe_index_ranges(linear_ramp, [])


# ── Resampling ───────────────────────────────────────────────────────


class TestResampleToUniform:
    def test_output_spacing(self):
        t = np.array([0.0, 0.1, 0.25, 0.4, 0.5, 0.7, 1.0])
        df = pd.DataFrame({"time": t, "val": np.sin(t)})
        result = resample_to_uniform(df, "time", target_spacing=0.05)
        dt = np.diff(result["time"].to_numpy())
        assert np.allclose(dt, 0.05, atol=1e-12)

    def test_interpolates_values(self):
        t = np.linspace(0, 1, 100)
        df = pd.DataFrame({"t": t, "y": 2 * t + 3})
        result = resample_to_uniform(df, "t", target_spacing=0.005)
        # Linear signal → interpolation should be exact
        expected = 2 * result["t"].to_numpy() + 3
        assert np.allclose(result["y"].to_numpy(), expected, atol=1e-6)

    def test_increases_sample_count(self):
        t = np.linspace(0, 1, 20)
        df = pd.DataFrame({"t": t, "y": np.sin(t)})
        result = resample_to_uniform(df, "t", target_spacing=0.01)
        assert len(result) > len(df)

    def test_missing_column_raises(self, linear_ramp):
        with pytest.raises(KeyError):
            resample_to_uniform(linear_ramp, "nonexistent", target_spacing=0.1)

    def test_negative_spacing_raises(self, linear_ramp):
        with pytest.raises(ValueError, match="greater than zero"):
            resample_to_uniform(linear_ramp, "time_s", target_spacing=-0.1)
