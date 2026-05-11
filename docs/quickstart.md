# Quickstart

Use this if you want one short end-to-end run before loading your own data.

## Example Run

The most reliable first run is the built-in spectral demo because the expected dominant frequencies are known in advance.

1. Start the application from the repository root with `python EvalData.py`.
2. Open `Files -> Load Demo/Test Signal -> Spectral Reference Signal -> Load This Demo`.
3. Select the newly loaded dataset in the dataset list.
4. In `Selected Dataset`, confirm the dataset summary looks reasonable.
5. In the right-side `Preview` area, open the `Table (200 rows)` tab and confirm the table contains columns such as `time_s`, `clean_signal`, and `measured_signal`.
6. In the left preparation controls, scroll to the `Roles` section and check that `time_s` is treated as `time` and `measured_signal` or `clean_signal` is available as a signal/output column.
7. In the same preparation area, optionally enter a clearer dataset name such as `spectral_demo_prepared`, then click `Create Dataset`.
8. Select the new prepared dataset and open `Analysis -> Open Analysis Workspace`.
9. In the analysis workspace sidebar, choose `measured_signal` or `clean_signal` as the active column.
10. Open the `Frequency` tab.
11. Leave `Method` on `FFT Amplitude`, set `X / reference` to `time_s`, and click `Analyze Spectrum`.
12. Confirm that the dominant peaks are near 1.0 Hz, 7.5 Hz, and 18.0 Hz.

Example expectation: the spectral demo is deterministic and should show the main peaks near 1.0 Hz, 7.5 Hz, and 18.0 Hz.

If you want the method background behind `FFT Amplitude` and `Welch PSD`, see [docs/latex/fft_welch_example.pdf](latex/fft_welch_example.pdf).

## What To Expect

- The main window is where you load data, check it, and prepare it.
- The main window now uses a left-side preparation flow and a right-side `Preview` area with separate `Plot` and `Table` tabs.
- Creating a prepared dataset currently keeps the full selected dataframe unless you explicitly reduce the column set.
- The overview plot is useful for inspection, but it is not currently a row-range trimming control.
- Creating a prepared dataset adds a new dataset inside the app. It does not automatically save a new file to disk.
- The analysis workspace is where you do the deeper analysis work and exports.

## If It Does Not Match

- Check that the active analysis column is `clean_signal` or `measured_signal`.
- Check that `X / reference` is `time_s`.
- Try `Welch PSD` after the FFT view if you want a smoother spectrum.
- If the demo result still looks wrong, treat it as a concrete defect signal in the current implementation, not as user error.

For the formal difference between the two spectrum methods, see [docs/latex/fft_welch_example.pdf](latex/fft_welch_example.pdf).

## Next

- [docs/user-guide.md](docs/user-guide.md) for the normal workflow
- [docs/demo-validation.md](docs/demo-validation.md) for a reproducible manual validation pass on all built-in demo datasets
- [docs/which-tool-when.md](docs/which-tool-when.md) to decide which window to use
- [docs/faq.md](docs/faq.md) if something behaves differently than expected
