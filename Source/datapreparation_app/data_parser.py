"""
data_parser.py

Utility class for robust log file parsing and datetime handling.
"""

import re
import importlib.util
import warnings
from collections.abc import Callable

import pandas as pd


MIN_DATETIME_PARSE_RATIO = 0.8

# Compiled once at import time — used in both load_file and parse_datetime_series.
_DATETIME_COL_RE = re.compile(r"(time|date|timestamp)", re.I)

_DATETIME_FORMATS = [
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


class DataParser:
    """
    Static utility class for parsing log files and handling date/time columns.
    """

    @staticmethod
    def detect_decimal_marker(file_path: str, sep: str, skiprows: int) -> str:
        """
        Detect whether the decimal marker in a file is a comma or dot.
        Args:
            file_path: Path to the file.
            sep: Field separator.
            skiprows: Number of rows to skip.
        Returns:
            Detected decimal marker (',' or '.')
        """
        comma_pattern = re.compile(r"^[-+]?\d{1,3}(?:\.\d{3})*,\d+$")
        dot_pattern = re.compile(r"^[-+]?\d{1,3}(?:,\d{3})*\.\d+$")
        comma_score = 0
        dot_score = 0
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
                    parts = [p.strip() for p in line.split(sep)]
                    for p in parts:
                        if comma_pattern.match(p):
                            comma_score += 1
                        elif dot_pattern.match(p):
                            dot_score += 1
                    lines_read += 1
        except Exception:
            return "."
        return "," if comma_score > dot_score else "."

    _DATETIME_PROBE_SIZE = 200

    @staticmethod
    def parse_datetime_series(series: pd.Series) -> pd.Series:
        """
        Attempt to parse a pandas Series as datetime, trying multiple formats.
        Args:
            series: The pandas Series to parse.
        Returns:
            Series with parsed datetimes if successful, else original.
        """
        if pd.api.types.is_datetime64_any_dtype(series):
            return series
        if pd.api.types.is_numeric_dtype(series):
            return series
        candidate_mask = series.notna()
        # Compute the full stripped representation once; reuse for both probing and
        # the final parse so we avoid a second O(n) .astype(str).str.strip() pass.
        full_stripped = series.astype(str).str.strip()
        stripped = full_stripped[candidate_mask]
        stripped = stripped[stripped != ""]
        if stripped.empty:
            return series
        # Probe format detection on a small sample to avoid O(formats × n_rows) overhead.
        probe = stripped.iloc[: DataParser._DATETIME_PROBE_SIZE]
        for fmt in _DATETIME_FORMATS:
            parsed = pd.to_datetime(probe, format=fmt, errors="coerce")
            if DataParser._is_sufficient_datetime_parse(parsed):
                return pd.to_datetime(full_stripped, format=fmt, errors="coerce")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Could not infer format.*")
            parsed = pd.to_datetime(probe, errors="coerce")
        if DataParser._is_sufficient_datetime_parse(parsed):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Could not infer format.*")
                return pd.to_datetime(full_stripped, errors="coerce")
        return series

    @staticmethod
    def _is_sufficient_datetime_parse(parsed: pd.Series) -> bool:
        if parsed.empty:
            return False
        return parsed.notna().mean() >= MIN_DATETIME_PARSE_RATIO

    @staticmethod
    def load_file(
        file_path: str,
        progress_callback: Callable[[float, float, str], None] | None = None,
    ) -> tuple[pd.DataFrame, str, str]:
        """
        Load a log file into a pandas DataFrame, auto-detecting separator and decimal marker.
        Args:
            file_path: Path to the log file.
        Returns:
            Tuple of (DataFrame, separator, decimal marker)
        """
        def _report(current: float, total: float, label: str) -> None:
            if progress_callback is not None:
                progress_callback(current, total, label)

        def _read_csv_with_pandas(file_path: str, sep: str, skiprows: int, decimal_marker: str, dt_format_map: dict[str, str]) -> pd.DataFrame:
            return pd.read_csv(
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

        def _read_csv_with_pyarrow(file_path: str, sep: str, skiprows: int, decimal_marker: str) -> pd.DataFrame:
            return pd.read_csv(
                file_path,
                sep=sep,
                skiprows=skiprows,
                header=0,
                decimal=decimal_marker,
                engine="pyarrow",
            )

        _report(0.0, 100.0, "Reading file header")
        sep = ";"
        skiprows = 0
        comma_pattern = re.compile(r"^[-+]?\d{1,3}(?:\.\d{3})*,\d+$")
        dot_pattern = re.compile(r"^[-+]?\d{1,3}(?:,\d{3})*\.\d+$")
        comma_score = 0
        dot_score = 0
        dt_format_map: dict[str, str] = {}
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
            # Capture column names; sample datetime-like column values and decimal
            # markers — all in a single sequential read with no extra file opens.
            header_line = f.readline()
            col_names_raw = [c.strip() for c in header_line.split(sep)]
            dt_col_indices: dict[int, str] = {
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
                        val = parts[idx]
                        if val:
                            dt_col_samples[idx].append(val)
                for part in parts:
                    if comma_pattern.match(part):
                        comma_score += 1
                    elif dot_pattern.match(part):
                        dot_score += 1
                lines_read += 1
        # Detect a datetime format for each candidate column from the sample rows.
        # Columns with a confirmed format are parsed inline by read_csv (C engine,
        # single pass); any that remain object dtype fall back to parse_datetime_series.
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
        _report(20.0, 100.0, "Detecting decimal marker")
        decimal_marker = "," if comma_score > dot_score else "."
        _report(40.0, 100.0, "Reading tabular data")
        try:
            if importlib.util.find_spec("pyarrow") is not None:
                df = _read_csv_with_pyarrow(file_path, sep, skiprows, decimal_marker)
            else:
                df = _read_csv_with_pandas(file_path, sep, skiprows, decimal_marker, dt_format_map)
        except Exception:
            df = _read_csv_with_pandas(file_path, sep, skiprows, decimal_marker, dt_format_map)
        _report(70.0, 100.0, "Cleaning columns")
        if df.columns.size > 0:
            last_col = df.columns[-1]
            if (last_col == "" or str(last_col).startswith("Unnamed")) and df.iloc[:, -1].isna().all():
                df = df.iloc[:, :-1]

        datetime_columns = [col for col in df.columns if _DATETIME_COL_RE.search(str(col))]
        datetime_total = max(1, len(datetime_columns))
        for index, col in enumerate(datetime_columns, start=1):
            progress = 70.0 + (index / datetime_total) * 30.0
            _report(progress, 100.0, f"Parsing datetime columns ({index}/{datetime_total})")
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                continue  # already parsed inline by read_csv
            parsed = DataParser.parse_datetime_series(df[col])
            if pd.api.types.is_datetime64_any_dtype(parsed):
                df[col] = parsed
        if not datetime_columns:
            _report(100.0, 100.0, "Finalizing")
        return df, sep, decimal_marker
