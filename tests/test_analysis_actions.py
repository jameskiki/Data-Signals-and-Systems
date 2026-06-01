"""Tests for analysis_app.actions — pure FrameUpdate builders."""

import numpy as np
import pandas as pd
import pytest

from analysis_app.actions import (
    FrameUpdate,
    build_derived_signal_update,
    build_reset_update,
    build_signal_filter_update,
    build_simple_filter_update,
    resolve_default_output_names,
)


@pytest.fixture
def simple_df():
    """Small numeric dataframe for filter/signal tests."""
    n = 100
    t = np.linspace(0, 1, n)
    return pd.DataFrame({"time_s": t, "sensor": np.sin(2 * np.pi * 5 * t)})


# ── build_simple_filter_update ────────────────────────────────────────────────


class TestBuildSimpleFilterUpdate:
    def test_returns_frame_update(self, simple_df):
        result = build_simple_filter_update(simple_df, "sensor", "", "-0.5", "0.5", keep_missing=False)
        assert isinstance(result, FrameUpdate)

    def test_filters_rows_outside_range(self, simple_df):
        result = build_simple_filter_update(simple_df, "sensor", "", "-0.5", "0.5", keep_missing=False)
        # Values outside range are set to NaN in the output column (source column is unchanged)
        filtered_col = result.dataframe["sensor_filt"].dropna()
        assert filtered_col.max() <= 0.5
        assert filtered_col.min() >= -0.5

    def test_history_entry_is_string(self, simple_df):
        result = build_simple_filter_update(simple_df, "sensor", "", "-1.0", "1.0", keep_missing=True)
        assert isinstance(result.history_entry, str)
        assert "sensor" in result.history_entry

    def test_named_output_column(self, simple_df):
        result = build_simple_filter_update(simple_df, "sensor", "sensor_filtered", "-1.0", "1.0", keep_missing=True)
        assert "sensor_filtered" in result.dataframe.columns

    def test_dataframe_is_immutable(self, simple_df):
        original_len = len(simple_df)
        build_simple_filter_update(simple_df, "sensor", "", "-0.5", "0.5", keep_missing=False)
        assert len(simple_df) == original_len


# ── build_signal_filter_update ────────────────────────────────────────────────


class TestBuildSignalFilterUpdate:
    def test_moving_average_returns_frame_update(self, simple_df):
        result = build_signal_filter_update(
            simple_df, "sensor", "moving_average", "", window_size=5,
            alpha=0.3, cutoff_hz=1.0, sample_spacing=0.01
        )
        assert isinstance(result, FrameUpdate)

    def test_new_column_added(self, simple_df):
        result = build_signal_filter_update(
            simple_df, "sensor", "moving_average", "smooth", window_size=5,
            alpha=0.3, cutoff_hz=1.0, sample_spacing=0.01
        )
        assert "smooth" in result.dataframe.columns

    def test_history_entry_contains_operation(self, simple_df):
        result = build_signal_filter_update(
            simple_df, "sensor", "median", "", window_size=5,
            alpha=0.3, cutoff_hz=1.0, sample_spacing=0.01
        )
        assert "median" in result.history_entry

    def test_butterworth_lowpass(self, simple_df):
        result = build_signal_filter_update(
            simple_df, "sensor", "butterworth_lowpass", "", window_size=5,
            alpha=0.3, cutoff_hz=10.0, sample_spacing=0.01, filter_order=4
        )
        assert isinstance(result, FrameUpdate)
        assert result.dataframe is not simple_df


# ── build_derived_signal_update ───────────────────────────────────────────────


class TestBuildDerivedSignalUpdate:
    def test_delta_creates_new_column(self, simple_df):
        result = build_derived_signal_update(
            simple_df, "sensor", "delta", "sensor_delta", reference_column=None, window_size=1
        )
        assert "sensor_delta" in result.dataframe.columns

    def test_returns_frame_update(self, simple_df):
        result = build_derived_signal_update(
            simple_df, "sensor", "rolling_mean", "sensor_rm", reference_column=None, window_size=5
        )
        assert isinstance(result, FrameUpdate)

    def test_history_entry_contains_operation_and_columns(self, simple_df):
        result = build_derived_signal_update(
            simple_df, "sensor", "normalized", "sensor_norm", reference_column=None, window_size=1
        )
        assert "normalized" in result.history_entry
        assert "sensor" in result.history_entry
        assert "sensor_norm" in result.history_entry


# ── build_reset_update ────────────────────────────────────────────────────────


class TestBuildResetUpdate:
    def test_returns_frame_update(self, simple_df):
        result = build_reset_update(simple_df)
        assert isinstance(result, FrameUpdate)

    def test_dataframe_is_copy(self, simple_df):
        result = build_reset_update(simple_df)
        assert result.dataframe is not simple_df

    def test_dataframe_contents_match_original(self, simple_df):
        result = build_reset_update(simple_df)
        pd.testing.assert_frame_equal(result.dataframe, simple_df)

    def test_history_entry_describes_reset(self, simple_df):
        result = build_reset_update(simple_df)
        assert "reset" in result.history_entry.lower() or "original" in result.history_entry.lower()


# ── resolve_default_output_names ──────────────────────────────────────────────


class TestResolveDefaultOutputNames:
    def test_no_active_column_returns_inputs_unchanged(self):
        result = resolve_default_output_names("", "my_filter", "my_signal", "my_derived", "delta")
        assert result == ("my_filter", "my_signal", "my_derived")

    def test_empty_names_are_derived_from_active_column(self):
        f, s, d = resolve_default_output_names("sensor", "", "", "", "delta")
        assert "sensor" in f
        assert "sensor" in s
        assert "sensor" in d
        assert "delta" in d

    def test_user_provided_names_preserved(self):
        f, s, d = resolve_default_output_names("sensor", "my_f", "my_s", "my_d", "delta")
        assert f == "my_f"
        assert s == "my_s"
        assert d == "my_d"

    def test_whitespace_only_name_treated_as_empty(self):
        f, s, d = resolve_default_output_names("sensor", "  ", "  ", "  ", "delta")
        assert "sensor" in f
        assert "sensor" in s
