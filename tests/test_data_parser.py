"""Tests for datapreparation_app.data_parser performance-sensitive behavior."""

import pandas as pd
import pytest

from Source.datapreparation_app.data_parser import DataParser, PARSER_WARNINGS_ATTR


class TestParseDatetimeSeries:
    def test_misleading_initial_sample_preserves_values(self):
        series = pd.Series(["2026-01-01"] * 200 + ["invalid"] * 800, name="time")
        diagnostics = []
        result = DataParser.parse_datetime_series(series, diagnostics.append)
        assert result is series
        assert "800 of 1000" in diagnostics[0]
        assert "original values retained" in diagnostics[0]

    @pytest.mark.parametrize("valid_count,accepted", [(80, True), (79, False)])
    def test_full_column_threshold_and_missing_values(self, valid_count, accepted):
        series = pd.Series(["2026-01-01"] * valid_count + ["bad"] * (100 - valid_count) + [None, ""], name="time")
        diagnostics = []
        result = DataParser.parse_datetime_series(series, diagnostics.append)
        assert pd.api.types.is_datetime64_any_dtype(result) == accepted
        assert f"{100 - valid_count} of 100" in diagnostics[0]
        if accepted:
            assert result.isna().sum() == 102 - valid_count
        else:
            assert result is series

    def test_mixed_formats_do_not_silently_discard_values(self):
        series = pd.Series(["2026-01-01"] * 200 + ["02.01.2026"] * 800, name="time")
        with pytest.warns(RuntimeWarning, match="original values retained"):
            result = DataParser.parse_datetime_series(series)
        assert result is series

    def test_numeric_series_skips_datetime_guessing(self, monkeypatch):
        series = pd.Series([0.0, 0.1, 0.2], name="time_s")

        def fail_to_datetime(*args, **kwargs):
            raise AssertionError("pd.to_datetime should not be used for numeric time columns")

        monkeypatch.setattr(pd, "to_datetime", fail_to_datetime)

        result = DataParser.parse_datetime_series(series)

        assert result is series

    def test_string_datetime_series_is_parsed(self):
        series = pd.Series(["2026-01-01 10:00:00", "2026-01-01 10:00:01", "2026-01-01 10:00:02"], name="time")

        result = DataParser.parse_datetime_series(series)

        assert pd.api.types.is_datetime64_any_dtype(result)
        assert result.notna().all()

    def test_sparse_datetime_series_stays_original_when_below_ratio(self):
        series = pd.Series(["not-a-time", "also-bad", "2026-01-01", "", None], name="time")

        with pytest.warns(RuntimeWarning, match="original values retained"):
            result = DataParser.parse_datetime_series(series)

        assert result is series


class TestDetectDecimalMarker:
    def test_detects_decimal_comma(self, tmp_path):
        file_path = tmp_path / "comma.csv"
        file_path.write_text("a;b\n1,5;2,5\n3,5;4,5\n", encoding="utf-8")

        marker = DataParser.detect_decimal_marker(str(file_path), sep=";", skiprows=0)

        assert marker == ","


class TestLoadFile:
    def test_load_diagnostics_are_retained_for_ui_and_history(self, tmp_path):
        path = tmp_path / "mixed.csv"
        path.write_text("time;value\n" + "2026-01-01;1\n" * 200 + "invalid;2\n" * 800, encoding="utf-8")
        frame, _, _ = DataParser.load_file(str(path))
        assert frame["time"].notna().all()
        assert not pd.api.types.is_datetime64_any_dtype(frame["time"])
        assert "800 of 1000" in frame.attrs[PARSER_WARNINGS_ATTR][0]
    def test_load_file_handles_sep_header_and_drops_empty_trailing_column(self, tmp_path):
        file_path = tmp_path / "sample.csv"
        file_path.write_text(
            "sep=;\n"
            "\n"
            "time;value;\n"
            "2026-01-01 00:00:00;1,5;\n"
            "2026-01-01 00:00:01;2,5;\n",
            encoding="utf-8",
        )

        dataframe, separator, decimal_marker = DataParser.load_file(str(file_path))

        assert separator == ";"
        assert decimal_marker == ","
        assert list(dataframe.columns) == ["time", "value"]
        assert pd.api.types.is_datetime64_any_dtype(dataframe["time"])
        assert dataframe["value"].tolist() == [1.5, 2.5]
