"""Datetime resolution regressions for spectral and coupled time operations."""

import numpy as np
import pandas as pd
import pytest

from Source.data_ops.time_axis import reference_axis_seconds
from Source.data_ops.spectral import (
    compute_fft_spectrum, compute_welch_psd, compute_spectrogram,
    compute_transfer_estimate, compute_coherence_spectrum,
)
from Source.data_ops.signals import add_derived_column
from Source.data_ops.frame_ops import resample_to_uniform
from Source.analysis_app.refresh import infer_sample_spacing


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
@pytest.mark.parametrize("timezone", [None, "UTC", "Europe/Berlin"])
def test_reference_axis_has_seconds_and_preserves_missing(unit, timezone):
    series = pd.Series(pd.date_range("2026-10-01", periods=4, freq="s", tz=timezone).as_unit(unit))
    series.iloc[1] = pd.NaT
    result = reference_axis_seconds(series)
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] - result.iloc[0] == 2
    assert infer_sample_spacing(pd.DataFrame({"time": series}), "time") == 1


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_spectral_methods_match_numeric_seconds(unit):
    elapsed = np.arange(1024)
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-10-01", periods=len(elapsed), freq="s").as_unit(unit),
        "elapsed": elapsed,
        "signal": 0.8 * np.sin(2 * np.pi * elapsed / 32),
        "response": 1.5 * np.sin(2 * np.pi * elapsed / 32),
    })
    for method in (compute_fft_spectrum, compute_welch_psd, compute_spectrogram,
                   compute_transfer_estimate, compute_coherence_spectrum):
        kwargs = {"dataframe": frame, "source_column": "signal"}
        if method in (compute_transfer_estimate, compute_coherence_spectrum):
            kwargs["comparison_column"] = "response"
        expected = method(**kwargs, reference_column="elapsed")
        actual = method(**kwargs, reference_column="timestamp")
        assert actual.sample_spacing == 1
        np.testing.assert_allclose(actual.frequencies, expected.frequencies)
        if method == compute_spectrogram:
            np.testing.assert_allclose(actual.power, expected.power)
        else:
            np.testing.assert_allclose(actual.amplitudes, expected.amplitudes)
            assert actual.dominant_frequency == expected.dominant_frequency


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_derivative_integral_and_resampling_use_seconds(unit):
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-10-01", periods=10, freq="s").as_unit(unit),
        "signal": np.arange(10, dtype=float),
    })
    derived = add_derived_column(frame, "derivative", "signal", "rate", second_column="timestamp")
    np.testing.assert_allclose(derived["rate"].iloc[1:], 1)
    integrated = add_derived_column(frame, "integrate", "signal", "area", second_column="timestamp")
    assert integrated["area"].iloc[-1] == 45
    sampled = resample_to_uniform(frame, "timestamp", 1)
    assert len(sampled) == 9
    np.testing.assert_allclose(np.diff(sampled["timestamp"]), 1)
