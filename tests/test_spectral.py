"""Tests for data_ops.spectral – FFT, Welch PSD, Transfer Estimate, Coherence, Spectrogram."""

import numpy as np
import pandas as pd
import pytest
from scipy.signal import welch as scipy_welch

from Source.data_ops.spectral import (
    FrequencySpectrumResult,
    SpectrogramResult,
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

    def test_peaks_frame_has_rows(self, sine_5hz_100fs):
        result = compute_fft_spectrum(sine_5hz_100fs, "signal", reference_column="time_s", peak_count=5)
        assert len(result.peaks_frame) <= 5
        assert "frequency_hz" in result.peaks_frame.columns


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
