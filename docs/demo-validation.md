# Demo Validation Guide

Use this document when you want a reproducible manual validation pass with the built-in demo datasets.

These checks are control cases, not proof that the application is generally correct. They are useful because the demo datasets are deterministic and have known intended behaviors.

## How To Use This Guide

1. Start the application from the repository root with `python EvalData.py`.
2. Load one demo dataset from `Files -> Load Demo/Test Signal`.
3. Select the dataset in the main window.
4. Open `Analysis -> Open Analysis Workspace` when the steps below call for analysis validation.
5. Compare the observed behavior against the expectations for that demo.

## Spectral Reference Signal

Use this demo to validate FFT, Welch PSD, filtering, and basic cycle segmentation.

### Main Channels

- `clean_signal`
- `measured_signal`
- `response_signal`
- `impact_marker`
- `structural_ringing`

### Recommended Checks

1. Load `Spectral Reference Signal`.
2. In the analysis workspace, select `clean_signal` as the active column.
3. Open `Frequency` and run `FFT Amplitude` with `X / reference = time_s`.
4. Confirm dominant peaks near `1.0 Hz`, `7.5 Hz`, and `18.0 Hz`.
5. Switch the active column to `measured_signal`.
6. Run `FFT Amplitude` again and confirm the same dominant peaks remain, with added low-frequency content near `0.15 Hz` and broader energy near `42 Hz`.
7. Switch to `Welch PSD` and confirm the same content remains visible in a smoother form.
8. Open `Cycles` and try `fixed_length` with `cycle_length = 250` as a first segmentation check.
9. Then try `rising_edge` with `Reference = impact_marker`, `Threshold = 0.5`, and minimum cycle length around `200`.

### What Should Stand Out

- `clean_signal` is the simplest known reference case.
- `measured_signal` adds drift, ringing, and noise to the same core frequencies.
- `impact_marker` provides a very explicit cycle reference.
- `structural_ringing` concentrates energy around `42 Hz`.

## Cycle Validation Drift Signal

Use this demo to validate cycle metrics, duration drift, representative-cycle behavior, and C2C plots.

### Main Channels

- `cycle_process`
- `trigger_pulse`
- `cycle_reference_zero`
- `true_cycle_duration_s`
- `baseline_drift`
- `amplitude_scale`

### Recommended Checks

1. Load `Cycle Validation Drift Signal`.
2. In the analysis workspace, use `cycle_process` as the active column.
3. In `Cycles`, choose `rising_edge`.
4. Set `Reference = trigger_pulse` and run cycle analysis.
5. Confirm the cycle-length or duration axis in the C2C plot trends upward over the dataset.
6. Confirm cycle mean trends upward with the built-in baseline drift.
7. Confirm `RMS` and `P2P` vary over time rather than staying flat.
8. Toggle `Min`, `Max`, and `Span` off in the `C2C Metrics` controls, then turn them back on and confirm the lower plot updates immediately.
9. Switch to `zero_crossing` with `Reference = cycle_reference_zero` and confirm the detected cycles remain sensible.

### What Should Stand Out

- cycle duration drifts upward overall
- cycle mean drifts upward overall
- amplitude variation causes visible movement in `RMS` and `P2P`
- both `trigger_pulse` and `cycle_reference_zero` act as clean cycle references

## Cycle Exclusion Stress Signal

Use this demo to validate exclude and restore workflows on clearly abnormal cycles.

### Main Channels

- `cycle_process`
- `trigger_pulse`
- `cycle_reference_zero`
- `is_outlier_cycle`
- `outlier_label`
- `true_cycle_duration_s`

### Built-In Outlier Types

- `low_amplitude`
- `short_cycle`
- `high_mean`
- `spike_outlier`

### Recommended Checks

1. Load `Cycle Exclusion Stress Signal`.
2. In the analysis workspace, use `cycle_process` as the active column.
3. In `Cycles`, choose `rising_edge` with `Reference = trigger_pulse`.
4. Run cycle analysis and inspect the metrics table.
5. Find the obvious outliers by looking for unusually low `P2P`, unusually short duration, unusually high mean, or unusually high `P2P` from a spike.
6. Exclude one or more of those cycles.
7. Confirm the representative-cycle band becomes tighter and the C2C plot becomes less erratic.
8. Restore one excluded cycle with `Restore Selected` and confirm the expected instability returns.
9. Use `Restore All` and confirm the full detected set returns.
10. Optionally switch to `zero_crossing` with `Reference = cycle_reference_zero` and confirm the anomalies are still visible in the metrics.

### What Should Stand Out

- one cycle has much lower amplitude than the stable population
- one cycle is visibly shorter than the stable population
- one cycle has a clearly elevated mean value
- one cycle has a clearly elevated `P2P` because of a built-in spike

## Input-Output Validation Signal

Use this demo to validate frequency comparisons, transfer-style checks, coherence-style checks, and derived-signal sanity.

### Main Channels

- `actuator_input`
- `delayed_input`
- `system_output`
- `resonance_component`

### Recommended Checks

1. Load `Input-Output Validation Signal`.
2. In the analysis workspace, run `FFT Amplitude` on `actuator_input` with `X / reference = time_s`.
3. Confirm peaks near `2.0 Hz`, `12.0 Hz`, and `28.0 Hz`.
4. Switch to `system_output` and confirm the same driven frequencies remain visible.
5. Confirm the `12.0 Hz` region is relatively emphasized and higher-frequency content is relatively attenuated.
6. If you are using transfer-style analysis, compare `system_output` against `actuator_input` or `delayed_input`.
7. If you are using coherence, confirm the strongest agreement is still near the driven frequencies.
8. Optionally inspect `output_residual` or `resonance_component` to confirm the synthetic resonance remains visible.

### What Should Stand Out

- the input contains known driven frequencies
- the output is delayed and filtered relative to the input
- the `12 Hz` region is intentionally emphasized by the synthetic resonance

## Fastest Useful Pass

If you want one compact validation sweep across the current demos:

1. On `Spectral Reference Signal`, verify FFT peaks on `clean_signal` and `measured_signal`.
2. On `Cycle Validation Drift Signal`, verify duration drift and mean drift in `Cycles`.
3. On `Cycle Exclusion Stress Signal`, exclude obvious outliers and confirm the plots stabilize.
4. On `Input-Output Validation Signal`, compare `actuator_input` and `system_output` in frequency analysis.

## Failure Signals

Treat the result as suspicious if any of these happen:

- expected dominant frequencies are missing entirely
- the duration trend is flat in the cycle drift demo
- the exclusion-stress demo does not show clearly abnormal cycles
- exclude and restore actions do not visibly affect the cycle plots
- the input-output demo does not preserve the known driven frequencies

For broader workflow guidance, see [quickstart.md](quickstart.md), [analysis-methods.md](analysis-methods.md), and [which-tool-when.md](which-tool-when.md).