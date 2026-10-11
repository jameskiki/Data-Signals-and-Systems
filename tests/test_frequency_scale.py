"""Display-only log frequency axes, including spectrogram/colorbar isolation."""

import matplotlib.pyplot as plt
import numpy as np

from Source.analysis_app.plotting import configure_frequency_scale, apply_frequency_scale
from Source.data_ops.spectral import compute_spectrogram
from Source.shared.plot_preparation import prepare_spectrogram_plot_data
from Source.shared.plot_utils import create_spectrogram_figure


def test_spectrum_and_phase_toggle_keeps_data_and_restores_linear_limits():
    figure, axes = plt.subplots(2, 1)
    frequencies = np.array([0, 0.0001, 0.001, 0.5])
    original = []
    for axis in axes:
        line, = axis.plot(frequencies, [10, 1, 2, 3])
        original.append((line.get_xdata().copy(), line.get_ydata().copy(), axis.get_xlim()))
    try:
        configure_frequency_scale(figure, axes, frequencies, "x", True)
        for axis in axes:
            assert axis.get_xscale() == "log"
            assert axis.get_xlim() == (0.0001, 0.5)
        figure.canvas.draw()
        apply_frequency_scale(figure, False)
        for axis, (x, y, limits) in zip(axes, original):
            assert axis.get_xscale() == "linear"
            assert axis.get_xlim() == limits
            np.testing.assert_array_equal(axis.lines[0].get_xdata(), x)
            np.testing.assert_array_equal(axis.lines[0].get_ydata(), y)
    finally:
        plt.close(figure)


def test_spectrogram_log_frequency_does_not_change_time_colorbar_or_power(sine_5hz_100fs):
    result = compute_spectrogram(sine_5hz_100fs, "signal", reference_column="time_s", segment_length=128)
    power = result.power.copy()
    figure = create_spectrogram_figure(prepare_spectrogram_plot_data(result))
    try:
        axis, colorbar = figure.get_axes()
        time_limits = axis.get_xlim()
        configure_frequency_scale(figure, [axis], result.frequencies, "y", True)
        assert axis.get_yscale() == "log"
        assert axis.get_ylim()[0] > 0
        assert axis.get_xlim() == time_limits
        assert colorbar.get_yscale() == "linear"
        figure.canvas.draw()
        apply_frequency_scale(figure, False)
        assert axis.get_yscale() == "linear"
        np.testing.assert_array_equal(result.power, power)
    finally:
        plt.close(figure)
