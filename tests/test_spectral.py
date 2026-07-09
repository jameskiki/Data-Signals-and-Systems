"""Tests for data_ops.spectral – FFT, Welch PSD, Transfer Estimate, Coherence, Spectrogram."""

import numpy as np
import pandas as pd
import pytest
from scipy.signal import welch as scipy_welch

from Source.data_ops.spectral import (
    FrequencySpectrumResult,
    SpectrogramResult,
    _build_peak_frame,
    compute_coherence_spectrum,
    compute_fft_spectrum,
    compute_spectrogram,
    compute_transfer_estimate,
    compute_welch_psd,
)


# ── FFT ──────────────────────────────────────────────────────────────


class TestFFTSpectrum:
    def test_dominant_frequency_matches_input(self, sine_5hz_100fs):
        result = compute_fft_spectrum(sine_5hz_100fs, "signal", reference_column="time_s")
        assert abs(result.dominant_frequency - 5.0) < 0.5

    def test_rectangular_window_alias_is_supported(self, sine_5hz_100fs):
        result = compute_fft_spectrum(
            sine_5hz_100fs,
            "signal",
            reference_column="time_s",
            window="rectangular",
        )
        assert abs(result.dominant_frequency - 5.0) < 0.5

    def test_sample_metadata(self, sine_5hz_100fs):
        result = compute_fft_spectrum(sine_5hz_100fs, "signal", reference_column="time_s")
        assert result.sample_count == len(sine_5hz_100fs)
        assert abs(result.sampling_frequency - 100.0) < 1.0
        assert abs(result.nyquist_frequency - 50.0) < 1.0

    def test_phase_is_none_for_fft(self, sine_5hz_100fs):
        result = compute_fft_spectrum(sine_5hz_100fs, "signal", reference_column="time_s")
        assert result.phase is None

    def test_frequencies_are_positive(self, sine_5hz_100fs):
        result = compute_fft_spectrum(sine_5hz_100fs, "signal", reference_column="time_s")
        assert (result.frequencies >= 0).all()

    def test_unknown_column_raises(self, sine_5hz_100fs):
        with pytest.raises(KeyError, match="Unknown source column"):
            compute_fft_spectrum(sine_5hz_100fs, "nonexistent")

    def test_unsupported_window_raises(self, sine_5hz_100fs):
        with pytest.raises(ValueError, match="Unsupported FFT window"):
            compute_fft_spectrum(
                sine_5hz_100fs,
                "signal",
                reference_column="time_s",
                window="definitely_not_a_window",
            )

    def test_peaks_frame_has_rows(self, sine_5hz_100fs):
        result = compute_fft_spectrum(sine_5hz_100fs, "signal", reference_column="time_s", peak_count=5)
        assert len(result.peaks_frame) <= 5
        assert "frequency_hz" in result.peaks_frame.columns

    def test_peak_table_prefers_separated_local_maxima(self):
        fs = 100.0
        t = np.arange(0, 10, 1.0 / fs)
        signal = 4.0 * np.sin(2 * np.pi * 5.35 * t) + 1.5 * np.sin(2 * np.pi * 17.8 * t)
        df = pd.DataFrame({"time_s": t, "signal": signal})

        result = compute_fft_spectrum(df, "signal", reference_column="time_s", peak_count=2)

        peak_frequencies = result.peaks_frame["frequency_hz"].to_numpy(dtype=float)
        assert peak_frequencies[0] == pytest.approx(5.35, abs=0.3)
        assert peak_frequencies[1] == pytest.approx(17.8, abs=0.5)


class TestPeakFrameBuilder:
    def test_falls_back_to_top_bins_when_no_local_maxima_exist(self):
        frequencies = np.array([0.0, 1.0, 2.0, 3.0])
        amplitudes = np.array([0.0, 5.0, 4.0, 3.0])

        peaks = _build_peak_frame(frequencies, amplitudes, peak_count=2)

        assert peaks["frequency_hz"].tolist() == [1.0, 2.0]
        assert peaks["rank"].tolist() == [1, 2]


# ── Welch PSD ────────────────────────────────────────────────────────


class TestWelchPSD:
    def test_dominant_frequency(self, sine_5hz_100fs):
        result = compute_welch_psd(sine_5hz_100fs, "signal", reference_column="time_s")
        assert abs(result.dominant_frequency - 5.0) < 1.0

    def test_scaling_matches_scipy(self, sine_5hz_100fs):
        result = compute_welch_psd(
            sine_5hz_100fs, "signal", reference_column="time_s",
            window="hann", detrend=True, segment_length=256, overlap_fraction=0.5,
        )
        signal = sine_5hz_100fs["signal"].to_numpy()
        f_scipy, psd_scipy = scipy_welch(
            signal - signal.mean(), fs=100.0, window="hann", nperseg=256, noverlap=128, detrend=False,
        )
        idx_ours = np.argmin(np.abs(result.frequencies - 5.0))
        idx_scipy = np.argmin(np.abs(f_scipy - 5.0))
        ratio = result.amplitudes[idx_ours] / psd_scipy[idx_scipy]
        assert 0.8 < ratio < 1.2, f"Welch scaling ratio {ratio:.4f} is too far from 1.0"

    def test_total_power_matches_scipy(self, sine_5hz_100fs):
        result = compute_welch_psd(
            sine_5hz_100fs, "signal", reference_column="time_s",
            window="hann", detrend=True, segment_length=256, overlap_fraction=0.5,
        )
        signal = sine_5hz_100fs["signal"].to_numpy()
        f_scipy, psd_scipy = scipy_welch(
            signal - signal.mean(), fs=100.0, window="hann", nperseg=256, noverlap=128, detrend=False,
        )
        ratio = np.sum(result.amplitudes) / np.sum(psd_scipy)
        assert 0.8 < ratio < 1.2

    def test_phase_is_none(self, sine_5hz_100fs):
        result = compute_welch_psd(sine_5hz_100fs, "signal", reference_column="time_s")
        assert result.phase is None

    def test_segment_metadata_is_populated(self, sine_5hz_100fs):
        result = compute_welch_psd(
            sine_5hz_100fs,
            "signal",
            reference_column="time_s",
            segment_length=128,
            overlap_fraction=0.5,
        )
        assert result.segment_count is not None and result.segment_count > 0
        assert result.segment_length is not None and result.segment_length >= 4


