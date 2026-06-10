"""Tests for data_ops.signals – derived columns and signal filters."""

import numpy as np
import pandas as pd
import pytest

from Source.data_ops.signals import add_derived_column, apply_signal_filter


# ── Derived columns ──────────────────────────────────────────────────


class TestDelta:
    def test_delta_first_row_is_nan(self, linear_ramp):
        result = add_derived_column(linear_ramp, "delta", "value", "d_value")
        assert pd.isna(result["d_value"].iloc[0])

    def test_delta_constant_step(self, linear_ramp):
        result = add_derived_column(linear_ramp, "delta", "value", "d_value")
        steps = result["d_value"].dropna()
        assert steps.std() < 1e-10


class TestRatio:
    def test_ratio_self_is_one(self, two_column_df):
        result = add_derived_column(
            two_column_df, "ratio", "sensor_a", "ratio_col", second_column="sensor_a",
        )
        non_nan = result["ratio_col"].dropna()
        assert np.allclose(non_nan, 1.0, atol=1e-12)

    def test_ratio_missing_denominator_raises(self, linear_ramp):
        with pytest.raises(KeyError):
            add_derived_column(linear_ramp, "ratio", "value", "r", second_column="nonexistent")


class TestNormalized:
    def test_normalized_has_zero_mean(self, noisy_sine):
        result = add_derived_column(noisy_sine, "normalized", "signal", "norm")
        assert abs(result["norm"].mean()) < 1e-10

    def test_normalized_has_unit_std(self, noisy_sine):
        result = add_derived_column(noisy_sine, "normalized", "signal", "norm")
        assert abs(result["norm"].std(ddof=1) - 1.0) < 1e-10


class TestDetrend:
    def test_detrend_removes_linear_trend(self, linear_ramp):
        result = add_derived_column(linear_ramp, "detrend", "value", "dt", window_size=1)
        assert abs(result["dt"].mean()) < 0.1

    def test_detrend_quadratic(self):
        t = np.linspace(0, 1, 500)
        df = pd.DataFrame({"t": t, "y": 3 * t**2 + 2 * t + 1 + 0.01 * np.sin(100 * t)})
        result = add_derived_column(df, "detrend", "y", "dt", window_size=2)
        assert result["dt"].std() < 0.1


class TestRollingMean:
    def test_smooths_signal(self, noisy_sine):
        result = add_derived_column(noisy_sine, "rolling_mean", "signal", "smooth", window_size=20)
        assert result["smooth"].std() < noisy_sine["signal"].std()

    def test_preserves_mean(self, noisy_sine):
        result = add_derived_column(noisy_sine, "rolling_mean", "signal", "smooth", window_size=10)
        assert abs(result["smooth"].mean() - noisy_sine["signal"].mean()) < 0.1


class TestDerivative:
    def test_derivative_of_linear(self, linear_ramp):
        result = add_derived_column(
            linear_ramp, "derivative", "value", "dv_dt", second_column="time_s",
        )
        values = result["dv_dt"].dropna()
        assert values.std() < 0.1  # constant slope → constant derivative

    def test_derivative_of_quadratic(self):
        t = np.linspace(0.01, 5, 500)
        df = pd.DataFrame({"t": t, "y": t**2})
        result = add_derived_column(df, "derivative", "y", "dy_dt", second_column="t")
        dy = result["dy_dt"].dropna()
        expected = 2 * t[1:]  # d/dt(t^2) = 2t
        assert np.allclose(dy.values, expected, atol=0.2)


class TestIntegrate:
    def test_integrate_constant_gives_linear(self):
        t = np.linspace(0, 5, 1000)
        df = pd.DataFrame({"t": t, "y": np.ones_like(t)})
        result = add_derived_column(df, "integrate", "y", "integral", second_column="t")
        assert abs(result["integral"].iloc[-1] - 5.0) < 0.1


class TestRmsEnvelope:
    def test_rms_envelope_positive(self, noisy_sine):
        result = add_derived_column(noisy_sine, "rms_envelope", "signal", "env", window_size=20)
        assert (result["env"].dropna() >= 0).all()


class TestHilbertEnvelope:
    def test_hilbert_envelope_matches_amplitude(self):
        t = np.linspace(0, 1, 1000)
        df = pd.DataFrame({"t": t, "y": 2.0 * np.sin(2 * np.pi * 10 * t)})
        result = add_derived_column(df, "hilbert_envelope", "y", "env")
        assert abs(result["env"].max() - 2.0) < 0.1

    def test_hilbert_envelope_nonnegative(self, noisy_sine):
        result = add_derived_column(noisy_sine, "hilbert_envelope", "signal", "env")
        assert (result["env"].dropna() >= 0).all()


