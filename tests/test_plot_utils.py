"""Tests for shared.plot_utils contract-driven generic plotting behavior."""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest

matplotlib.use("Agg")

import pandas as pd

from Source.shared.plot_options import (
    CyclePlotData,
    DeviationPanelPlotData,
    DeviationPlotData,
    DeviationSeriesPlotData,
    FrequencySeriesPlotData,
    MagnitudePhasePlotData,
    PlotDescriptor,
    PlotOptions,
    PlotStyle,
    ResidualSpectrumPlotData,
    SignalComparisonPlotData,
    SpectrogramPlotData,
)
from Source.shared.plot_utils import (
    create_cycle_figure,
    create_deviation_figure,
    create_frequency_series_figure,
    create_magnitude_phase_figure,
    create_plot_figure,
    create_residual_spectrum_figure,
    create_signal_comparison_figure,
    create_spectrogram_figure,
)


def test_plot_descriptor_formats_family_and_variant() -> None:
    assert str(PlotDescriptor("Frequency", "Transfer estimate")) == "Frequency · Transfer estimate"


def test_frequency_series_renderer_draws_prepared_values_and_limits() -> None:
    figure = create_frequency_series_figure(
        FrequencySeriesPlotData(
            x_values=[0.0, 1.0, 2.0],
            y_values=[0.1, 0.8, 0.2],
            title="Coherence",
            y_label="Coherence",
            y_limits=(-0.02, 1.02),
            coherence_segment_count=3,
        )
    )
    axis = figure.get_axes()[0]

    np.testing.assert_array_equal(axis.lines[0].get_xdata(), [0.0, 1.0, 2.0])
    np.testing.assert_array_equal(axis.lines[0].get_ydata(), [0.1, 0.8, 0.2])
    assert axis.get_title() == "Coherence"
    assert axis.get_ylabel() == "Coherence"
    assert axis.get_ylim() == (-0.02, 1.02)
    assert any("Low confidence" in text.get_text() for text in axis.texts)


def test_deviation_and_residual_renderers_draw_prepared_series() -> None:
    deviation = DeviationPanelPlotData(
        series=(DeviationSeriesPlotData([0.0, 1.0], [-1.0, 2.0], "Candidate"),),
        title="Difference",
        x_label="Time [s]",
        y_label="Candidate - baseline",
        reference_label="Baseline (zero)",
        fill_deviations=True,
    )
    difference_figure = create_deviation_figure(
        DeviationPlotData((deviation,), "Difference Comparison")
    )
    residual_figure = create_residual_spectrum_figure(
        ResidualSpectrumPlotData(
            deviation=DeviationPanelPlotData(
                series=(DeviationSeriesPlotData([0.0, 1.0], [-1.0, 2.0], "Residual"),),
                title="Residual",
                x_label="Time [s]",
                y_label="Original - Filtered",
                reference_label="Zero residual",
            ),
            spectrum=FrequencySeriesPlotData([0.0, 1.0], [0.0, 0.5], "Residual Spectrum"),
        )
    )

    try:
        difference_axis = difference_figure.axes[0]
        residual_axis, spectrum_axis = residual_figure.axes
        assert residual_axis.get_subplotspec().get_gridspec().get_geometry() == (1, 2)
        np.testing.assert_array_equal(difference_axis.lines[0].get_ydata(), [-1.0, 2.0])
        assert difference_axis.lines[1].get_linestyle() == "--"
        assert {collection.get_label() for collection in difference_axis.collections} == {
            "Above baseline",
            "Below baseline",
        }
        np.testing.assert_array_equal(residual_axis.lines[0].get_ydata(), [-1.0, 2.0])
        np.testing.assert_array_equal(spectrum_axis.lines[0].get_ydata(), [0.0, 0.5])
    finally:
        plt.close(difference_figure)
        plt.close(residual_figure)


def test_magnitude_phase_renderer_draws_prepared_values_without_conversion() -> None:
    frequencies = np.array([1.0, 2.0, 3.0])
    magnitude = np.array([-3.0, -6.0, -9.0])
    phase_degrees = np.array([180.0, 90.0, -45.0])

    figure = create_magnitude_phase_figure(
        MagnitudePhasePlotData(
            x_values=frequencies,
            magnitude_values=magnitude,
            phase_degrees=phase_degrees,
            magnitude_title="Magnitude",
            magnitude_label="Magnitude [dB]",
            phase_title="Phase",
            wrapped_phase=True,
        )
    )
    magnitude_axis, phase_axis = figure.get_axes()
    assert magnitude_axis.get_subplotspec().get_gridspec().get_geometry() == (1, 2)

    np.testing.assert_array_equal(magnitude_axis.lines[0].get_xdata(), frequencies)
    np.testing.assert_array_equal(magnitude_axis.lines[0].get_ydata(), magnitude)
    np.testing.assert_array_equal(phase_axis.lines[0].get_ydata(), phase_degrees)
    assert magnitude_axis.get_ylabel() == "Magnitude [dB]"
    assert phase_axis.get_ylabel() == "Phase [deg]"
    assert phase_axis.get_ylim() == pytest.approx((-200.0, 200.0))


def test_spectrogram_renderer_draws_prepared_db_values_without_conversion() -> None:
    power_db = np.array([[-30.0, -20.0], [-10.0, 0.0]])

    figure = create_spectrogram_figure(
        SpectrogramPlotData(
            times=[0.0, 1.0],
            frequencies=[2.0, 4.0],
            power_db=power_db,
            title="Prepared Spectrogram",
            x_label="Time [s]",
        )
    )
    plot_axis = figure.get_axes()[0]

    np.testing.assert_array_equal(plot_axis.collections[0].get_array(), power_db)
    assert plot_axis.get_title() == "Prepared Spectrogram"


