from dataclasses import dataclass, field
from collections.abc import Mapping, Sequence
from typing import List


@dataclass(frozen=True)
class PlotDescriptor:
    """User-visible identity for the plot currently shown in a canvas."""

    family: str
    variant: str

    def __str__(self) -> str:
        return f"{self.family} · {self.variant}"


@dataclass
class PlotStyle:
    """Shared visual/style contract used by generic plot builders."""

    # Grid
    show_grid: bool = True
    grid_alpha: float = 0.3
    grid_line_style: str = "--"
    grid_line_width: float = 0.5
    grid_color: str = "gray"
    # Sub-grid (minor grid)
    show_subgrid: bool = False
    subgrid_alpha: float = 0.15
    subgrid_line_style: str = ":"
    subgrid_line_width: float = 0.4
    subgrid_color: str = "lightgray"
    # Legend
    show_legend: bool = True
    legend_location: str = "upper right"
    legend_fontsize: int = 8
    # Font
    font_family: str = "sans-serif"
    title_fontsize: int = 10
    label_fontsize: int = 9
    tick_fontsize: int = 8
    # Lines / markers
    line_width: float = 2.0
    marker: str = "o"
    marker_size: float = 2.0
    # Color palette (cycled when column role provides no color)
    color_palette: List[str] = field(
        default_factory=lambda: [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
            "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        ]
    )

@dataclass
class PlotOptions:
    """Configuration for a plot figure."""
    cols_to_plot: List[str] = field(default_factory=list)
    xcol: str = "Index"
    use_subplots: bool = True
    # Contract fields for consistent plot presentation.
    title: str | None = None
    y_label: str = "Value"
    subplot_columns: int = 2
    style: PlotStyle = field(default_factory=PlotStyle)


@dataclass(frozen=True)
class MagnitudePhasePlotData:
    """Fully prepared values and labels for a magnitude/phase figure."""

    x_values: Sequence[float]
    magnitude_values: Sequence[float]
    phase_degrees: Sequence[float]
    magnitude_title: str
    magnitude_label: str
    phase_title: str
    phase_label: str = "Phase [deg]"
    x_label: str = "Frequency [Hz]"
    wrapped_phase: bool = False


@dataclass(frozen=True)
class FrequencyPlotValues:
    """Prepared frequency-domain values passed from application logic to rendering."""

    frequencies: Sequence[float]
    magnitudes: Sequence[float]
    phase_degrees: Sequence[float] | None = None
    wrapped_phase: bool = False


@dataclass(frozen=True)
class FrequencySeriesPlotData:
    """Prepared values and labels for a single frequency-domain series."""

    x_values: Sequence[float]
    y_values: Sequence[float]
    title: str
    x_label: str = "Frequency [Hz]"
    y_label: str = "Amplitude"
    y_limits: tuple[float, float] | None = None
    coherence_segment_count: int | None = None


@dataclass(frozen=True)
class DeviationSeriesPlotData:
    """Prepared deviation values for one candidate or residual series."""

    x_values: Sequence[float]
    values: Sequence[float]
    label: str


@dataclass(frozen=True)
class DeviationPanelPlotData:
    """Prepared values and labels for one zero-referenced deviation panel."""

    series: Sequence[DeviationSeriesPlotData]
    title: str
    x_label: str
    y_label: str
    reference_label: str | None = None
    fill_deviations: bool = False
    unavailable_message: str | None = None


@dataclass(frozen=True)
class DeviationPlotData:
    """Prepared multi-panel candidate-minus-baseline plot values."""

    panels: Sequence[DeviationPanelPlotData]
    figure_title: str
    channels_in_grid: bool = False


@dataclass(frozen=True)
class ResidualSpectrumPlotData:
    """Prepared residual trace and optional frequency spectrum for one figure."""

    deviation: DeviationPanelPlotData
    spectrum: FrequencySeriesPlotData | None
    unavailable_spectrum_message: str = "Residual spectrum unavailable (need at least 4 finite samples)."


@dataclass(frozen=True)
class SpectrogramPlotData:
    """Fully prepared values and labels for a spectrogram figure."""

    times: Sequence[float]
    frequencies: Sequence[float]
    power_db: Sequence[Sequence[float]]
    title: str
    x_label: str
    y_label: str = "Frequency [Hz]"
    colorbar_label: str = "Power [dB]"


@dataclass(frozen=True)
class SignalComparisonPlotData:
    """Fully prepared values and labels for a two-signal overlay."""

    x_values: Sequence[float]
    original_values: Sequence[float]
    comparison_values: Sequence[float]
    title: str
    x_label: str
    y_label: str
    original_label: str = "Original"
    comparison_label: str = "Filtered"


@dataclass(frozen=True)
class CyclePlotData:
    """Fully prepared values and labels for a cycle-analysis figure."""

    step_values: Sequence[float]
    selected_cycles: Sequence[Sequence[float]]
    mean_values: Sequence[float]
    std_values: Sequence[float]
    early_mean_values: Sequence[float] | None
    late_mean_values: Sequence[float] | None
    support_values: Sequence[float] | None
    cycle_numbers: Sequence[float]
    metric_values: Mapping[str, Sequence[float]]
    length_values: Sequence[float]
    length_label: str
    length_legend: str
    source_label: str
