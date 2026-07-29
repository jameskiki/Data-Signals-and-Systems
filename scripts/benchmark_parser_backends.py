"""Benchmark CSV parser backends on a real file.

This script is intentionally non-invasive: it does not change app behavior.
It compares parser ingestion times for available backends and reports
speedups against the current DataParser baseline.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from collections.abc import Callable

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from Source.datapreparation_app.data_parser import DataParser, _DATETIME_COL_RE


def _detect_separator_and_skiprows(file_path: str) -> tuple[str, int]:
    sep = ";"
    skiprows = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
        first_line = handle.readline()
        if first_line.lower().strip().startswith("sep="):
            sep = first_line.split("=", 1)[1].strip() or sep
            skiprows = 1
            while True:
                position = handle.tell()
                line = handle.readline()
                if not line:
                    break
                if line.strip() == "":
                    skiprows += 1
                    continue
                handle.seek(position)
                break
    return sep, skiprows


def _median_runtime(loader: Callable[[], pd.DataFrame], runs: int) -> tuple[float, tuple[int, int]]:
    times: list[float] = []
    shape = (0, 0)
    for _ in range(runs):
        t0 = time.perf_counter()
        frame = loader()
        times.append(time.perf_counter() - t0)
        shape = frame.shape
    return statistics.median(times), shape


def _load_via_data_parser(file_path: str) -> pd.DataFrame:
    frame, _, _ = DataParser.load_file(file_path)
    return frame


def _load_via_pandas_c(file_path: str, sep: str, skiprows: int, decimal_marker: str) -> pd.DataFrame:
    return pd.read_csv(
        file_path,
        sep=sep,
        skiprows=skiprows,
        skipinitialspace=True,
        header=0,
        decimal=decimal_marker,
        engine="c",
        low_memory=False,
    )


def _load_via_pandas_c_plus_datetime(file_path: str, sep: str, skiprows: int, decimal_marker: str) -> pd.DataFrame:
    frame = _load_via_pandas_c(file_path, sep=sep, skiprows=skiprows, decimal_marker=decimal_marker)
    datetime_columns = [column for column in frame.columns if _DATETIME_COL_RE.search(str(column))]
    for column in datetime_columns:
        if pd.api.types.is_datetime64_any_dtype(frame[column]):
            continue
        parsed = DataParser.parse_datetime_series(frame[column])
        if pd.api.types.is_datetime64_any_dtype(parsed):
            frame[column] = parsed
    return frame


def _load_via_pandas_pyarrow(file_path: str, sep: str, skiprows: int, decimal_marker: str) -> pd.DataFrame:
    return pd.read_csv(
        file_path,
        sep=sep,
        skiprows=skiprows,
        header=0,
        decimal=decimal_marker,
        engine="pyarrow",
    )


def _load_via_duckdb(file_path: str, sep: str, decimal_marker: str) -> pd.DataFrame:
    import duckdb

    relation = duckdb.sql(
        """
        SELECT *
        FROM read_csv_auto(
            ?,
            delim=?,
            decimal_separator=?,
            header=true,
            sample_size=-1
        )
        """,
        params=[file_path, sep, decimal_marker],
    )
    return relation.df()


def _load_via_polars(file_path: str, sep: str) -> pd.DataFrame:
    import polars as pl

    frame = pl.read_csv(
        file_path,
        separator=sep,
        try_parse_dates=True,
        infer_schema_length=10000,
    )
    return frame.to_pandas()


def _format_seconds(seconds: float) -> str:
    return f"{seconds:.3f}s"


def _print_result(name: str, seconds: float, baseline: float | None, shape: tuple[int, int]) -> None:
    if baseline is None:
        speed = "baseline"
    elif seconds == 0:
        speed = "n/a"
    else:
        ratio = baseline / seconds
        speed = f"{ratio:.2f}x {'faster' if ratio >= 1 else 'slower'}"
    print(f"{name:<22} {_format_seconds(seconds):>10}  {shape[0]:>10,} x {shape[1]:<4}  {speed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark CSV parser backends")
    parser.add_argument("file", help="Path to csv/log file")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per backend")
    args = parser.parse_args()

    file_path = args.file
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    sep, skiprows = _detect_separator_and_skiprows(file_path)
    decimal_marker = DataParser.detect_decimal_marker(file_path, sep=sep, skiprows=skiprows)

    print("=== Parser Backend Benchmark ===")
    print(f"file={file_path}")
    print(f"size_mb={os.path.getsize(file_path)/1_048_576:.2f}")
    print(f"runs={args.runs}")
    print(f"sep={sep} decimal={decimal_marker} skiprows={skiprows}")
    print()
    print(f"{'backend':<22} {'median':>10}  {'shape':>17}  speed_vs_dataparser")
    print("-" * 78)

    baseline_time, baseline_shape = _median_runtime(lambda: _load_via_data_parser(file_path), args.runs)
    _print_result("dataparser_current", baseline_time, None, baseline_shape)

    pandas_c_time, pandas_c_shape = _median_runtime(
        lambda: _load_via_pandas_c(file_path, sep=sep, skiprows=skiprows, decimal_marker=decimal_marker),
        args.runs,
    )
    _print_result("pandas_c_raw", pandas_c_time, baseline_time, pandas_c_shape)

    pandas_c_dt_time, pandas_c_dt_shape = _median_runtime(
        lambda: _load_via_pandas_c_plus_datetime(file_path, sep=sep, skiprows=skiprows, decimal_marker=decimal_marker),
        args.runs,
    )
    _print_result("pandas_c_plus_datetime", pandas_c_dt_time, baseline_time, pandas_c_dt_shape)

    try:
        pyarrow_time, pyarrow_shape = _median_runtime(
            lambda: _load_via_pandas_pyarrow(file_path, sep=sep, skiprows=skiprows, decimal_marker=decimal_marker),
            args.runs,
        )
        _print_result("pandas_pyarrow", pyarrow_time, baseline_time, pyarrow_shape)
    except Exception as error:  # Optional dependency or unsupported parsing path.
        print(f"{'pandas_pyarrow':<22} {'n/a':>10}  {'-':>17}  skipped ({error})")

    try:
        duckdb_time, duckdb_shape = _median_runtime(
            lambda: _load_via_duckdb(file_path, sep=sep, decimal_marker=decimal_marker),
            args.runs,
        )
        _print_result("duckdb", duckdb_time, baseline_time, duckdb_shape)
    except Exception as error:  # Optional dependency.
        print(f"{'duckdb':<22} {'n/a':>10}  {'-':>17}  skipped ({error})")

    try:
        polars_time, polars_shape = _median_runtime(
            lambda: _load_via_polars(file_path, sep=sep),
            args.runs,
        )
        _print_result("polars_to_pandas", polars_time, baseline_time, polars_shape)
    except Exception as error:  # Optional dependency.
        print(f"{'polars_to_pandas':<22} {'n/a':>10}  {'-':>17}  skipped ({error})")


if __name__ == "__main__":
    main()
