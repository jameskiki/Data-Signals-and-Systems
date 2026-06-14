from dataclasses import dataclass, field
from typing import List, Optional


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
