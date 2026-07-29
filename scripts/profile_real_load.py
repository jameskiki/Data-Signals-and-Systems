"""Profile real CSV load path with stage-level timings."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from Source.datapreparation_app.data_parser import (
    _DATETIME_COL_RE,
    _DATETIME_FORMATS,
    DataParser,
)


def profile_load(file_path: str) -> None:
    t_all_start = time.perf_counter()

    sep = ";"
    skiprows = 0
    comma_pattern = re.compile(r"^[-+]?\d{1,3}(?:\.\d{3})*,\d+$")
    dot_pattern = re.compile(r"^[-+]?\d{1,3}(?:,\d{3})*\.\d+$")
    comma_score = 0
    dot_score = 0
    dt_format_map: dict[str, str] = {}

    t_scan_start = time.perf_counter()
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

        header_line = f.readline()
        col_names_raw = [c.strip() for c in header_line.split(sep)]
        dt_col_indices = {
            i: name
            for i, name in enumerate(col_names_raw)
            if _DATETIME_COL_RE.search(name)
        }
        dt_col_samples: dict[int, list[str]] = {i: [] for i in dt_col_indices}

        lines_read = 0
        while lines_read < 20:
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(sep)]
            for idx in dt_col_indices:
                if idx < len(parts):
                    value = parts[idx]
                    if value:
                        dt_col_samples[idx].append(value)
            for part in parts:
                if comma_pattern.match(part):
                    comma_score += 1
                elif dot_pattern.match(part):
                    dot_score += 1
            lines_read += 1
    t_scan = time.perf_counter() - t_scan_start

    t_probe_start = time.perf_counter()
    for idx, col_name in dt_col_indices.items():
        samples = dt_col_samples.get(idx, [])
        if not samples:
            continue
        probe = pd.Series(samples)
        for fmt in _DATETIME_FORMATS:
            parsed_probe = pd.to_datetime(probe, format=fmt, errors="coerce")
            if DataParser._is_sufficient_datetime_parse(parsed_probe):
                dt_format_map[col_name] = fmt
                break
    t_probe = time.perf_counter() - t_probe_start

    decimal_marker = "," if comma_score > dot_score else "."

    t_read_start = time.perf_counter()
    df = pd.read_csv(
        file_path,
        sep=sep,
        skiprows=skiprows,
        skipinitialspace=True,
        header=0,
        decimal=decimal_marker,
        engine="c",
        low_memory=False,
        parse_dates=list(dt_format_map) if dt_format_map else False,
        date_format=dt_format_map if dt_format_map else None,
    )
    t_read = time.perf_counter() - t_read_start

    t_post_start = time.perf_counter()
    if df.columns.size > 0:
        last_col = df.columns[-1]
        if (last_col == "" or str(last_col).startswith("Unnamed")) and df.iloc[:, -1].isna().all():
            df = df.iloc[:, :-1]

    datetime_columns = [col for col in df.columns if _DATETIME_COL_RE.search(str(col))]
    for col in datetime_columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        parsed = DataParser.parse_datetime_series(df[col])
        if pd.api.types.is_datetime64_any_dtype(parsed):
            df[col] = parsed
    t_post = time.perf_counter() - t_post_start

    t_all = time.perf_counter() - t_all_start

    print("=== Real File Load Profile ===")
    print(f"file={file_path}")
    print(f"rows={len(df):,} cols={len(df.columns)}")
    print(f"datetime_cols={datetime_columns}")
    print(f"dt_format_map={dt_format_map}")
    print(f"sep={sep} decimal={decimal_marker} skiprows={skiprows}")
    print()
    print(f"scan_header_decimal_sample = {t_scan:.3f}s")
    print(f"probe_datetime_format     = {t_probe:.3f}s")
    print(f"read_csv                  = {t_read:.3f}s")
    print(f"postprocess_datetime      = {t_post:.3f}s")
    print(f"total                     = {t_all:.3f}s")

    print()
    if t_all > 0:
        print("=== Share of Total ===")
        print(f"scan_header_decimal_sample = {100.0 * t_scan / t_all:5.1f}%")
        print(f"probe_datetime_format     = {100.0 * t_probe / t_all:5.1f}%")
        print(f"read_csv                  = {100.0 * t_read / t_all:5.1f}%")
        print(f"postprocess_datetime      = {100.0 * t_post / t_all:5.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile real load path")
    parser.add_argument("file", help="Path to csv file")
    args = parser.parse_args()
    profile_load(args.file)


if __name__ == "__main__":
    main()
