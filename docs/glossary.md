# Glossary

Use this page as a short lookup. The fuller explanations live in [user-guide.md](user-guide.md).

## Key Terms

- `Prepared dataset`: a new in-app dataset created from one selected source dataset, currently by copying the full dataframe and optionally keeping only selected columns.
- `Column role`: a semantic label such as `time`, `input`, `output`, `signal`, or `metadata`.
- `Overview plot`: the inspection plot in the main window; it does not trim rows for prepared dataset creation.
- `Active analysis column`: the main column currently targeted by analysis actions in the analysis workspace.
- `Welch PSD`: a smoother spectral estimate based on overlapping windows. For the current formal note, see [docs/latex/fft_welch_example.pdf](latex/fft_welch_example.pdf).
- `Transfer Estimate`: frequency response estimate $H_1(f) = S_{xy}/S_{xx}$ from a comparison (input) signal to the active (output) signal, including magnitude and phase.
- `Coherence`: magnitude-squared coherence $\gamma^2(f)$ measuring the linear relationship strength between two signals at each frequency, ranging from 0 to 1.
- `Spectrogram`: a time-frequency representation produced by short-time FFT, showing how spectral content evolves over time as a heatmap.
- `Butterworth filter`: a maximally-flat magnitude-response IIR filter. EvalData uses zero-phase `sosfiltfilt` (forward-backward filtering) for lowpass, highpass, and bandpass variants.
- `Prominence`: a peak-detection parameter from `scipy.signal.find_peaks` that measures how much a peak stands out relative to its surroundings; used in the `peak` cycle-detection mode to ignore minor peaks.
- `Zero-crossing`: a point where a signal changes sign; the `zero_crossing` cycle-detection mode uses these points as cycle boundaries with configurable direction (rising, falling, or both).
- `Hilbert envelope`: the amplitude envelope of a signal computed via the analytic signal (Hilbert transform). Useful for extracting the modulation envelope of narrowband or oscillatory signals.
- `RMS envelope`: a rolling root-mean-square value computed over a centered window, tracking the instantaneous energy of a signal.
- `Detrend`: removal of a polynomial trend (order 1–3) from a signal by least-squares fit and subtraction.
- `Resample to uniform grid`: interpolation of all numeric columns onto evenly spaced time points, using `resample_to_uniform` from `data_ops/frame_ops.py`.
