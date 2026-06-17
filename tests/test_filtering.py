"""Tests for data_ops.filtering – simple column filtering and row subsetting."""

import numpy as np
import pandas as pd
import pytest

from Source.data_ops.filtering import apply_simple_filter, resolve_filtered_column_name


# ── resolve_filtered_column_name ─────────────────────────────────────


class TestResolveFilteredColumnName:
    def test_user_name_wins(self):
        assert resolve_filtered_column_name("pressure", "my_col") == "my_col"

    def test_default_suffix(self):
        assert resolve_filtered_column_name("pressure", "") == "pressure_filt"

    def test_already_filt_suffix(self):
        assert resolve_filtered_column_name("pressure_filt", "") == "pressure_filt"

    def test_whitespace_only_uses_default(self):
        assert resolve_filtered_column_name("temp", "   ") == "temp_filt"


# ── apply_simple_filter (numeric) ────────────────────────────────────


@pytest.fixture
def numeric_df():
    return pd.DataFrame({"val": [1.0, 5.0, 10.0, 15.0, 20.0, np.nan]})


class TestSimpleFilterNumeric:
    def test_min_only(self, numeric_df):
        result = apply_simple_filter(numeric_df, "val", "filtered", minimum_value="10")
        kept = result["filtered"].dropna()
        assert (kept >= 10).all()
        assert len(kept) == 3  # 10, 15, 20

    def test_max_only(self, numeric_df):
        result = apply_simple_filter(numeric_df, "val", "filtered", maximum_value="10")
        kept = result["filtered"].dropna()
        assert (kept <= 10).all()
        assert len(kept) == 3  # 1, 5, 10

    def test_min_and_max(self, numeric_df):
        result = apply_simple_filter(numeric_df, "val", "filtered", minimum_value="5", maximum_value="15")
        kept = result["filtered"].dropna()
        assert len(kept) == 3  # 5, 10, 15
        assert kept.min() >= 5
        assert kept.max() <= 15

    def test_keep_missing_true(self, numeric_df):
        result = apply_simple_filter(
            numeric_df, "val", "filtered", minimum_value="10", keep_missing=True,
        )
        # NaN row should be kept as NaN (not filtered out)
        # 10, 15, 20 pass filter; original NaN also passes
        kept = result["filtered"]
        non_nan_kept = kept.dropna()
        assert len(non_nan_kept) >= 3

    def test_no_bounds_raises(self, numeric_df):
        with pytest.raises(ValueError, match="minimum or maximum"):
            apply_simple_filter(numeric_df, "val", "filtered")

    def test_unknown_column_raises(self, numeric_df):
        with pytest.raises(KeyError):
            apply_simple_filter(numeric_df, "nonexistent", "out", minimum_value="0")

    def test_preserves_original_column(self, numeric_df):
        result = apply_simple_filter(numeric_df, "val", "filtered", minimum_value="10")
        # Original column should still be intact
        assert result["val"].equals(numeric_df["val"])

    def test_default_column_name(self, numeric_df):
        result = apply_simple_filter(numeric_df, "val", "", minimum_value="10")
        assert "val_filt" in result.columns


# ── apply_simple_filter (text) ───────────────────────────────────────


@pytest.fixture
def text_df():
    return pd.DataFrame({"label": ["alpha", "bravo", "charlie", "delta", "echo"]})


class TestSimpleFilterText:
    def test_min_text_range(self, text_df):
        result = apply_simple_filter(text_df, "label", "filtered", minimum_value="charlie")
        kept = result["filtered"].dropna()
        assert "alpha" not in kept.values
        assert "charlie" in kept.values

    def test_max_text_range(self, text_df):
        result = apply_simple_filter(text_df, "label", "filtered", maximum_value="bravo")
        kept = result["filtered"].dropna()
        assert "charlie" not in kept.values
        assert "alpha" in kept.values


# ── apply_simple_filter (datetime) ───────────────────────────────────


@pytest.fixture
def datetime_df():
    dates = pd.to_datetime(["2024-01-01", "2024-06-15", "2025-01-01", "2025-06-15"])
    return pd.DataFrame({"ts": dates, "val": [1, 2, 3, 4]})


class TestSimpleFilterDatetime:
    def test_min_date(self, datetime_df):
        result = apply_simple_filter(datetime_df, "ts", "filtered", minimum_value="2025-01-01")
        kept = result["filtered"].dropna()
        assert len(kept) == 2

    def test_max_date(self, datetime_df):
        result = apply_simple_filter(datetime_df, "ts", "filtered", maximum_value="2024-06-15")
        kept = result["filtered"].dropna()
        assert len(kept) == 2
