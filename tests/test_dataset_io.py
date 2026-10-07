"""CSV compatibility and Parquet dataset round-trip tests."""

from types import SimpleNamespace
from contextlib import contextmanager

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from Source.data_ops.io_ops import (
    DATAFRAME_ROLE_ATTR,
    PARQUET_ROLE_METADATA_KEY,
    build_export_filenames,
    export_clean_dataframes,
    read_dataframe_parquet,
    write_dataframe_with_progress,
)
from Source.datapreparation_app.data_parser import DataParser
from Source.analysis_app.app import AnalysisWorkspace
from Source.analysis_app import app as analysis_app
from Source.shared import dataset_dialogs


@pytest.fixture
def typed_frame():
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=5, freq="ms", tz="UTC"),
        "signal": pd.Series([1.0, np.nan, 3.0, 4.0, 5.0], dtype="float32"),
        "count": pd.Series([1, None, 3, 4, 5], dtype="Int64"),
        "flag": pd.Series([True, False, None, True, False], dtype="boolean"),
        "label": pd.Series(["alpha", "beta", None, "delta", "epsilon"], dtype="string"),
    })


@pytest.mark.parametrize("extension", [".parquet", ".pq", ".PARQUET"])
def test_parquet_round_trip_preserves_values_types_and_roles(tmp_path, typed_frame, extension):
    path = str(tmp_path / ("dataset" + extension))
    roles = {"time": "time", "signal": "signal", "count": "metadata", "removed": "signal"}
    progress = []
    write_dataframe_with_progress(
        typed_frame, path, chunk_size=2, column_roles=roles,
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    restored, separator, decimal = DataParser.load_file(path)

    pd.testing.assert_frame_equal(restored, typed_frame)
    assert restored.attrs[DATAFRAME_ROLE_ATTR] == {key: value for key, value in roles.items() if key != "removed"}
    assert (separator, decimal) == ("", "")
    assert progress == [(2, 5), (4, 5), (5, 5)]
    assert pq.ParquetFile(path).metadata.row_group(0).column(0).compression == "SNAPPY"


def test_parquet_empty_frame_retains_schema_and_reports_progress(tmp_path, typed_frame):
    path = str(tmp_path / "empty.parquet")
    progress = []
    frame = typed_frame.iloc[:0]
    write_dataframe_with_progress(
        frame, path, progress_callback=lambda current, total: progress.append((current, total)),
    )
    pd.testing.assert_frame_equal(read_dataframe_parquet(path), frame)
    assert progress == [(0, 0)]


def test_parquet_does_not_export_dataframe_index(tmp_path):
    path = str(tmp_path / "indexed.parquet")
    frame = pd.DataFrame({"value": [1, 2]}, index=pd.Index([10, 20], name="sample"))
    write_dataframe_with_progress(frame, path)
    pd.testing.assert_frame_equal(read_dataframe_parquet(path), frame.reset_index(drop=True))


def test_external_parquet_skips_text_parser(tmp_path, monkeypatch):
    path = str(tmp_path / "external.parquet")
    frame = pd.DataFrame({"time": ["not a timestamp"], "value": [1.25]})
    frame.to_parquet(path, engine="pyarrow", index=False)
    monkeypatch.setattr(
        DataParser, "parse_datetime_series",
        lambda *_: pytest.fail("Parquet must not run CSV datetime guessing"),
    )
    progress = []
    restored, _, _ = DataParser.load_file(
        path, progress_callback=lambda current, total, label: progress.append((current, total)),
    )
    pd.testing.assert_frame_equal(restored, frame)
    assert DATAFRAME_ROLE_ATTR not in restored.attrs
    assert progress == [(0.0, 100.0), (100.0, 100.0)]


@pytest.mark.parametrize("metadata", [b"not json", b'["signal"]', b'{"signal": 42}'])
def test_invalid_parquet_role_metadata_raises(tmp_path, metadata):
    path = str(tmp_path / "invalid.parquet")
    table = pa.Table.from_pandas(pd.DataFrame({"signal": [1.0]}))
    table = table.replace_schema_metadata({PARQUET_ROLE_METADATA_KEY: metadata})
    pq.write_table(table, path)
    with pytest.raises(ValueError):
        DataParser.load_file(path)


def test_corrupt_parquet_raises_without_csv_fallback(tmp_path):
    path = tmp_path / "corrupt.parquet"
    path.write_text("signal;value\n1;2\n", encoding="utf-8")
    with pytest.raises(pa.ArrowInvalid):
        DataParser.load_file(str(path))


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_invalid_write_chunk_size_raises(tmp_path, chunk_size):
    with pytest.raises(ValueError, match="chunk_size"):
        write_dataframe_with_progress(pd.DataFrame({"x": [1]}), str(tmp_path / "a.parquet"), chunk_size=chunk_size)


def test_csv_writer_preserves_separator_headers_missing_values_and_progress(tmp_path):
    frame = pd.DataFrame({"signal": [1.5, np.nan, 3.5]}, index=[10, 20, 30])
    path = tmp_path / "data.csv"
    progress = []
    write_dataframe_with_progress(
        frame, str(path), chunk_size=2,
        progress_callback=lambda current, total: progress.append((current, total)),
    )
    assert path.read_text().count("signal") == 1
    pd.testing.assert_frame_equal(pd.read_csv(path, sep=";"), frame.reset_index(drop=True))
    assert progress == [(2, 3), (3, 3)]


def test_clean_parquet_export_drops_missing_rows_and_retains_roles(tmp_path):
    frame = pd.DataFrame({"signal": [1.0, np.nan, 3.0]})
    count = export_clean_dataframes(
        {"run.csv": frame}, str(tmp_path), file_format="parquet",
        column_roles_by_path={"run.csv": {"signal": "metadata"}},
    )
    restored = read_dataframe_parquet(str(tmp_path / "clean_run.parquet"))
    assert count == 1
    assert restored["signal"].tolist() == [1.0, 3.0]
    assert restored.attrs[DATAFRAME_ROLE_ATTR] == {"signal": "metadata"}


def test_export_format_validation_and_duplicate_filenames():
    assert build_export_filenames(["a.parquet", "a.csv"], "clean", "parquet") == {
        "a.parquet": "clean_a.parquet", "a.csv": "clean_a_2.parquet",
    }
    with pytest.raises(ValueError, match="format"):
        build_export_filenames(["a.csv"], "clean", "pickle")


@pytest.mark.parametrize(("path", "selected_type", "expected"), [
    ("run", "CSV files", "run.csv"),
    ("run", "Parquet files", "run.parquet"),
    ("run.csv", "Parquet files", "run.csv"),
    ("run.PQ", "CSV files", "run.PQ"),
    ("", "Parquet files", ""),
])
def test_save_path_completion(path, selected_type, expected):
    assert dataset_dialogs.complete_dataset_save_path(path, selected_type) == expected


def test_save_dialog_confirms_overwrite_after_adding_extension(tmp_path, monkeypatch):
    path = tmp_path / "run.parquet"
    path.touch()
    monkeypatch.setattr(dataset_dialogs.tk, "StringVar", lambda **_: SimpleNamespace(get=lambda: "Parquet files"))
    monkeypatch.setattr(dataset_dialogs.filedialog, "asksaveasfilename", lambda **_: str(tmp_path / "run"))
    confirmations = []
    monkeypatch.setattr(
        dataset_dialogs.messagebox, "askyesno",
        lambda *args, **kwargs: confirmations.append(args) or False,
    )
    assert dataset_dialogs.ask_dataset_save_path(object(), "Export") == ""
    assert len(confirmations) == 1


@pytest.mark.parametrize("extension", [".csv", ".parquet"])
def test_analysis_export_writes_selected_format_and_report(tmp_path, monkeypatch, extension):
    path = str(tmp_path / ("view" + extension))
    workspace = AnalysisWorkspace.__new__(AnalysisWorkspace)
    workspace.window = object()
    workspace.session = SimpleNamespace(working_frame=pd.DataFrame({"signal": [1.5, np.nan]}))
    workspace.column_roles = {"signal": "metadata"}
    workspace._latest_frequency_result = SimpleNamespace(analysis_name="Coherence")
    workspace._build_frequency_export_lines = lambda _: ["Analysis report"]
    messages = []
    workspace.notifications = SimpleNamespace(success=messages.append)

    @contextmanager
    def error_dialog(_):
        yield False

    workspace._error_dialog = error_dialog
    monkeypatch.setattr(analysis_app, "ask_dataset_save_path", lambda *_: path)
    workspace._export_current_view()

    if extension == ".parquet":
        restored = read_dataframe_parquet(path)
        assert restored.attrs[DATAFRAME_ROLE_ATTR] == workspace.column_roles
    else:
        restored = pd.read_csv(path, sep=";")
    pd.testing.assert_frame_equal(restored, workspace.session.working_frame)
    assert (tmp_path / ("view" + extension + ".analysis_report.txt")).read_text().strip() == "Analysis report"
    assert len(messages) == 1
