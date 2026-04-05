"""Shared test fixtures for data_ops tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sine_5hz_100fs():
    """5 Hz sine wave, amplitude 3, sampled at 100 Hz for 10 seconds."""
    fs = 100.0
    t = np.arange(0, 10, 1.0 / fs)
    signal = 3.0 * np.sin(2 * np.pi * 5.0 * t)
    return pd.DataFrame({"time_s": t, "signal": signal})


@pytest.fixture
def noisy_sine():
    """2 Hz sine + Gaussian noise, sampled at 200 Hz for 5 seconds."""
    rng = np.random.default_rng(42)
    fs = 200.0
    t = np.arange(0, 5, 1.0 / fs)
    signal = 1.5 * np.sin(2 * np.pi * 2.0 * t) + 0.3 * rng.standard_normal(len(t))
    return pd.DataFrame({"time_s": t, "signal": signal})


@pytest.fixture
def linear_ramp():
    """Linearly increasing signal from 0 to 100 over 1000 samples."""
    n = 1000
    t = np.linspace(0, 10, n)
    return pd.DataFrame({"time_s": t, "value": np.linspace(0, 100, n)})


@pytest.fixture
def two_column_df():
    """Two-column numeric dataframe for correlation and multi-column tests."""
    rng = np.random.default_rng(99)
    n = 500
    t = np.linspace(0, 5, n)
    a = np.sin(2 * np.pi * 3.0 * t)
    b = 0.8 * a + 0.2 * rng.standard_normal(n)
    return pd.DataFrame({"time_s": t, "sensor_a": a, "sensor_b": b})
