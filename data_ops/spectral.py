"""Frequency-domain analysis helpers."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


FFT_WINDOW_OPTIONS = ["hann", "hamming", "blackman", "rectangular"]
FREQUENCY_ANALYSIS_METHODS = ["FFT Amplitude", "Welch PSD", "Transfer Estimate", "Coherence"]


@dataclass(frozen=True)
class FrequencySpectrumResult:
    """Computed one-sided amplitude spectrum for a signal."""

    analysis_name: str
    source_column: str
    comparison_column: str | None
    reference_column: str | None
    sample_count: int
    sample_spacing: float
    sampling_frequency: float
    nyquist_frequency: float
    dominant_frequency: float
    dominant_amplitude: float
    window: str
    detrended: bool
    spacing_source_text: str
    uniformity_ratio: float
    frequencies: np.ndarray
    amplitudes: np.ndarray
    phase: np.ndarray | None
    peaks_frame: pd.DataFrame
    y_axis_label: str
    plot_title: str
    value_column_label: str


def compute_fft_spectrum(
    dataframe: pd.DataFrame,
    source_column: str,
    reference_column: str | None = None,
    sample_spacing: float = 1.0,
    window: str = "hann",
    detrend: bool = True,
    peak_count: int = 10,
) -> FrequencySpectrumResult:
    """Compute a one-sided amplitude spectrum for one signal column."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")

    signal_series = pd.to_numeric(dataframe[source_column], errors="coerce")
    if reference_column is None:
        valid_mask = signal_series.notna()
        resolved_sample_spacing = float(sample_spacing)
        spacing_source_text = "Fixed spacing"
        uniformity_ratio = 0.0
    else:
        if reference_column not in dataframe.columns:
            raise KeyError(f"Unknown reference column: {reference_column}")
        reference_values = _coerce_reference_axis(dataframe[reference_column])
        valid_mask = signal_series.notna() & reference_values.notna()
        resolved_sample_spacing, uniformity_ratio = _estimate_sample_spacing(reference_values.loc[valid_mask])
        spacing_source_text = f"Median spacing from {reference_column}"

    if resolved_sample_spacing <= 0:
        raise ValueError("Sample spacing must be greater than zero")

    values = signal_series.loc[valid_mask].to_numpy(dtype=float, copy=False)
    if values.size < 2:
        raise ValueError("At least two valid samples are required for FFT analysis")

    working_values = values - values.mean() if detrend else values.copy()
    window_values = _build_window(window, working_values.size)
    coherent_gain = float(window_values.mean())
    if coherent_gain == 0:
        raise ValueError("Invalid FFT window configuration")

    spectrum = np.fft.rfft(working_values * window_values)
    frequencies = np.fft.rfftfreq(working_values.size, d=resolved_sample_spacing)
    amplitudes = (2.0 / (working_values.size * coherent_gain)) * np.abs(spectrum)
    if amplitudes.size > 0:
        amplitudes[0] /= 2.0
    if working_values.size % 2 == 0 and amplitudes.size > 1:
        amplitudes[-1] /= 2.0

    dominant_index = _get_dominant_frequency_index(amplitudes)
    peaks_frame = _build_peak_frame(frequencies, amplitudes, peak_count)

    return FrequencySpectrumResult(
        analysis_name="FFT Amplitude",
        source_column=source_column,
        comparison_column=None,
        reference_column=reference_column,
        sample_count=int(working_values.size),
        sample_spacing=float(resolved_sample_spacing),
        sampling_frequency=float(1.0 / resolved_sample_spacing),
        nyquist_frequency=float(0.5 / resolved_sample_spacing),
        dominant_frequency=float(frequencies[dominant_index]),
        dominant_amplitude=float(amplitudes[dominant_index]),
        window=window,
        detrended=detrend,
        spacing_source_text=spacing_source_text,
        uniformity_ratio=float(uniformity_ratio),
        frequencies=frequencies,
        amplitudes=amplitudes,
        phase=None,
        peaks_frame=peaks_frame,
        y_axis_label="Amplitude",
        plot_title=f"FFT of {source_column}",
        value_column_label="Amp",
    )


