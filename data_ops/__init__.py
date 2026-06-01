"""Public data operation API."""

from .cycles import (
    CycleAnalysisResult,
    compute_cycle_analysis_from_ranges,
    compute_fixed_length_cycle_analysis,
    detect_peak_cycle_ranges,
    detect_rising_edge_cycle_ranges,
    rebuild_cycle_analysis_result,
    detect_zero_crossing_cycle_ranges,
)
from .filtering import apply_simple_filter, resolve_filtered_column_name, subset_dataframe_rows
from .frame_ops import (
    drop_dataframe_columns,
    drop_dataframe_index_range,
    keep_dataframe_index_ranges,
    normalize_index_range,
    resample_to_uniform,
    select_dataframe_columns,
    slice_dataframe_by_index_range,
    split_dataframe_by_index_ranges,
)
from .io_ops import analyze_selected_dataframes, export_clean_dataframes, merge_selected_dataframes
from .models import DataFrameMap, DataSummary, SIGNAL_FILTER_OPERATIONS
from .signals import add_derived_column, apply_signal_filter
from .spectral import (
    FFT_WINDOW_OPTIONS,
    FREQUENCY_ANALYSIS_METHODS,
    FrequencySpectrumResult,
    SpectrogramResult,
    compute_coherence_spectrum,
    compute_fft_spectrum,
    compute_spectrogram,
    compute_transfer_estimate,
    compute_welch_psd,
)
from .summary import build_correlation_frame, build_statistics_frame, summarize_dataframe

__all__ = [
    "CycleAnalysisResult",
    "DataFrameMap",
    "DataSummary",
    "FFT_WINDOW_OPTIONS",
    "FREQUENCY_ANALYSIS_METHODS",
    "FrequencySpectrumResult",
    "SpectrogramResult",
    "SIGNAL_FILTER_OPERATIONS",
    "add_derived_column",
    "analyze_selected_dataframes",
    "apply_signal_filter",
    "apply_simple_filter",
    "build_correlation_frame",
    "build_statistics_frame",
    "compute_coherence_spectrum",
    "compute_cycle_analysis_from_ranges",
    "compute_fft_spectrum",
    "compute_fixed_length_cycle_analysis",
    "compute_spectrogram",
    "compute_transfer_estimate",
    "compute_welch_psd",
    "detect_peak_cycle_ranges",
    "detect_rising_edge_cycle_ranges",
    "rebuild_cycle_analysis_result",
    "detect_zero_crossing_cycle_ranges",
    "drop_dataframe_columns",
    "drop_dataframe_index_range",
    "export_clean_dataframes",
    "keep_dataframe_index_ranges",
    "merge_selected_dataframes",
    "normalize_index_range",
    "resample_to_uniform",
    "resolve_filtered_column_name",
    "select_dataframe_columns",
    "slice_dataframe_by_index_range",
    "split_dataframe_by_index_ranges",
    "subset_dataframe_rows",
    "summarize_dataframe",
]
