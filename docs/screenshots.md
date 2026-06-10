# Screenshot Plan

This repository now reserves `docs/images/` for screenshots that show the current UI and workflow.

## Automated Capture

Use the single script below to generate the full algorithm coverage set automatically:

```powershell
python scripts/capture_app_screenshots.py
```

Default output directory:

- `docs/images/overview/`

Optional custom output directory:

```powershell
python scripts/capture_app_screenshots.py --output-dir docs/images/my-run
```

If screenshot capture fails with a Pillow import error, install Pillow in your active environment:

```powershell
pip install Pillow
```

## Default Capture Set (Minimal + Full Algorithm Coverage)

- `main-window.png`
- `algorithms-filtering.png` (simple filtering, all signal-processing filters, and resample)
- `algorithms-derived-signals.png` (all derived-signal operations)
- `algorithms-frequency.png` (FFT, Welch PSD, Transfer Estimate, Coherence, Spectrogram)
- `algorithms-cycles.png` (fixed-length, rising-edge, zero-crossing, peak)

## Additional Explanatory Images

The cycle-analysis docs also use focused annotated visuals:

- `cycle-analysis-map.png`
- `cycle-analysis-metrics-annotated.png`
- `cycles-workspace-raw.png`

## Naming Convention

The script writes these stable names by default:

- `main-window.png`
- `algorithms-filtering.png`
- `algorithms-derived-signals.png`
- `algorithms-frequency.png`
- `algorithms-cycles.png`

## Notes

- Prefer screenshots from demo datasets when possible so the visuals are reproducible.
- Cycle-focused screenshots should use the `Cycle Validation Drift Signal` demo dataset.
- Frequency screenshots should continue to use the spectral reference demo dataset.
- Capture the app at a readable scale and avoid personal file paths when practical.
- After images are added, the README can embed the most representative ones directly.
