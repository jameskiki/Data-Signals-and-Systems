"""Tests for shared.display_format — numeric and display formatting helpers."""

import math

import numpy as np
import pandas as pd
import pytest

from shared.display_format import (
    format_display_number,
    format_display_percent,
    format_display_value,
)


# ── format_display_number ─────────────────────────────────────────────────────


class TestFormatDisplayNumber:
    def test_integer_value(self):
        assert format_display_number(3.0) == "3"

    def test_rounds_to_three_decimals(self):
        assert format_display_number(1.23456) == "1.235"

    def test_strips_trailing_zeros(self):
        assert format_display_number(1.500) == "1.5"

    def test_strips_trailing_decimal_point(self):
        assert format_display_number(2.0000) == "2"

    def test_nan_returns_nan_string(self):
        assert format_display_number(float("nan")) == "nan"

    def test_inf_returns_inf_string(self):
        assert format_display_number(float("inf")) == "inf"

    def test_negative_inf(self):
        assert format_display_number(float("-inf")) == "-inf"

    def test_zero(self):
        assert format_display_number(0.0) == "0"

    def test_negative_value(self):
        result = format_display_number(-1.5)
        assert result == "-1.5"

    def test_custom_decimals(self):
        assert format_display_number(1.23456, decimals=2) == "1.23"

    def test_very_small_value(self):
        result = format_display_number(0.001)
        assert result == "0.001"


# ── format_display_percent ────────────────────────────────────────────────────


class TestFormatDisplayPercent:
    def test_half_is_fifty_percent(self):
        assert format_display_percent(0.5) == "50%"

    def test_full_is_hundred_percent(self):
        assert format_display_percent(1.0) == "100%"

    def test_zero_is_zero_percent(self):
        assert format_display_percent(0.0) == "0%"

    def test_fractional_percent(self):
        result = format_display_percent(0.1234)
        assert result == "12.34%"

    def test_custom_decimals(self):
        result = format_display_percent(0.12345, decimals=1)
        assert result == "12.3%"


# ── format_display_value ──────────────────────────────────────────────────────


class TestFormatDisplayValue:
    def test_none_returns_empty_string(self):
        assert format_display_value(None) == ""

    def test_nan_returns_empty_string(self):
        assert format_display_value(float("nan")) == ""
        assert format_display_value(np.nan) == ""

    def test_pd_nat_returns_empty_string(self):
        assert format_display_value(pd.NaT) == ""

    def test_timestamp_returns_iso_format(self):
        ts = pd.Timestamp("2024-03-15 12:30:00")
        result = format_display_value(ts)
        assert "2024-03-15" in result
        assert "12:30:00" in result

    def test_integer_returns_plain_int_string(self):
        assert format_display_value(42) == "42"
        assert format_display_value(np.int64(7)) == "7"

    def test_float_returns_formatted_string(self):
        result = format_display_value(3.14159)
        assert result == "3.142"

    def test_numpy_float_formatted(self):
        result = format_display_value(np.float64(1.5))
        assert result == "1.5"

    def test_string_returned_as_is(self):
        assert format_display_value("hello") == "hello"

    def test_bool_not_treated_as_int(self):
        # bool is a subclass of int, but should be formatted as string
        assert format_display_value(True) == "True"
        assert format_display_value(False) == "False"

    def test_numpy_bool_not_treated_as_float(self):
        assert format_display_value(np.bool_(True)) == "True"
