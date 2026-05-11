"""Tests for datapreparation_app.data_parser performance-sensitive behavior."""

import pandas as pd

from datapreparation_app.data_parser import DataParser


class TestParseDatetimeSeries:
    def test_numeric_series_skips_datetime_guessing(self, monkeypatch):
        series = pd.Series([0.0, 0.1, 0.2], name="time_s")

        def fail_to_datetime(*args, **kwargs):
            raise AssertionError("pd.to_datetime should not be used for numeric time columns")

        monkeypatch.setattr(pd, "to_datetime", fail_to_datetime)

        result = DataParser.parse_datetime_series(series)

        assert result is series
