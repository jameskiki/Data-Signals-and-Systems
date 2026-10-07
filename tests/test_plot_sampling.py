"""Adaptive plotting preserves extrema, gap breaks, and full-resolution zooms."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import pytest

from Source.shared.plot_options import PlotOptions, SignalComparisonPlotData
from Source.shared.plot_sampling import envelope_indices, plot_adaptive_line
from Source.shared.plot_utils import create_plot_figure, create_signal_comparison_figure


@pytest.mark.parametrize("count", [101, 1003, 100_000])
@pytest.mark.parametrize("budget", [8, 64, 512])
def test_envelope_is_bounded_ordered_and_preserves_extrema(count, budget):
    values = np.random.default_rng(42).normal(size=count)
    values[17] = 1000
    values[-19] = -1000
    selected = envelope_indices(values, budget)
    assert len(selected) <= budget
    assert np.all(np.diff(selected) > 0)
    assert selected[0] == 0 and selected[-1] == count - 1
    assert 17 in selected and count - 19 in selected
    step = (count + budget // 8 - 1) // (budget // 8)
    for start in range(0, count, step):
        bucket = values[start:start + step]
        assert start + np.argmin(bucket) in selected
        assert start + np.argmax(bucket) in selected


def test_envelope_preserves_breaks_when_missing_points_would_be_skipped():
    values = np.arange(10_000, dtype=float)
    values[333:338] = np.nan
    values[7500] = np.inf
    selected = envelope_indices(values, 64)
    assert 333 in selected
    assert 7500 in selected
    assert len(selected) <= 64
    for left, right in zip(selected[:-1], selected[1:]):
        if np.isfinite(values[left]) and np.isfinite(values[right]):
            assert np.isfinite(values[left:right + 1]).all()


def test_envelope_empty_small_and_all_missing():
    assert len(envelope_indices(np.array([]), 64)) == 0
    np.testing.assert_array_equal(envelope_indices(np.arange(10.0), 64), np.arange(10))
    values = np.full(100_000, np.nan)
    selected = envelope_indices(values, 64)
    assert len(selected) <= 64
    assert np.isnan(values[selected]).all()
    with pytest.raises(ValueError):
        envelope_indices(values, 0)


@pytest.mark.parametrize("descending", [False, True])
def test_large_line_zoom_restores_original_samples_and_caches_view(descending):
    x = np.arange(100_000)
    if descending:
        x = x[::-1]
    y = np.sin(x / 100)
    y[np.flatnonzero(x == 12345)[0]] = 1000
    figure, axis = plt.subplots()
    try:
        line = plot_adaptive_line(axis, x, y)
        figure.canvas.draw()
        assert len(line.get_xdata()) <= 20_000
        assert 1000 in line.get_ydata()
        assert axis.get_ylim()[1] >= 1000
        axis.set_xlim(12340, 12350)
        figure.canvas.draw()
        visible = (x >= 12339) & (x <= 12351)
        np.testing.assert_array_equal(line.get_xdata(), x[visible])
        np.testing.assert_array_equal(line.get_ydata(), y[visible])
        assert line._evaldata_adaptive_line.refresh() is False
        axis.set_xlim(-200, -100)
        figure.canvas.draw()
        assert len(line.get_xdata()) <= 1
    finally:
        plt.close(figure)


@pytest.mark.parametrize("timezone", [None, "Europe/Zurich"])
def test_datetime_zoom_uses_matplotlib_date_coordinates(timezone):
    frame = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=50_000, freq="s", tz=timezone),
        "value": np.sin(np.arange(50_000) / 100),
    })
    figure = create_plot_figure(
        PlotOptions(cols_to_plot=["value"], xcol="time", use_subplots=False),
        ["run"], {"run": frame},
    )
    try:
        axis = figure.axes[0]
        axis.set_xlim(frame["time"].iloc[1000], frame["time"].iloc[1010])
        figure.canvas.draw()
        x = axis.lines[0].get_xdata()
        assert len(x) < 20
        expected = mdates.date2num(frame["time"].iloc[1000])
        assert np.min(np.abs(x - expected)) < 1e-10
    finally:
        plt.close(figure)


@pytest.mark.parametrize("case", ["small", "unsorted", "categorical", "missing_x"])
def test_unsupported_or_small_series_keeps_full_original_line(case):
    count = 10 if case == "small" else 30_000
    x = np.arange(count, dtype=float)
    if case == "unsorted":
        x[10], x[11] = x[11], x[10]
    elif case == "categorical":
        x = np.full(count, "category")
    elif case == "missing_x":
        x[5] = np.nan
    y = np.arange(count, dtype=float)
    figure, axis = plt.subplots()
    try:
        line = plot_adaptive_line(axis, x, y)
        assert len(line.get_xdata()) == count
        np.testing.assert_array_equal(line.get_ydata(), y)
        assert not hasattr(line, "_evaldata_adaptive_line")
    finally:
        plt.close(figure)


@pytest.mark.parametrize("subplots", [False, True])
def test_generic_plots_preserve_independent_channel_peaks_and_shared_zoom(subplots):
    frame = pd.DataFrame({"a": np.zeros(100_000), "b": np.zeros(100_000)})
    frame.loc[12345, "a"] = 100
    frame.loc[12346, "b"] = -200
    original = frame.copy()
    figure = create_plot_figure(
        PlotOptions(cols_to_plot=["a", "b"], use_subplots=subplots),
        ["run"], {"run": frame},
    )
    try:
        figure.canvas.draw()
        axes = [axis for axis in figure.axes if axis.get_visible()]
        lines = [line for axis in axes for line in axis.lines]
        assert 100 in lines[0].get_ydata()
        assert -200 in lines[1].get_ydata()
        axes[0].set_xlim(12340, 12350)
        figure.canvas.draw()
        assert all(len(line.get_xdata()) < 20 for line in lines)
        assert all(len(axis.texts) == 1 for axis in axes)
        pd.testing.assert_frame_equal(frame, original)
    finally:
        plt.close(figure)


def test_filter_comparison_preview_uses_adaptive_lines():
    x = np.arange(100_000)
    figure = create_signal_comparison_figure(
        SignalComparisonPlotData(x, np.sin(x), np.cos(x), "Filter preview", "Index", "Value"),
    )
    try:
        figure.canvas.draw()
        assert all(len(line.get_xdata()) <= 20_000 for line in figure.axes[0].lines)
    finally:
        plt.close(figure)


def test_resize_updates_point_budget():
    figure, axis = plt.subplots(figsize=(2, 2))
    try:
        line = plot_adaptive_line(axis, np.arange(100_000), np.sin(np.arange(100_000)))
        figure.canvas.draw()
        small_count = len(line.get_xdata())
        figure.set_size_inches(10, 2)
        figure.canvas.draw()
        assert small_count < len(line.get_xdata()) <= 20_000
    finally:
        plt.close(figure)


def test_nullable_signal_and_constant_x_are_supported():
    count = 30_000
    values = pd.Series(np.arange(count), dtype="Int64")
    values.iloc[333] = pd.NA
    figure, axis = plt.subplots()
    try:
        line = plot_adaptive_line(axis, np.zeros(count), values)
        figure.canvas.draw()
        assert np.isnan(line.get_ydata()).any()
        assert len(line.get_xdata()) <= 20_000
    finally:
        plt.close(figure)


def test_plot_retains_source_snapshot_after_dataframe_changes():
    frame = pd.DataFrame({"signal": np.arange(30_000, dtype=float)})
    figure, axis = plt.subplots()
    try:
        line = plot_adaptive_line(axis, frame.index, frame["signal"])
        figure.canvas.draw()
        frame.loc[1000, "signal"] = -1000
        axis.set_xlim(995, 1005)
        figure.canvas.draw()
        x = line.get_xdata()
        y = line.get_ydata()
        assert y[np.flatnonzero(x == 1000)[0]] == 1000
    finally:
        plt.close(figure)