def test_signal_comparison_renderer_draws_prepared_values_without_conversion() -> None:
    figure = create_signal_comparison_figure(
        SignalComparisonPlotData(
            x_values=[0.0, 0.5, 1.0],
            original_values=[1.0, 2.0, 3.0],
            comparison_values=[0.8, 1.8, 2.8],
            title="Comparison",
            x_label="Time [s]",
            y_label="Signal",
        )
    )
    axis = figure.get_axes()[0]

    np.testing.assert_array_equal(axis.lines[0].get_ydata(), [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(axis.lines[1].get_ydata(), [0.8, 1.8, 2.8])
    assert axis.lines[0].get_linestyle() == "--"
    assert axis.get_ylabel() == "Signal"


def test_cycle_renderer_respects_enabled_metric_controls() -> None:
    plot_data = CyclePlotData(
        step_values=[0.0, 1.0, 2.0],
        selected_cycles=[[1.0, 2.0, 1.0], [1.5, 2.5, 1.5]],
        mean_values=[1.25, 2.25, 1.25],
        std_values=[0.25, 0.25, 0.25],
        early_mean_values=None,
        late_mean_values=None,
        support_values=None,
        cycle_numbers=[1.0, 2.0],
        metric_values={
            "mean": [1.3, 1.4],
            "rms": [1.5, 1.6],
            "peak_to_peak": [1.0, 1.0],
            "min": [1.0, 1.1],
            "max": [2.0, 2.1],
        },
        length_values=[1.0, 1.1],
        length_label="Cycle duration [s]",
        length_legend="dur [s]",
        source_label="cycle_process",
    )

    figure = create_cycle_figure(plot_data, enabled_metrics=["mean", "peak_to_peak"])
    metrics_axis = figure.get_axes()[2]

    assert metrics_axis.get_subplotspec().get_gridspec().get_geometry() == (3, 1)
    cycle_axis, representative_axis = figure.get_axes()[:2]
    assert cycle_axis.get_position().y0 > representative_axis.get_position().y0 > metrics_axis.get_position().y0
    assert [line.get_label() for line in metrics_axis.lines] == ["mean", "p2p"]


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



def test_subplot_uses_contract_y_label_and_balanced_columns() -> None:
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
    assert axes[0].get_subplotspec().get_gridspec().get_geometry() == (1, 2)


@pytest.mark.parametrize(
    "panel_count, expected_grid",
    [(1, (1, 1)), (2, (1, 2)), (3, (2, 2)), (5, (2, 3)), (9, (3, 3)), (10, (3, 4))],
)
def test_generic_subplots_use_balanced_grids(panel_count, expected_grid) -> None:
    columns = [f"signal_{index}" for index in range(panel_count)]
    dataframe = pd.DataFrame({column: [1.0, 2.0] for column in columns})
    figure = create_plot_figure(
        PlotOptions(cols_to_plot=columns, subplot_columns=1),
        ["sample"],
        {"sample": dataframe},
    )
    try:
        assert figure.axes[0].get_subplotspec().get_gridspec().get_geometry() == expected_grid
        assert sum(axis.get_visible() for axis in figure.axes) == panel_count
        assert all(not axis.get_visible() for axis in figure.axes[panel_count:])
    finally:
        plt.close(figure)


@pytest.mark.parametrize("channels_in_grid", [False, True])
def test_deviation_panels_use_balanced_grids(channels_in_grid) -> None:
    panel = DeviationPanelPlotData(
        series=(DeviationSeriesPlotData([0.0, 1.0], [1.0, 2.0], "Candidate"),),
        title="Difference",
        x_label="Index",
        y_label="Deviation",
    )
    figure = create_deviation_figure(
        DeviationPlotData((panel,) * 5, "Differences", channels_in_grid=channels_in_grid)
    )
    try:
        assert figure.axes[0].get_subplotspec().get_gridspec().get_geometry() == (2, 3)
        assert sum(axis.get_visible() for axis in figure.axes) == 5
        assert not figure.axes[-1].get_visible()
    finally:
        plt.close(figure)



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


def test_overlay_cycles_configured_palette() -> None:
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


@pytest.mark.parametrize("use_subplots", [False, True])
def test_dataset_line_styles_apply_to_overlay_and_subplots(use_subplots: bool) -> None:
    data_frames = {
        "baseline": pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.0, 2.0]}),
        "candidate": pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.5, 2.5]}),
    }
    options = PlotOptions(
        cols_to_plot=["signal"],
        xcol="time_s",
        use_subplots=use_subplots,
    )

    figure = create_plot_figure(
        options,
        ["baseline", "candidate"],
        data_frames,
        dataset_line_styles={"baseline": "--"},
    )
    lines = figure.get_axes()[0].lines

    assert lines[0].get_linestyle() == "--"
    assert lines[1].get_linestyle() == "-"


def test_overlay_uses_fixed_color_when_palette_is_empty() -> None:
    df = pd.DataFrame({"time_s": [0.0, 1.0], "signal": [1.0, 2.0]})
    options = PlotOptions(
        cols_to_plot=["signal"],
        xcol="time_s",
        use_subplots=False,
        style=PlotStyle(color_palette=[]),
    )

    figure = create_plot_figure(options, ["a"], {"a": df})
    colors = [line.get_color() for line in figure.get_axes()[0].lines]

    assert colors == ["#1f77b4"]
