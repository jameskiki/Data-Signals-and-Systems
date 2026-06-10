from dataclasses import dataclass, field
from typing import List


@dataclass
class PlotStyle:
    """Shared visual/style contract used by generic plot builders."""

    show_grid: bool = True
    grid_alpha: float = 0.3
    show_legend: bool = True
    legend_location: str = "upper right"
    title_fontsize: int = 10
    label_fontsize: int = 9
    legend_fontsize: int = 8
    line_width: float = 2.0
    marker: str = "o"
    marker_size: float = 2.0

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
