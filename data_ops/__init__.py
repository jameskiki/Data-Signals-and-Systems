"""Public data operation API."""

from .filtering import apply_simple_filter, resolve_filtered_column_name, subset_dataframe_rows
from .frame_ops import (
    drop_dataframe_columns,
    drop_dataframe_index_range,
    normalize_index_range,
    select_dataframe_columns,
    slice_dataframe_by_index_range,
    split_dataframe_by_index_ranges,
)
from .io_ops import analyze_selected_dataframes, export_clean_dataframes, merge_selected_dataframes
from .models import AnalysisResult, DataFrameMap, DataSummary, SIGNAL_FILTER_OPERATIONS
from .signals import add_derived_column, apply_signal_filter
from .spectral import (
    FFT_WINDOW_OPTIONS,
    FREQUENCY_ANALYSIS_METHODS,
    FrequencySpectrumResult,
    compute_coherence_spectrum,
    compute_fft_spectrum,
    compute_transfer_estimate,
    compute_welch_psd,
)
from .summary import build_correlation_frame, build_statistics_frame, summarize_dataframe

__all__ = [
    "AnalysisResult",
    "DataFrameMap",
    "DataSummary",
    "FFT_WINDOW_OPTIONS",
    "FREQUENCY_ANALYSIS_METHODS",
    "FrequencySpectrumResult",
    "SIGNAL_FILTER_OPERATIONS",
    "add_derived_column",
    "analyze_selected_dataframes",
    "apply_signal_filter",
    "apply_simple_filter",
    "build_correlation_frame",
    "build_statistics_frame",
    "compute_coherence_spectrum",
    "compute_fft_spectrum",
    "compute_transfer_estimate",
    "compute_welch_psd",
    "drop_dataframe_columns",
    "drop_dataframe_index_range",
    "export_clean_dataframes",
    "merge_selected_dataframes",
    "normalize_index_range",
    "resolve_filtered_column_name",
    "select_dataframe_columns",
    "slice_dataframe_by_index_range",
    "split_dataframe_by_index_ranges",
    "subset_dataframe_rows",
    "summarize_dataframe",
]
