"""Tests for data_ops.summary – statistics, correlation, and summarize_dataframe."""

import numpy as np
import pandas as pd
import pytest

from data_ops.summary import build_correlation_frame, build_statistics_frame, summarize_dataframe


# ── summarize_dataframe ──────────────────────────────────────────────


class TestSummarizeDataframe:
    def test_overview_contains_shape(self, two_column_df):
        result = summarize_dataframe(two_column_df)
        assert f"{len(two_column_df)} rows" in result.overview_text

    def test_row_and_column_counts(self, two_column_df):
        result = summarize_dataframe(two_column_df)
        assert result.row_count == len(two_column_df)
        assert result.column_count == len(two_column_df.columns)

    def test_numeric_column_count(self, two_column_df):
        result = summarize_dataframe(two_column_df)
        assert result.numeric_column_count == 3  # time_s, sensor_a, sensor_b

    def test_statistics_frame_populated(self, two_column_df):
        result = summarize_dataframe(two_column_df)
        assert not result.statistics_frame.empty

    def test_correlation_frame_populated(self, two_column_df):
        result = summarize_dataframe(two_column_df)
        assert not result.correlation_frame.empty

    def test_missing_count_zero_for_clean_data(self, two_column_df):
        result = summarize_dataframe(two_column_df)
        assert result.total_missing_count == 0

    def test_missing_count_nonzero(self):
        df = pd.DataFrame({"x": [1, np.nan, 3], "y": [np.nan, 2, 3]})
        result = summarize_dataframe(df)
        assert result.total_missing_count == 2

    def test_datetime_columns_detected(self):
        df = pd.DataFrame({
            "ts": pd.to_datetime(["2024-01-01", "2024-06-01"]),
            "val": [1, 2],
        })
        result = summarize_dataframe(df)
        assert result.datetime_column_count == 1
        assert result.time_range_text != ""


class TestBuildStatisticsFrame:
    def test_expected_columns(self, two_column_df):
        result = build_statistics_frame(two_column_df)
        for col in ("count", "missing", "min", "max", "mean", "std", "rms", "peak_to_peak"):
            assert col in result.columns

    def test_count_matches_rows(self, two_column_df):
        result = build_statistics_frame(two_column_df)
        counts = result["count"].to_numpy()
        assert (counts == len(two_column_df)).all()

    def test_rms_positive(self, noisy_sine):
        result = build_statistics_frame(noisy_sine)
        rms_values = result["rms"].dropna()
        assert (rms_values > 0).all()

    def test_empty_dataframe(self):
        df = pd.DataFrame({"text": ["a", "b", "c"]})
        result = build_statistics_frame(df)
        assert result.empty


class TestBuildCorrelationFrame:
    def test_diagonal_is_one(self, two_column_df):
        result = build_correlation_frame(two_column_df)
        for col in result.columns:
            if col in result.index:
                assert abs(result.loc[col, col] - 1.0) < 1e-10

    def test_symmetric(self, two_column_df):
        result = build_correlation_frame(two_column_df)
        numeric_cols = [c for c in result.columns if c in result.index]
        for i, c1 in enumerate(numeric_cols):
            for c2 in numeric_cols[i + 1:]:
                assert abs(result.loc[c1, c2] - result.loc[c2, c1]) < 1e-10

    def test_correlated_signals(self, two_column_df):
        result = build_correlation_frame(two_column_df)
        # sensor_b = 0.8 * sensor_a + noise → should be highly correlated
        assert result.loc["sensor_a", "sensor_b"] > 0.8
