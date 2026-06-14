"""
benchmark_io.py

Measures load and write performance of the old vs new IO paths across three
dataset sizes. Generates synthetic CSV files on the fly — no real data needed.

Sizes
-----
small  :   10 000 rows, 12 columns  (~2 MB)
medium :   50 000 rows, 12 columns  (~10 MB)
large  : 10 000 000 rows, 12 columns (~1.8 GB)

Run
---
    .venv\Scripts\python scripts\benchmark_io.py
"""

from __future__ import annotations

import io
import os
import re
import statistics
import sys
import tempfile
import time
import warnings
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Synthetic data generator
# ---------------------------------------------------------------------------

COLUMNS = [
    "timestamp",
    "time_s",
    "channel_A",
    "channel_B",
    "channel_C",
    "channel_D",
    "channel_E",
    "temperature_C",
    "pressure_bar",
    "voltage_V",
    "current_A",
    "cycle_phase_deg",
]

SIZES = {
    "small":  10_000,
    "medium": 50_000,
    "large":  10_000_000,
}

RUNS = 3  # median of N runs per case


def _generate_csv(n_rows: int, path: str) -> None:
    """Write a synthetic `;`-separated CSV with a datetime column to *path*."""
    rng = np.random.default_rng(42)
    t = np.arange(n_rows) * 0.002  # 500 Hz
    # Vectorised timestamp generation — avoids a 10M-iteration Python loop.
    timestamps = pd.date_range("2024-01-01", periods=n_rows, freq="2ms").strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame({
        "timestamp":       timestamps,
        "time_s":          t,
        "channel_A":       np.sin(2 * np.pi * 1.0 * t),
        "channel_B":       np.sin(2 * np.pi * 7.5 * t) * 0.5,
        "channel_C":       np.sin(2 * np.pi * 18.0 * t) * 0.25,
        "channel_D":       rng.normal(0, 0.1, n_rows),
        "channel_E":       np.cos(2 * np.pi * 2.0 * t),
        "temperature_C":   20.0 + rng.normal(0, 0.5, n_rows),
        "pressure_bar":    1.013 + rng.normal(0, 0.01, n_rows),
        "voltage_V":       12.0 + rng.normal(0, 0.05, n_rows),
        "current_A":       2.5 + rng.normal(0, 0.02, n_rows),
        "cycle_phase_deg": (t * 360 * 1.0) % 360,
    })
    df.to_csv(path, sep=";", index=False)


# ---------------------------------------------------------------------------
# OLD load path (reconstructed — 3 file opens, no engine hint, full probe)
# ---------------------------------------------------------------------------

MIN_DATETIME_PARSE_RATIO = 0.8

def _old_detect_decimal_marker(file_path: str, sep: str, skiprows: int) -> str:
    comma_pattern = re.compile(r"^[-+]?\d{1,3}(?:\.\d{3})*,\d+$")
    dot_pattern   = re.compile(r"^[-+]?\d{1,3}(?:,\d{3})*\.\d+$")
    comma_score = dot_score = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(skiprows):
                f.readline()
            lines_read = 0
            while lines_read < 20:
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                for p in (p.strip() for p in line.split(sep)):
                    if comma_pattern.match(p):
                        comma_score += 1
                    elif dot_pattern.match(p):
                        dot_score += 1
                lines_read += 1
    except Exception:
        return "."
    return "," if comma_score > dot_score else "."


