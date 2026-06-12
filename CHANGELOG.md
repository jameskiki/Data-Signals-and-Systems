# Changelog

## [Unreleased]

## [v0.4.0] - 2026-06-12

### Added
- **Dynamic Options Refactor (Rules in Code)** — all analysis-method control rules moved to
  `Source/analysis_app/rules.py` (pure Python, no Tk) and applied via
  `Source/analysis_app/rules_orchestrator.py`:
  - 16 rule IDs across Frequency (5), Signal Filter (7), and Cycle (4) domains.
  - `get_rule` / `validate_params` pure helpers for programmatic lookup and preflight checks.
  - Frame show/hide, widget enable/disable, and stale-value correction driven by rules.
- **Preflight validation gates** in `handlers.py` for `compute_fft`, `apply_signal_filter`,
  and `compute_cycle_analysis` — invalid or missing required params are caught with a clear
  warning before any computation runs.
- **Bandpass high-cutoff field** — `butterworth_bandpass` now exposes a separate
  *High cutoff freq [Hz]* entry (hidden for LP/HP); low > high ordering is validated.
- **Data-inferred defaults** — on every control refresh the workspace auto-fills these fields
  from the time-role column and active signal when the user has not yet set a value:
  - Signal filter sample spacing
  - FFT index step size
  - Resample target spacing (when a real time column is selected)
  - Welch segment length (nearest power-of-two ≤ sample count, capped at 256)
  - Fixed-cycle length (dominant spectral period of the active signal)
- **Inferred / User-set badges** — five spacing/length fields display a blue *Inferred* or
  *User-set* label that updates live; flips to *User-set* the moment the user edits a field.
  Implemented via `_inferred_fields` tracker, `_set_inferred_field_value`, and
  `_refresh_inferred_badges` in `AnalysisWorkspace`.
- Signal Filter tab restructured into three named frames
  (`signal_filter_window_frame`, `signal_filter_alpha_frame`, `signal_filter_butterworth_frame`)
  so the orchestrator can show/hide the right subset of controls per operation.
- 66 new automated tests covering rules, handler preflight gates, bandpass plumbing,
  spacing inference, badge tracking, and analysis-length inference.

### Changed
- `_refresh_frequency_method_controls` and `_refresh_cycle_method_controls` in
  `AnalysisWorkspace` replaced by single-line orchestrator calls; new
  `_refresh_signal_filter_controls` wired for Signal Filter operation changes.
- `butterworth_bandpass` `cutoff_hz` parameter now accepts `float | list[float]` throughout
  `signals.py`, `actions.py`, and `handlers.py`.
- Parameter requirement tables in `docs/analysis-methods.md` updated to reflect rule definitions.

- Consolidated plotting presentation under a shared contract in `shared/plot_options.py` and `shared/plot_utils.py`.
- Unified Preview and Analysis time-series generic plotting behavior (labels/grid/legend/format defaults now come from shared contract fields).
- Applied shared axis presentation helpers to specialized Frequency and Cycle plots while preserving existing analytical layouts.
- Consolidated embedded Tk/matplotlib canvas lifecycle handling into `shared/base_app_shell.py` and adopted it in analysis and datapreparation preview rendering.
- Added debounced resize synchronization for the ad-hoc `Plot Data` detached window.
- Datapreparation row-range handling now supports datetime-like time columns consistently when using preview drag-select (`SpanSelector`) and manual range entry.
- Removed unused helper code and orphan scripts (`scripts/bench_perf.py`, `scripts/profile_view.py`, unreferenced listbox role-color helper).

### Added
- Direct unit coverage for embedded figure lifecycle helper create/reuse behavior in `tests/test_base_app_shell.py`.
- Focused datapreparation row-range regression coverage in `tests/test_dataprep_row_range.py` (numeric and datetime range parsing, including Matplotlib span coordinates).

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