# ── Transfer Estimate ────────────────────────────────────────────────


class TestTransferEstimate:
    def test_phase_is_computed(self, two_column_df):
        result = compute_transfer_estimate(
            two_column_df, "sensor_a", comparison_column="sensor_b", reference_column="time_s",
        )
        assert result.phase is not None
        assert result.phase.shape == result.amplitudes.shape

    def test_dominant_frequency(self, two_column_df):
        result = compute_transfer_estimate(
            two_column_df, "sensor_a", comparison_column="sensor_b", reference_column="time_s",
        )
        assert result.dominant_frequency > 0

    def test_nyquist_populated(self, two_column_df):
        result = compute_transfer_estimate(
            two_column_df, "sensor_a", comparison_column="sensor_b", reference_column="time_s",
        )
        assert result.nyquist_frequency > 0

    def test_segment_metadata_is_populated(self, two_column_df):
        result = compute_transfer_estimate(
            two_column_df,
            "sensor_a",
            comparison_column="sensor_b",
            reference_column="time_s",
            segment_length=128,
            overlap_fraction=0.5,
        )
        assert result.segment_count is not None and result.segment_count > 0
        assert result.segment_length is not None and result.segment_length >= 4

    def test_gain_and_phase_match_simple_scaled_signal(self):
        fs = 200.0
        t = np.arange(0, 5, 1 / fs)
        input_signal = np.sin(2 * np.pi * 5.0 * t)
        output_signal = 2.0 * input_signal
        df = pd.DataFrame({"time_s": t, "input": input_signal, "output": output_signal})

        result = compute_transfer_estimate(
            df,
            "output",
            comparison_column="input",
            reference_column="time_s",
            segment_length=256,
            overlap_fraction=0.5,
        )

        idx = np.argmin(np.abs(result.frequencies - 5.0))
        assert result.amplitudes[idx] == pytest.approx(20.0 * np.log10(2.0), abs=0.5)
        assert np.degrees(result.phase[idx]) == pytest.approx(0.0, abs=5.0)


# ── Coherence ────────────────────────────────────────────────────────


class TestCoherence:
    def test_coherence_between_0_and_1(self, two_column_df):
        result = compute_coherence_spectrum(
            two_column_df, "sensor_a", comparison_column="sensor_b", reference_column="time_s",
        )
        assert (result.amplitudes >= -0.01).all()
        assert (result.amplitudes <= 1.01).all()

    def test_phase_is_none(self, two_column_df):
        result = compute_coherence_spectrum(
            two_column_df, "sensor_a", comparison_column="sensor_b", reference_column="time_s",
        )
        assert result.phase is None

    def test_segment_metadata_is_populated(self, two_column_df):
        result = compute_coherence_spectrum(
            two_column_df,
            "sensor_a",
            comparison_column="sensor_b",
            reference_column="time_s",
            segment_length=128,
            overlap_fraction=0.5,
        )
        assert result.segment_count is not None and result.segment_count > 0
        assert result.segment_length is not None and result.segment_length >= 4

    def test_coherence_is_near_one_for_scaled_copy(self):
        fs = 200.0
        t = np.arange(0, 5, 1 / fs)
        input_signal = np.sin(2 * np.pi * 5.0 * t)
        output_signal = 2.0 * input_signal
        df = pd.DataFrame({"time_s": t, "input": input_signal, "output": output_signal})

        result = compute_coherence_spectrum(
            df,
            "output",
            comparison_column="input",
            reference_column="time_s",
            segment_length=256,
            overlap_fraction=0.5,
        )

        idx = np.argmin(np.abs(result.frequencies - 5.0))
        assert result.amplitudes[idx] == pytest.approx(1.0, abs=0.02)


# ── Spectrogram ──────────────────────────────────────────────────────


class TestSpectrogram:
    def test_shape_reasonable(self, sine_5hz_100fs):
        result = compute_spectrogram(sine_5hz_100fs, "signal", reference_column="time_s", segment_length=128)
        assert isinstance(result, SpectrogramResult)
        assert result.power.ndim == 2
        # power shape is (n_times, n_freqs)
        assert result.frequencies.shape[0] == result.power.shape[1]
        assert result.times.shape[0] == result.power.shape[0]

    def test_dominant_frequency_in_stft(self, sine_5hz_100fs):
        result = compute_spectrogram(sine_5hz_100fs, "signal", reference_column="time_s", segment_length=128)
        mean_power = result.power.mean(axis=1)
        peak_freq = result.frequencies[np.argmax(mean_power)]
        assert abs(peak_freq - 5.0) < 1.5
