"""Tests for data_ops.io_ops – merge, analyze, and export dataframes."""

import numpy as np
import pandas as pd
import pytest

from Source.data_ops.io_ops import analyze_selected_dataframes, export_clean_dataframes, merge_selected_dataframes


@pytest.fixture
def sample_data_frames():
    """Simulate a DataFrameMap with two fake file paths."""
    return {
        "/data/file_a.csv": pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]}),
        "/data/file_b.csv": pd.DataFrame({"x": [4, 5], "y": [40, 50]}),
    }


@pytest.fixture
def data_frames_with_nan():
    return {
        "/data/dirty.csv": pd.DataFrame({"a": [1, np.nan, 3], "b": [np.nan, 2, 3]}),
    }


# ── merge_selected_dataframes ────────────────────────────────────────


class TestMergeSelectedDataframes:
    def test_merges_all_rows(self, sample_data_frames):
        paths = list(sample_data_frames.keys())
        result = merge_selected_dataframes(paths, sample_data_frames)
        assert len(result) == 5

    def test_single_file(self, sample_data_frames):
        paths = ["/data/file_a.csv"]
        result = merge_selected_dataframes(paths, sample_data_frames)
        assert len(result) == 3

    def test_preserves_columns(self, sample_data_frames):
        paths = list(sample_data_frames.keys())
        result = merge_selected_dataframes(paths, sample_data_frames)
        assert "x" in result.columns and "y" in result.columns

    def test_resets_index(self, sample_data_frames):
        paths = list(sample_data_frames.keys())
        result = merge_selected_dataframes(paths, sample_data_frames)
        assert list(result.index) == list(range(len(result)))


# ── analyze_selected_dataframes ──────────────────────────────────────


class TestAnalyzeSelectedDataframes:
    def test_report_contains_file_count(self, sample_data_frames):
        paths = list(sample_data_frames.keys())
        result = analyze_selected_dataframes(paths, sample_data_frames)
        assert "Files 2" in result

    def test_report_contains_filenames(self, sample_data_frames):
        paths = list(sample_data_frames.keys())
        result = analyze_selected_dataframes(paths, sample_data_frames)
        assert "file_a.csv" in result
        assert "file_b.csv" in result

    def test_returns_string(self, sample_data_frames):
        paths = list(sample_data_frames.keys())
        result = analyze_selected_dataframes(paths, sample_data_frames)
        assert isinstance(result, str)


# ── export_clean_dataframes ──────────────────────────────────────────


class TestExportCleanDataframes:
    def test_creates_output_files(self, data_frames_with_nan, tmp_path):
        count = export_clean_dataframes(data_frames_with_nan, str(tmp_path))
        assert count == 1
        output_file = tmp_path / "clean_dirty.csv"
        assert output_file.exists()

    def test_drops_nan_rows(self, data_frames_with_nan, tmp_path):
        export_clean_dataframes(data_frames_with_nan, str(tmp_path))
        output_file = tmp_path / "clean_dirty.csv"
        exported = pd.read_csv(output_file, sep=";")
        assert exported.notna().all().all()
        assert len(exported) == 1  # only row index 2 has no NaN

    def test_custom_separator(self, sample_data_frames, tmp_path):
        export_clean_dataframes(sample_data_frames, str(tmp_path), sep=",")
        output_file = tmp_path / "clean_file_a.csv"
        content = output_file.read_text()
        assert "," in content

    def test_returns_count(self, sample_data_frames, tmp_path):
        count = export_clean_dataframes(sample_data_frames, str(tmp_path))
        assert count == 2
