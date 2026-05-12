"""Shared state and configuration for the analysis workspace."""

from dataclasses import dataclass, field

import pandas as pd

from data_ops.models import DataSummary
from data_ops.spectral import FFT_WINDOW_OPTIONS


ANALYSIS_WINDOW_GEOMETRY = "1450x900"
PREVIEW_ROW_LIMIT = 200
DERIVED_OPERATIONS = [
    "delta", "ratio", "rolling_mean", "derivative", "normalized",
    "detrend", "integrate", "rms_envelope", "hilbert_envelope",
]
UI_FREQUENCY_ANALYSIS_METHODS = ["FFT Amplitude", "Welch PSD", "Transfer Estimate", "Coherence", "Spectrogram"]
STATISTICS_COLUMNS = ["count", "missing", "min", "max", "mean", "std", "rms", "peak_to_peak"]
STATISTICS_COLUMN_LABELS = {
    "count": "n",
    "missing": "na",
    "min": "min",
    "max": "max",
    "mean": "avg",
    "std": "sd",
    "rms": "rms",
    "peak_to_peak": "p2p",
}
CORRELATION_POSITIVE_THRESHOLD = 0.7
CORRELATION_NEGATIVE_THRESHOLD = -0.7
CORRELATION_STRONG_POSITIVE_COLOR = "#1b5e20"
CORRELATION_STRONG_NEGATIVE_COLOR = "#b71c1c"
CORRELATION_DIAGONAL_COLOR = "#0d47a1"
CORRELATION_HEADER_COLOR = "#444444"


@dataclass
class AnalysisSession:
    """Mutable session state for one analysis workspace."""

    source_path: str
    original_frame: pd.DataFrame
    working_frame: pd.DataFrame
    selected_x_column: str = "Index"
    selected_y_columns: list[str] = field(default_factory=list)
    use_subplots: bool = True
    last_summary: DataSummary | None = None
    last_summary_revision: int = -1
    working_revision: int = 0
