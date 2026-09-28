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


def test_overlay_cycles_palette_when_roles_unavailable() -> None:
    df_a = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.0, 2.0]})
    df_b = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [2.0, 3.0]})
    style = PlotStyle(color_palette=["#123456", "#abcdef"])
    options = PlotOptions(
        cols_to_plot=["signal"],
        xcol="time_s",
        use_subplots=False,
        style=style,
    )

    figure = create_plot_figure(options, ["a", "b"], {"a": df_a, "b": df_b})
    colors = [line.get_color() for line in figure.get_axes()[0].lines]

    assert colors == ["#123456", "#abcdef"]


def test_overlay_cycles_palette_when_role_mapping_is_missing_columns() -> None:
    df_a = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.0, 2.0]})
    df_b = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [2.0, 3.0]})
    style = PlotStyle(color_palette=["#654321", "#fedcba"])
    options = PlotOptions(
        cols_to_plot=["signal"],
        xcol="time_s",
        use_subplots=False,
        style=style,
    )

    figure = create_plot_figure(
        options,
        ["a", "b"],
        {"a": df_a, "b": df_b},
        column_roles={"other": "signal"},
    )
    colors = [line.get_color() for line in figure.get_axes()[0].lines]

    assert colors == ["#654321", "#fedcba"]


def test_overlay_uses_dataset_specific_role_mapping_when_provided() -> None:
    df_a = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.0, 2.0]})
    df_b = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [2.0, 3.0]})
    options = PlotOptions(
        cols_to_plot=["signal"],
        xcol="time_s",
        use_subplots=False,
        style=PlotStyle(color_palette=["#654321", "#fedcba"]),
    )

    figure = create_plot_figure(
        options,
        ["a", "b"],
        {"a": df_a, "b": df_b},
        column_roles={"a": {"signal": "signal"}, "b": {"signal": "output"}},
    )
    colors = [line.get_color() for line in figure.get_axes()[0].lines]

    assert colors == ["#7b1fa2", "#1b5e20"]


def test_overlay_uses_fixed_color_when_palette_is_empty() -> None:
    df = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.0, 2.0]})
    options = PlotOptions(
        cols_to_plot=["signal"],
        xcol="time_s",
        use_subplots=False,
        style=PlotStyle(color_palette=[]),
    )

    figure = create_plot_figure(options, ["a"], {"a": df}, column_roles=None)
    colors = [line.get_color() for line in figure.get_axes()[0].lines]

    assert colors == ["#1f77b4"]