class TestDerivedEdgeCases:
    def test_unknown_operation_raises(self, linear_ramp):
        with pytest.raises(ValueError, match="Unsupported"):
            add_derived_column(linear_ramp, "bogus", "value", "out")

    def test_unknown_column_raises(self, linear_ramp):
        with pytest.raises(KeyError):
            add_derived_column(linear_ramp, "delta", "nonexistent", "out")

    def test_empty_column_name_raises(self, linear_ramp):
        with pytest.raises(ValueError, match="name"):
            add_derived_column(linear_ramp, "delta", "value", "  ")


# ── Signal filters ───────────────────────────────────────────────────


class TestMovingAverage:
    def test_smooths_noise(self, noisy_sine):
        result = apply_signal_filter(noisy_sine, "signal", "moving_average", "smooth", window_size=15)
        raw_std = noisy_sine["signal"].std()
        smooth_std = result["smooth"].std()
        assert smooth_std < raw_std


class TestMedianFilter:
    def test_removes_spike(self):
        values = np.zeros(100)
        values[50] = 1000.0
        df = pd.DataFrame({"sig": values})
        result = apply_signal_filter(df, "sig", "median", "filtered", window_size=5)
        assert result["filtered"].max() < 1.0


class TestExponentialSmoothing:
    def test_alpha_bounds(self, noisy_sine):
        with pytest.raises(ValueError, match="Alpha"):
            apply_signal_filter(noisy_sine, "signal", "exponential_smoothing", "out", alpha=0.0)
        with pytest.raises(ValueError, match="Alpha"):
            apply_signal_filter(noisy_sine, "signal", "exponential_smoothing", "out", alpha=1.5)


class TestHighPass:
    def test_removes_dc_offset(self):
        values = np.ones(200) * 10.0 + 0.5 * np.sin(np.linspace(0, 20 * np.pi, 200))
        df = pd.DataFrame({"sig": values})
        result = apply_signal_filter(df, "sig", "high_pass", "hp", window_size=30)
        assert abs(result["hp"].mean()) < 1.0


class TestButterworthLowpass:
    def test_attenuates_high_frequency(self):
        fs = 200.0
        t = np.arange(0, 2, 1 / fs)
        # Low component at 5 Hz, high component at 80 Hz
        sig = np.sin(2 * np.pi * 5 * t) + np.sin(2 * np.pi * 80 * t)
        df = pd.DataFrame({"sig": sig})
        result = apply_signal_filter(
            df, "sig", "butterworth_lowpass", "lp",
            cutoff_hz=20.0, sample_spacing=1 / fs, filter_order=4,
        )
        # After lowpass at 20 Hz, the 80 Hz component should be mostly gone
        residual = result["lp"] - np.sin(2 * np.pi * 5 * t)
        assert residual.std() < 0.15

    def test_bad_spacing_raises(self, noisy_sine):
        with pytest.raises(ValueError, match="spacing"):
            apply_signal_filter(
                noisy_sine, "signal", "butterworth_lowpass", "out",
                cutoff_hz=10.0, sample_spacing=0.0, filter_order=2,
            )

    def test_cutoff_above_nyquist_raises(self):
        df = pd.DataFrame({"sig": np.ones(100)})
        with pytest.raises(ValueError, match="outside valid range"):
            apply_signal_filter(
                df, "sig", "butterworth_lowpass", "out",
                cutoff_hz=60.0, sample_spacing=0.01, filter_order=2,
            )


class TestButterworthHighpass:
    def test_removes_low_frequency(self):
        fs = 200.0
        t = np.arange(0, 2, 1 / fs)
        sig = np.sin(2 * np.pi * 1 * t) + np.sin(2 * np.pi * 50 * t)
        df = pd.DataFrame({"sig": sig})
        result = apply_signal_filter(
            df, "sig", "butterworth_highpass", "hp",
            cutoff_hz=10.0, sample_spacing=1 / fs, filter_order=4,
        )
        # The 1 Hz component should be mostly removed
        residual = result["hp"] - np.sin(2 * np.pi * 50 * t)
        assert residual.std() < 0.15


class TestFilterEdgeCases:
    def test_unknown_operation_raises(self, noisy_sine):
        with pytest.raises(ValueError, match="Unsupported"):
            apply_signal_filter(noisy_sine, "signal", "bogus_filter", "out")

    def test_unknown_column_raises(self, noisy_sine):
        with pytest.raises(KeyError):
            apply_signal_filter(noisy_sine, "nonexistent", "moving_average", "out")
