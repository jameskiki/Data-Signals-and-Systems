from dataclasses import dataclass, field
from typing import List

@dataclass
class PlotOptions:
    """Configuration for a plot figure."""
    cols_to_plot: List[str] = field(default_factory=list)
    xcol: str = "Index"
    use_subplots: bool = True
