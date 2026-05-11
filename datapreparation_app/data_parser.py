"""
data_parser.py

Utility class for robust log file parsing and datetime handling.
"""

import re
import warnings

import pandas as pd


MIN_DATETIME_PARSE_RATIO = 0.8


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
            if DataParser._is_sufficient_datetime_parse(parsed):
                return pd.to_datetime(series.astype(str).str.strip(), format=fmt, errors="coerce")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Could not infer format.*")
            parsed = pd.to_datetime(stripped, errors="coerce")
        if DataParser._is_sufficient_datetime_parse(parsed):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Could not infer format.*")
                return pd.to_datetime(series.astype(str).str.strip(), errors="coerce")
        return series

    @staticmethod
    def _is_sufficient_datetime_parse(parsed: pd.Series) -> bool:
        if parsed.empty:
            return False
        return parsed.notna().mean() >= MIN_DATETIME_PARSE_RATIO

    @staticmethod
    def load_file(file_path: str) -> tuple[pd.DataFrame, str, str]:
        """
        Load a log file into a pandas DataFrame, auto-detecting separator and decimal marker.
        Args:
            file_path: Path to the log file.
        Returns:
            Tuple of (DataFrame, separator, decimal marker)
        """
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
        decimal_marker = DataParser.detect_decimal_marker(file_path, sep, skiprows)
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
        for col in df.columns:
            if re.search(r"(time|date|timestamp)", str(col), re.I):
                parsed = DataParser.parse_datetime_series(df[col])
                if pd.api.types.is_datetime64_any_dtype(parsed):
                    df[col] = parsed
        return df, sep, decimal_marker