def _old_parse_datetime_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    if pd.api.types.is_numeric_dtype(series):
        return series
    candidate_mask = series.notna()
    stripped = series[candidate_mask].astype(str).str.strip()
    stripped = stripped[stripped != ""]
    if stripped.empty:
        return series
    formats = [
        "%Y %m %d %H:%M:%S:%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y %m %d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        parsed = pd.to_datetime(stripped, format=fmt, errors="coerce")
        if parsed.notna().mean() >= MIN_DATETIME_PARSE_RATIO:
            return pd.to_datetime(series.astype(str).str.strip(), format=fmt, errors="coerce")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Could not infer format.*")
        parsed = pd.to_datetime(stripped, errors="coerce")
    if parsed.notna().mean() >= MIN_DATETIME_PARSE_RATIO:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Could not infer format.*")
            return pd.to_datetime(series.astype(str).str.strip(), errors="coerce")
    return series


def _old_load_file(file_path: str) -> tuple[pd.DataFrame, str, str]:
    sep = ";"
    skiprows = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
        if first_line.lower().strip().startswith("sep="):
            sep = first_line.split("=", 1)[1].strip() or sep
            skiprows = 1
            while True:
                position = f.tell()
                line = f.readline()
                if not line:
                    break
                if line.strip() == "":
                    skiprows += 1
                    continue
                f.seek(position)
                break
    decimal_marker = _old_detect_decimal_marker(file_path, sep, skiprows)
    df = pd.read_csv(
        file_path,
        sep=sep,
        skiprows=skiprows,
        skipinitialspace=True,
        header=0,
        decimal=decimal_marker,
    )
    if df.columns.size > 0:
        last_col = df.columns[-1]
        if (last_col == "" or str(last_col).startswith("Unnamed")) and df.iloc[:, -1].isna().all():
            df = df.iloc[:, :-1]
    datetime_columns = [col for col in df.columns if re.search(r"(time|date|timestamp)", str(col), re.I)]
    for col in datetime_columns:
        parsed = _old_parse_datetime_series(df[col])
        if pd.api.types.is_datetime64_any_dtype(parsed):
            df[col] = parsed
    return df, sep, decimal_marker


# ---------------------------------------------------------------------------
# OLD write path (per-chunk open/close)
# ---------------------------------------------------------------------------

def _old_write_csv(dataframe: pd.DataFrame, output_path: str, sep: str = ";", chunk_size: int = 100_000) -> None:
    total_rows = int(len(dataframe))
    if total_rows == 0:
        dataframe.to_csv(output_path, sep=sep, index=False)
        return
    for start in range(0, total_rows, chunk_size):
        end = min(start + chunk_size, total_rows)
        is_first_chunk = start == 0
        dataframe.iloc[start:end].to_csv(
            output_path,
            sep=sep,
            index=False,
            mode="w" if is_first_chunk else "a",
            header=is_first_chunk,
        )


# ---------------------------------------------------------------------------
# NEW paths — import from Source
# ---------------------------------------------------------------------------

from Source.datapreparation_app.data_parser import DataParser
from Source.data_ops.io_ops import write_dataframe_csv_with_progress


def _new_load_file(file_path: str) -> tuple[pd.DataFrame, str, str]:
    return DataParser.load_file(file_path)


def _new_write_csv(dataframe: pd.DataFrame, output_path: str, sep: str = ";") -> None:
    write_dataframe_csv_with_progress(dataframe, output_path, sep=sep)


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _median_time(fn: Callable, runs: int) -> float:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def _fmt(seconds: float) -> str:
    if seconds >= 1:
        return f"{seconds:.2f} s"
    return f"{seconds * 1000:.1f} ms"


def _speedup(old: float, new: float) -> str:
    if new == 0:
        return "N/A"
    ratio = old / new
    return f"{ratio:.2f}x {'faster' if ratio >= 1 else 'slower'}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{'='*68}")
    print(f"  IO Benchmark  —  {RUNS} runs per case, median reported")
    print(f"  Columns: {len(COLUMNS)}  |  Separator: ';'  |  1 datetime column")
    print(f"{'='*68}\n")

    header = f"{'Size':<8} {'Rows':>12} {'File':>8}  {'Old load':>10} {'New load':>10} {'Speedup':>12}"
    print("LOAD")
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    write_header = f"{'Size':<8} {'Rows':>12} {'File':>8}  {'Old write':>10} {'New write':>10} {'Speedup':>12}"

    write_rows = []

    with tempfile.TemporaryDirectory() as tmp:
        for name, n_rows in SIZES.items():
            csv_path = os.path.join(tmp, f"bench_{name}.csv")
            out_old   = os.path.join(tmp, f"out_old_{name}.csv")
            out_new   = os.path.join(tmp, f"out_new_{name}.csv")

            print(f"  Generating {name} ({n_rows:,} rows)...", end=" ", flush=True)
            _generate_csv(n_rows, csv_path)
            size_mb = os.path.getsize(csv_path) / 1_048_576
            print(f"{size_mb:.1f} MB")

            # Load benchmark
            old_load = _median_time(lambda p=csv_path: _old_load_file(p), RUNS)
            new_load = _median_time(lambda p=csv_path: _new_load_file(p), RUNS)

            print(f"  {name:<8} {n_rows:>12,} {size_mb:>7.1f}M  {_fmt(old_load):>10} {_fmt(new_load):>10} {_speedup(old_load, new_load):>12}")

            # Pre-load df for write benchmark
            df, _, _ = _new_load_file(csv_path)

            # Write benchmark
            old_write = _median_time(lambda df=df, p=out_old: _old_write_csv(df, p), RUNS)
            new_write = _median_time(lambda df=df, p=out_new: _new_write_csv(df, p), RUNS)
            write_rows.append((name, n_rows, size_mb, old_write, new_write))

    print()
    print("WRITE")
    print("-" * len(write_header))
    print(write_header)
    print("-" * len(write_header))
    for name, n_rows, size_mb, old_write, new_write in write_rows:
        print(f"  {name:<8} {n_rows:>12,} {size_mb:>7.1f}M  {_fmt(old_write):>10} {_fmt(new_write):>10} {_speedup(old_write, new_write):>12}")

    print(f"\n{'='*68}\n")


if __name__ == "__main__":
    main()