def compute_welch_psd(
    dataframe: pd.DataFrame,
    source_column: str,
    reference_column: str | None = None,
    sample_spacing: float = 1.0,
    window: str = "hann",
    detrend: bool = True,
    segment_length: int = 256,
    overlap_fraction: float = 0.5,
    peak_count: int = 10,
) -> FrequencySpectrumResult:
    """Compute a Welch-style power spectral density estimate."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")

    signal_series = pd.to_numeric(dataframe[source_column], errors="coerce")
    if reference_column is None:
        valid_mask = signal_series.notna()
        resolved_sample_spacing = float(sample_spacing)
        spacing_source_text = "Fixed spacing"
        uniformity_ratio = 0.0
    else:
        if reference_column not in dataframe.columns:
            raise KeyError(f"Unknown reference column: {reference_column}")
        reference_values = _coerce_reference_axis(dataframe[reference_column])
        valid_mask = signal_series.notna() & reference_values.notna()
        resolved_sample_spacing, uniformity_ratio = _estimate_sample_spacing(reference_values.loc[valid_mask])
        spacing_source_text = f"Median spacing from {reference_column}"

    if resolved_sample_spacing <= 0:
        raise ValueError("Sample spacing must be greater than zero")

    values = signal_series.loc[valid_mask].to_numpy(dtype=float, copy=False)
    if values.size < 4:
        raise ValueError("At least four valid samples are required for Welch PSD analysis")

    normalized_overlap_fraction = float(overlap_fraction)
    if not 0 <= normalized_overlap_fraction < 1:
        raise ValueError("Welch overlap fraction must be between 0 and 1")

    normalized_segment_length = max(4, min(int(segment_length), values.size))
    if normalized_segment_length % 2 == 1:
        normalized_segment_length -= 1
    if normalized_segment_length < 4:
        raise ValueError("Welch segment length must be at least 4")

    step = max(1, int(round(normalized_segment_length * (1.0 - normalized_overlap_fraction))))
    window_values = _build_window(window, normalized_segment_length)
    window_power = float(np.sum(window_values * window_values))
    if window_power == 0:
        raise ValueError("Invalid Welch window configuration")

    working_values = values - values.mean() if detrend else values.copy()
    segment_starts = list(range(0, values.size - normalized_segment_length + 1, step))
    if not segment_starts:
        segment_starts = [0]

    n_freqs = normalized_segment_length // 2 + 1
    segment_spectra = np.empty((len(segment_starts), n_freqs))
    valid_count = 0
    for start in segment_starts:
        segment = working_values[start : start + normalized_segment_length]
        if segment.size != normalized_segment_length:
            continue
        fft_values = np.fft.rfft(segment * window_values)
        power_density = np.abs(fft_values) ** 2 / (window_power / resolved_sample_spacing)
        if power_density.size > 2:
            power_density[1:-1] *= 2.0
        segment_spectra[valid_count] = power_density
        valid_count += 1

    if valid_count == 0:
        raise ValueError("Unable to build Welch segments from the selected data")

    frequencies = np.fft.rfftfreq(normalized_segment_length, d=resolved_sample_spacing)
    amplitudes = np.mean(segment_spectra[:valid_count], axis=0)
    dominant_index = _get_dominant_frequency_index(amplitudes)
    peaks_frame = _build_peak_frame(frequencies, amplitudes, peak_count)

    sampling_freq = float(1.0 / resolved_sample_spacing)

    return FrequencySpectrumResult(
        analysis_name="Welch PSD",
        source_column=source_column,
        comparison_column=None,
        reference_column=reference_column,
        sample_count=int(values.size),
        sample_spacing=float(resolved_sample_spacing),
        sampling_frequency=sampling_freq,
        nyquist_frequency=float(0.5 * sampling_freq),
        dominant_frequency=float(frequencies[dominant_index]),
        dominant_amplitude=float(amplitudes[dominant_index]),
        window=window,
        detrended=detrend,
        spacing_source_text=spacing_source_text,
        uniformity_ratio=float(uniformity_ratio),
        frequencies=frequencies,
        amplitudes=amplitudes,
        phase=None,
        peaks_frame=peaks_frame,
        y_axis_label="PSD",
        plot_title=f"Welch PSD of {source_column}",
        value_column_label="PSD",
    )


def compute_transfer_estimate(
    dataframe: pd.DataFrame,
    source_column: str,
    comparison_column: str,
    reference_column: str | None = None,
    sample_spacing: float = 1.0,
    window: str = "hann",
    detrend: bool = True,
    segment_length: int = 256,
    overlap_fraction: float = 0.5,
    peak_count: int = 10,
) -> FrequencySpectrumResult:
    """Estimate a transfer magnitude from comparison/input to source/output."""

    prepared = _prepare_dual_signal_spectra(
        dataframe=dataframe,
        source_column=source_column,
        comparison_column=comparison_column,
        reference_column=reference_column,
        sample_spacing=sample_spacing,
        window=window,
        detrend=detrend,
        segment_length=segment_length,
        overlap_fraction=overlap_fraction,
    )
    denominator = np.maximum(np.abs(prepared["auto_input"]), 1e-12)
    transfer_values = prepared["cross_spectrum"] / denominator
    amplitudes = np.abs(transfer_values)
    phase = np.angle(transfer_values)
    dominant_index = _get_dominant_frequency_index(amplitudes)
    peaks_frame = _build_peak_frame(prepared["frequencies"], amplitudes, peak_count)

    return FrequencySpectrumResult(
        analysis_name="Transfer Estimate",
        source_column=source_column,
        comparison_column=comparison_column,
        reference_column=reference_column,
        sample_count=int(prepared["sample_count"]),
        sample_spacing=float(prepared["sample_spacing"]),
        sampling_frequency=float(prepared["sampling_frequency"]),
        nyquist_frequency=float(0.5 * prepared["sampling_frequency"]),
        dominant_frequency=float(prepared["frequencies"][dominant_index]),
        dominant_amplitude=float(amplitudes[dominant_index]),
        window=window,
        detrended=detrend,
        spacing_source_text=str(prepared["spacing_source_text"]),
        uniformity_ratio=float(prepared["uniformity_ratio"]),
        frequencies=prepared["frequencies"],
        amplitudes=amplitudes,
        phase=phase,
        peaks_frame=peaks_frame,
        y_axis_label="|H(f)|",
        plot_title=f"Transfer Estimate: {comparison_column} -> {source_column}",
        value_column_label="|H|",
    )


def compute_coherence_spectrum(
    dataframe: pd.DataFrame,
    source_column: str,
    comparison_column: str,
    reference_column: str | None = None,
    sample_spacing: float = 1.0,
    window: str = "hann",
    detrend: bool = True,
    segment_length: int = 256,
    overlap_fraction: float = 0.5,
    peak_count: int = 10,
) -> FrequencySpectrumResult:
    """Compute magnitude-squared coherence between comparison/input and source/output."""

    prepared = _prepare_dual_signal_spectra(
        dataframe=dataframe,
        source_column=source_column,
        comparison_column=comparison_column,
        reference_column=reference_column,
        sample_spacing=sample_spacing,
        window=window,
        detrend=detrend,
        segment_length=segment_length,
        overlap_fraction=overlap_fraction,
    )
    denominator = np.maximum(np.real(prepared["auto_input"] * prepared["auto_output"]), 1e-12)
    amplitudes = np.clip((np.abs(prepared["cross_spectrum"]) ** 2) / denominator, 0.0, 1.0)
    dominant_index = _get_dominant_frequency_index(amplitudes)
    peaks_frame = _build_peak_frame(prepared["frequencies"], amplitudes, peak_count)

    return FrequencySpectrumResult(
        analysis_name="Coherence",
        source_column=source_column,
        comparison_column=comparison_column,
        reference_column=reference_column,
        sample_count=int(prepared["sample_count"]),
        sample_spacing=float(prepared["sample_spacing"]),
        sampling_frequency=float(prepared["sampling_frequency"]),
        nyquist_frequency=float(0.5 * prepared["sampling_frequency"]),
        dominant_frequency=float(prepared["frequencies"][dominant_index]),
        dominant_amplitude=float(amplitudes[dominant_index]),
        window=window,
        detrended=detrend,
        spacing_source_text=str(prepared["spacing_source_text"]),
        uniformity_ratio=float(prepared["uniformity_ratio"]),
        frequencies=prepared["frequencies"],
        amplitudes=amplitudes,
        phase=None,
        peaks_frame=peaks_frame,
        y_axis_label="Coherence",
        plot_title=f"Coherence: {comparison_column} -> {source_column}",
        value_column_label="Coh",
    )


@dataclass(frozen=True)
class SpectrogramResult:
    """Time-frequency representation of a signal via short-time FFT."""

    source_column: str
    reference_column: str | None
    sample_spacing: float
    sampling_frequency: float
    segment_length: int
    overlap_fraction: float
    window: str
    times: np.ndarray
    frequencies: np.ndarray
    power: np.ndarray


def compute_spectrogram(
    dataframe: pd.DataFrame,
    source_column: str,
    reference_column: str | None = None,
    sample_spacing: float = 1.0,
    window: str = "hann",
    detrend: bool = True,
    segment_length: int = 256,
    overlap_fraction: float = 0.5,
) -> SpectrogramResult:
    """Compute a short-time Fourier transform spectrogram for one signal column."""

    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")

    signal_series = pd.to_numeric(dataframe[source_column], errors="coerce")
    if reference_column is None:
        valid_mask = signal_series.notna()
        resolved_sample_spacing = float(sample_spacing)
    else:
        if reference_column not in dataframe.columns:
            raise KeyError(f"Unknown reference column: {reference_column}")
        reference_values = _coerce_reference_axis(dataframe[reference_column])
        valid_mask = signal_series.notna() & reference_values.notna()
        resolved_sample_spacing, _ = _estimate_sample_spacing(reference_values.loc[valid_mask])

    if resolved_sample_spacing <= 0:
        raise ValueError("Sample spacing must be greater than zero")

    values = signal_series.loc[valid_mask].to_numpy(dtype=float, copy=False)
    if values.size < 4:
        raise ValueError("At least four valid samples are required for spectrogram analysis")

    normalized_segment_length = max(4, min(int(segment_length), values.size))
    if normalized_segment_length % 2 == 1:
        normalized_segment_length -= 1

    normalized_overlap_fraction = float(overlap_fraction)
    step = max(1, int(round(normalized_segment_length * (1.0 - normalized_overlap_fraction))))
    window_values = _build_window(window, normalized_segment_length)
    window_power = float(np.sum(window_values * window_values))
    if window_power == 0:
        raise ValueError("Invalid window configuration")

    working_values = values - values.mean() if detrend else values.copy()

    segment_starts = list(range(0, values.size - normalized_segment_length + 1, step))
    if not segment_starts:
        raise ValueError("Unable to build spectrogram segments from the selected data")

    n_freqs = normalized_segment_length // 2 + 1
    power = np.empty((len(segment_starts), n_freqs))
    times = np.empty(len(segment_starts))
    valid_count = 0
    for start in segment_starts:
        segment = working_values[start : start + normalized_segment_length]
        if segment.size != normalized_segment_length:
            continue
        fft_values = np.fft.rfft(segment * window_values)
        power_density = np.abs(fft_values) ** 2 / (window_power / resolved_sample_spacing)
        if power_density.size > 2:
            power_density[1:-1] *= 2.0
        power[valid_count] = power_density
        times[valid_count] = (start + normalized_segment_length // 2) * resolved_sample_spacing
        valid_count += 1

    frequencies = np.fft.rfftfreq(normalized_segment_length, d=resolved_sample_spacing)
    power = power[:valid_count]  # shape: (n_times, n_freqs)
    times = times[:valid_count]
    fs = 1.0 / resolved_sample_spacing

    return SpectrogramResult(
        source_column=source_column,
        reference_column=reference_column,
        sample_spacing=float(resolved_sample_spacing),
        sampling_frequency=float(fs),
        segment_length=normalized_segment_length,
        overlap_fraction=normalized_overlap_fraction,
        window=window,
        times=np.array(times),
        frequencies=frequencies,
        power=power,
    )


def _coerce_reference_axis(reference_series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(reference_series):
        timestamps = pd.to_datetime(reference_series, errors="coerce")
        return pd.Series(timestamps.astype("int64") / 1_000_000_000, index=reference_series.index)
    return pd.to_numeric(reference_series, errors="coerce")


def _estimate_sample_spacing(reference_values: pd.Series) -> tuple[float, float]:
    numeric_values = reference_values.to_numpy(dtype=float, copy=False)
    diffs = np.diff(numeric_values)
    finite_diffs = diffs[np.isfinite(diffs)]
    positive_diffs = finite_diffs[finite_diffs > 0]
    if positive_diffs.size == 0:
        raise ValueError("Reference column must contain increasing values for FFT analysis")

    sample_spacing = float(np.median(positive_diffs))
    uniformity_ratio = float(np.max(np.abs(positive_diffs - sample_spacing)) / sample_spacing) if sample_spacing else 0.0
    return sample_spacing, uniformity_ratio


def _build_window(window: str, size: int) -> np.ndarray:
    normalized_window = window.strip().lower()
    if normalized_window == "hann":
        return np.hanning(size)
    if normalized_window == "hamming":
        return np.hamming(size)
    if normalized_window == "blackman":
        return np.blackman(size)
    if normalized_window == "rectangular":
        return np.ones(size)
    raise ValueError(f"Unsupported FFT window: {window}")


def _get_dominant_frequency_index(amplitudes: np.ndarray) -> int:
    if amplitudes.size <= 1:
        return 0
    return int(np.argmax(amplitudes[1:])) + 1


def _build_peak_frame(frequencies: np.ndarray, amplitudes: np.ndarray, peak_count: int) -> pd.DataFrame:
    if amplitudes.size <= 1:
        return pd.DataFrame(columns=["rank", "frequency_hz", "amplitude"])

    sorted_indices = np.argsort(amplitudes[1:])[::-1][: max(1, int(peak_count))] + 1
    peak_rows = [
        {
            "rank": rank,
            "frequency_hz": float(frequencies[index]),
            "amplitude": float(amplitudes[index]),
        }
        for rank, index in enumerate(sorted_indices, start=1)
    ]
    return pd.DataFrame(peak_rows)


def _prepare_dual_signal_spectra(
    dataframe: pd.DataFrame,
    source_column: str,
    comparison_column: str,
    reference_column: str | None,
    sample_spacing: float,
    window: str,
    detrend: bool,
    segment_length: int,
    overlap_fraction: float,
) -> dict[str, object]:
    if source_column not in dataframe.columns:
        raise KeyError(f"Unknown source column: {source_column}")
    if comparison_column not in dataframe.columns:
        raise KeyError(f"Unknown comparison column: {comparison_column}")
    if source_column == comparison_column:
        raise ValueError("Choose different source and comparison columns for input-output analysis")

    source_series = pd.to_numeric(dataframe[source_column], errors="coerce")
    comparison_series = pd.to_numeric(dataframe[comparison_column], errors="coerce")
    if reference_column is None:
        valid_mask = source_series.notna() & comparison_series.notna()
        resolved_sample_spacing = float(sample_spacing)
        spacing_source_text = "Fixed spacing"
        uniformity_ratio = 0.0
    else:
        if reference_column not in dataframe.columns:
            raise KeyError(f"Unknown reference column: {reference_column}")
        reference_values = _coerce_reference_axis(dataframe[reference_column])
        valid_mask = source_series.notna() & comparison_series.notna() & reference_values.notna()
        resolved_sample_spacing, uniformity_ratio = _estimate_sample_spacing(reference_values.loc[valid_mask])
        spacing_source_text = f"Median spacing from {reference_column}"

    if resolved_sample_spacing <= 0:
        raise ValueError("Sample spacing must be greater than zero")

    output_values = source_series.loc[valid_mask].to_numpy(dtype=float, copy=False)
    input_values = comparison_series.loc[valid_mask].to_numpy(dtype=float, copy=False)
    if output_values.size < 4:
        raise ValueError("At least four aligned valid samples are required for input-output spectral analysis")

    normalized_overlap_fraction = float(overlap_fraction)
    if not 0 <= normalized_overlap_fraction < 1:
        raise ValueError("Welch overlap fraction must be between 0 and 1")

    normalized_segment_length = max(4, min(int(segment_length), output_values.size))
    if normalized_segment_length % 2 == 1:
        normalized_segment_length -= 1
    if normalized_segment_length < 4:
        raise ValueError("Welch segment length must be at least 4")

    step = max(1, int(round(normalized_segment_length * (1.0 - normalized_overlap_fraction))))
    window_values = _build_window(window, normalized_segment_length)
    if not np.any(window_values):
        raise ValueError("Invalid Welch window configuration")

    working_output = output_values - output_values.mean() if detrend else output_values.copy()
    working_input = input_values - input_values.mean() if detrend else input_values.copy()

    n_freqs = normalized_segment_length // 2 + 1
    cross_sum = np.zeros(n_freqs, dtype=complex)
    auto_input_sum = np.zeros(n_freqs, dtype=float)
    auto_output_sum = np.zeros(n_freqs, dtype=float)
    segment_count = 0
    for start in range(0, output_values.size - normalized_segment_length + 1, step):
        output_segment = working_output[start : start + normalized_segment_length]
        input_segment = working_input[start : start + normalized_segment_length]
        if output_segment.size != normalized_segment_length or input_segment.size != normalized_segment_length:
            continue
        output_fft = np.fft.rfft(output_segment * window_values)
        input_fft = np.fft.rfft(input_segment * window_values)
        cross_sum += output_fft * np.conjugate(input_fft)
        auto_input_sum += np.real(input_fft * np.conjugate(input_fft))
        auto_output_sum += np.real(output_fft * np.conjugate(output_fft))
        segment_count += 1

    if segment_count == 0:
        raise ValueError("Unable to build Welch segments from the selected data")

    frequencies = np.fft.rfftfreq(normalized_segment_length, d=resolved_sample_spacing)
    return {
        "sample_count": int(output_values.size),
        "sample_spacing": float(resolved_sample_spacing),
        "sampling_frequency": float(1.0 / resolved_sample_spacing),
        "spacing_source_text": spacing_source_text,
        "uniformity_ratio": float(uniformity_ratio),
        "frequencies": frequencies,
        "cross_spectrum": cross_sum / segment_count,
        "auto_input": auto_input_sum / segment_count,
        "auto_output": auto_output_sum / segment_count,
    }
