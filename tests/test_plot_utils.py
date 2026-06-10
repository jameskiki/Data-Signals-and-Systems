"""Tests for shared.plot_utils contract-driven generic plotting behavior."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import pandas as pd

from Source.shared.plot_options import PlotOptions, PlotStyle
from Source.shared.plot_utils import create_plot_figure


def test_overlay_uses_contract_title_and_y_label() -> None:
    df = pd.DataFrame({"time_s": [0.0, 1.0, 2.0], "signal": [1.0, 2.0, 3.0]})
    options = PlotOptions(
        cols_to_plot=["signal"],
        xcol="time_s",
        use_subplots=False,
        title="Contract Title",
        y_label="Pressure [bar]",
    )

    figure = create_plot_figure(options, ["sample"], {"sample": df})
    axis = figure.get_axes()[0]

    assert axis.get_title() == "Contract Title"
    assert axis.get_ylabel() == "Pressure [bar]"



def test_subplot_uses_contract_y_label_and_subplots_columns() -> None:
    df = pd.DataFrame(
        {
            "time_s": [0.0, 1.0, 2.0],
            "signal_a": [1.0, 2.0, 3.0],
            "signal_b": [1.5, 2.5, 3.5],
        }
    )
    options = PlotOptions(
        cols_to_plot=["signal_a", "signal_b"],
        xcol="time_s",
        use_subplots=True,
        subplot_columns=1,
        y_label="Force [N]",
    )

    figure = create_plot_figure(options, ["sample"], {"sample": df})
    axes = figure.get_axes()

    assert len(axes) == 2
    assert all(axis.get_ylabel() == "Force [N]" for axis in axes)



def test_style_contract_controls_legend_and_grid() -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0], "a": [1.0, 1.5, 2.0], "b": [2.0, 2.5, 3.0]})
    options = PlotOptions(
        cols_to_plot=["a", "b"],
        xcol="x",
        use_subplots=False,
        style=PlotStyle(show_grid=False, show_legend=False),
    )

    figure = create_plot_figure(options, ["sample"], {"sample": df})
    axis = figure.get_axes()[0]

    assert axis.get_legend() is None
    assert not any(line.get_visible() for line in axis.xaxis.get_gridlines())
    assert not any(line.get_visible() for line in axis.yaxis.get_gridlines())
