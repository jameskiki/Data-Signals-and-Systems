"""Shared state and configuration for the analysis workspace."""

from dataclasses import dataclass, field

import pandas as pd
import tkinter as tk

from Source.data_ops.models import DataSummary
from Source.data_ops.spectral import FFT_WINDOW_OPTIONS
from Source.shared.plot_options import PlotStyle


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
CORRELATION_STRONG_POSITIVE_COLOR = "#0b3d2e"
CORRELATION_STRONG_NEGATIVE_COLOR = "#7a1c3a"
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


class PlotStyleVars:
    """Tkinter variables mirroring each exposed PlotStyle field.

    Initialized from PlotStyle defaults so widgets show correct values on
    first launch without duplicating the default values in two places.
    """

    def __init__(self) -> None:
        _d = PlotStyle()
        self.show_grid = tk.BooleanVar(value=_d.show_grid)
        self.show_subgrid = tk.BooleanVar(value=_d.show_subgrid)
        self.show_legend = tk.BooleanVar(value=_d.show_legend)
        self.grid_alpha = tk.DoubleVar(value=_d.grid_alpha)
        self.subgrid_alpha = tk.DoubleVar(value=_d.subgrid_alpha)
        self.line_width = tk.DoubleVar(value=_d.line_width)
        self.marker_size = tk.DoubleVar(value=_d.marker_size)
        self.title_fontsize = tk.IntVar(value=_d.title_fontsize)
        self.label_fontsize = tk.IntVar(value=_d.label_fontsize)
        self.tick_fontsize = tk.IntVar(value=_d.tick_fontsize)
        self.legend_fontsize = tk.IntVar(value=_d.legend_fontsize)
        self.font_family = tk.StringVar(value=_d.font_family)
        self.marker = tk.StringVar(value=_d.marker)
        self.legend_location = tk.StringVar(value=_d.legend_location)

    def reset_to_defaults(self) -> None:
        """Reset all variables back to PlotStyle defaults."""
        _d = PlotStyle()
        self.show_grid.set(_d.show_grid)
        self.show_subgrid.set(_d.show_subgrid)
        self.show_legend.set(_d.show_legend)
        self.grid_alpha.set(_d.grid_alpha)
        self.subgrid_alpha.set(_d.subgrid_alpha)
        self.line_width.set(_d.line_width)
        self.marker_size.set(_d.marker_size)
        self.title_fontsize.set(_d.title_fontsize)
        self.label_fontsize.set(_d.label_fontsize)
        self.tick_fontsize.set(_d.tick_fontsize)
        self.legend_fontsize.set(_d.legend_fontsize)
        self.font_family.set(_d.font_family)
        self.marker.set(_d.marker)
        self.legend_location.set(_d.legend_location)
