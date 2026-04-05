"""Tests for data_ops.cycles – fixed-length, rising-edge, zero-crossing, peak cycle detection."""

import numpy as np
import pandas as pd
import pytest

from data_ops.cycles import (
    compute_cycle_analysis_from_ranges,
    compute_fixed_length_cycle_analysis,
    detect_peak_cycle_ranges,
    detect_rising_edge_cycle_ranges,
    detect_zero_crossing_cycle_ranges,
)


# ── Fixed-length segmentation ────────────────────────────────────────


class TestFixedLengthCycles:
    def test_correct_cycle_count(self):
        df = pd.DataFrame({"sig": np.arange(100)})
        result = compute_fixed_length_cycle_analysis(df, "sig", cycle_length=10)
        assert result.cycle_count == 10

    def test_max_cycles_limit(self):
        df = pd.DataFrame({"sig": np.arange(100)})
        result = compute_fixed_length_cycle_analysis(df, "sig", cycle_length=10, max_cycles=3)
        assert result.cycle_count == 3

    def test_dropped_rows(self):
        df = pd.DataFrame({"sig": np.arange(95)})
        result = compute_fixed_length_cycle_analysis(df, "sig", cycle_length=10)
        assert result.cycle_count == 9
        assert result.dropped_rows >= 0

    def test_too_short_raises(self):
        df = pd.DataFrame({"sig": np.arange(5)})
        with pytest.raises(ValueError, match="Need at least"):
            compute_fixed_length_cycle_analysis(df, "sig", cycle_length=10)

    def test_metrics_frame_columns(self):
        df = pd.DataFrame({"sig": np.random.default_rng(0).standard_normal(200)})
        result = compute_fixed_length_cycle_analysis(df, "sig", cycle_length=20)
        for col in ("cycle", "start", "end", "length", "mean", "std", "min", "max", "rms", "peak_to_peak"):
            assert col in result.metrics_frame.columns

    def test_representative_frame_length(self):
        df = pd.DataFrame({"sig": np.arange(100)})
        result = compute_fixed_length_cycle_analysis(df, "sig", cycle_length=25)
        assert len(result.representative_frame) == 25


# ── Rising-edge detection ────────────────────────────────────────────


class TestRisingEdgeCycles:
    def test_detects_correct_count(self):
        # Create a triangular wave that crosses threshold=0.5 periodically
        t = np.linspace(0, 10, 1000)
        sig = np.abs(np.mod(t, 1.0) - 0.5) * 4 - 1  # oscillates between -1 and 1
        df = pd.DataFrame({"ref": sig})
        ranges = detect_rising_edge_cycle_ranges(df, "ref", threshold=0.5, min_cycle_length=10)
        assert len(ranges) >= 2

    def test_min_cycle_length_enforcement(self):
        sig = np.zeros(50)
        sig[10] = 1.0
        sig[12] = 1.0
        sig[40] = 1.0
        df = pd.DataFrame({"ref": sig})
        ranges = detect_rising_edge_cycle_ranges(df, "ref", threshold=0.5, min_cycle_length=5)
        for start, end in ranges:
            assert end - start >= 5

    def test_too_few_crossings_raises(self):
        df = pd.DataFrame({"ref": np.zeros(100)})
        with pytest.raises(ValueError, match="two rising-edge"):
            detect_rising_edge_cycle_ranges(df, "ref", threshold=0.5, min_cycle_length=2)


# ── Zero-crossing detection ──────────────────────────────────────────


class TestZeroCrossingCycles:
    def test_rising_crossings_of_sine(self):
        fs = 100.0
        t = np.arange(0, 5, 1 / fs)
        sig = np.sin(2 * np.pi * 2.0 * t)  # 2 Hz → 10 full cycles in 5 s
        df = pd.DataFrame({"sig": sig})
        ranges = detect_zero_crossing_cycle_ranges(df, "sig", direction="rising")
        assert 8 <= len(ranges) <= 10

    def test_falling_crossings(self):
        fs = 100.0
        t = np.arange(0, 5, 1 / fs)
        sig = np.sin(2 * np.pi * 2.0 * t)
        df = pd.DataFrame({"sig": sig})
        ranges = detect_zero_crossing_cycle_ranges(df, "sig", direction="falling")
        assert len(ranges) >= 5

    def test_any_direction_doubles_crossings(self):
        fs = 100.0
        t = np.arange(0, 5, 1 / fs)
        sig = np.sin(2 * np.pi * 2.0 * t)
        df = pd.DataFrame({"sig": sig})
        rising = detect_zero_crossing_cycle_ranges(df, "sig", direction="rising")
        any_dir = detect_zero_crossing_cycle_ranges(df, "sig", direction="any")
        assert len(any_dir) > len(rising)

    def test_no_crossings_raises(self):
        df = pd.DataFrame({"sig": np.ones(100)})
        with pytest.raises(ValueError, match="zero crossings"):
            detect_zero_crossing_cycle_ranges(df, "sig")


# ── Peak detection ───────────────────────────────────────────────────


class TestPeakCycles:
    def test_detects_peaks_of_sine(self):
        fs = 200.0
        t = np.arange(0, 5, 1 / fs)
        sig = np.sin(2 * np.pi * 2.0 * t)  # 2 Hz
        df = pd.DataFrame({"sig": sig})
        ranges = detect_peak_cycle_ranges(df, "sig", min_cycle_length=50)
        assert 7 <= len(ranges) <= 10

    def test_prominence_filter(self):
        rng = np.random.default_rng(7)
        fs = 200.0
        t = np.arange(0, 5, 1 / fs)
        sig = np.sin(2 * np.pi * 2.0 * t) + 0.1 * rng.standard_normal(len(t))
        df = pd.DataFrame({"sig": sig})
        ranges_no_prom = detect_peak_cycle_ranges(df, "sig", min_cycle_length=20)
        ranges_prom = detect_peak_cycle_ranges(df, "sig", min_cycle_length=20, prominence=0.5)
        assert len(ranges_prom) <= len(ranges_no_prom)

    def test_flat_signal_raises(self):
        df = pd.DataFrame({"sig": np.ones(100)})
        with pytest.raises(ValueError, match="two peaks"):
            detect_peak_cycle_ranges(df, "sig")


# ── Ranges → analysis pipeline ───────────────────────────────────────


class TestCycleAnalysisFromRanges:
    def test_roundtrip(self):
        rng = np.random.default_rng(0)
        df = pd.DataFrame({"sig": rng.standard_normal(300)})
        ranges = [(0, 100), (100, 200), (200, 300)]
        result = compute_cycle_analysis_from_ranges(df, "sig", ranges, method="manual", reference_column="Index")
        assert result.cycle_count == 3
        assert result.method == "manual"

    def test_empty_ranges_raises(self):
        df = pd.DataFrame({"sig": np.arange(50)})
        with pytest.raises(ValueError, match="No valid"):
            compute_cycle_analysis_from_ranges(df, "sig", [], method="test", reference_column="Index")
