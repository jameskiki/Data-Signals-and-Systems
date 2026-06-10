# Changelog

## [Unreleased]

### Changed
- Consolidated plotting presentation under a shared contract in `shared/plot_options.py` and `shared/plot_utils.py`.
- Unified Preview and Analysis time-series generic plotting behavior (labels/grid/legend/format defaults now come from shared contract fields).
- Applied shared axis presentation helpers to specialized Frequency and Cycle plots while preserving existing analytical layouts.
- Consolidated embedded Tk/matplotlib canvas lifecycle handling into `shared/base_app_shell.py` and adopted it in analysis and datapreparation preview rendering.
- Added debounced resize synchronization for the ad-hoc `Plot Data` detached window.
- Datapreparation row-range handling now supports datetime-like time columns consistently when using preview drag-select (`SpanSelector`) and manual range entry.
- Removed unused helper code and orphan scripts (`Scripts/bench_perf.py`, `Scripts/profile_view.py`, unreferenced listbox role-color helper).

### Added
- Direct unit coverage for embedded figure lifecycle helper create/reuse behavior in `tests/test_base_app_shell.py`.
- Focused datapreparation row-range regression coverage in `Tests/test_dataprep_row_range.py` (numeric and datetime range parsing, including Matplotlib span coordinates).

## [v0.3.0] - 2026-05-12

### Added
- Cycle review improvements with updated demo validation coverage

### Changed
- Adaptive analysis controls and analysis UI refinements
- Data merge and file-save handling improvements for preparation workflows
- Datetime parsing and dataset handling robustness improvements
- Performance and memory optimizations across dataframe operations

## [v0.2.0] - 2026-04-06

### Added
- Full data preparation and filtering workflow in the analysis workspace
- Simple filtering (min/max masking)
- Signal processing: moving average, median, exponential smoothing, high-pass, Butterworth lowpass/highpass/bandpass (zero-phase)
- Derived signals: delta, ratio, rolling mean, derivative, normalized, detrend (polynomial), integrate (cumulative trapezoid), RMS envelope, Hilbert envelope
- Frequency analysis: FFT Amplitude, Welch PSD, Transfer Estimate, Coherence, Spectrogram
- Cycle analysis: fixed-length, rising-edge, zero-crossing, and peak detection (with prominence)
- Resample to uniform time grid (interpolates all numeric columns)
- Engineering statistics and correlation matrices
- Demo datasets for reproducible walkthroughs
- 131 automated tests covering all data_ops modules
- All documentation (README, markdown, LaTeX) updated to match features

### Changed
- UI: All orphaned features now fully accessible from the analysis workspace
- Improved .gitignore, packaging, and build scripts

### Known Issues / Deferred
- Systems/controls analysis (Phase 2) is deferred to a future release
- No automated UI (Tkinter) tests yet; manual verification recommended

---

See previous commits for earlier history.
