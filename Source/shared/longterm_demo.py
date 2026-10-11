"""One deterministic long-term test delivered as three consecutive daily files."""

from pathlib import Path

import numpy as np
import pandas as pd

from Source.data_ops.io_ops import write_dataframe_with_progress


DAILY_SAMPLE_COUNT = 86_400
SLOW_CYCLE_PERIOD_S = 12 * 3600
LONGTERM_FILENAMES = tuple(f"longterm_run_day_{day:02d}.csv" for day in range(1, 4))


def create_longterm_daily_frames() -> tuple[pd.DataFrame, ...]:
    count = 3 * DAILY_SAMPLE_COUNT
    elapsed = np.arange(count)
    rng = np.random.default_rng(20261011)
    drift = 0.6 * elapsed / (count - 1)
    anomaly = (elapsed >= 2 * DAILY_SAMPLE_COUNT + 12 * 3600) & (
        elapsed < 2 * DAILY_SAMPLE_COUNT + 12 * 3600 + 600
    )
    reference = 10 + 0.8 * np.sin(2 * np.pi * elapsed / 3600)
    slow_cycle = 0.5 * np.sin(2 * np.pi * elapsed / SLOW_CYCLE_PERIOD_S)
    frame = pd.DataFrame({
        "timestamp": pd.date_range("2026-10-01", periods=count, freq="s"),
        "elapsed_s": elapsed,
        "measurement": reference + slow_cycle + drift + rng.normal(0, 0.03, count) + 2.5 * anomaly,
        "reference": reference,
        "temperature_c": 22 + 2 * np.sin(2 * np.pi * elapsed / DAILY_SAMPLE_COUNT) + 0.2 * drift,
        "run_id": "longterm_demo_001",
        "day_number": elapsed // DAILY_SAMPLE_COUNT + 1,
        "known_drift": drift,
        "known_slow_cycle": slow_cycle,
        "known_anomaly": anomaly,
    })
    return tuple(
        frame.iloc[start:start + DAILY_SAMPLE_COUNT].reset_index(drop=True)
        for start in range(0, count, DAILY_SAMPLE_COUNT)
    )


def write_longterm_demo_files(output_dir: str) -> tuple[str, ...]:
    directory = Path(output_dir)
    paths = tuple(directory / name for name in LONGTERM_FILENAMES)
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError("Demo files already exist; choose another folder:\n" + "\n".join(existing))
    directory.mkdir(parents=True, exist_ok=True)
    for path, frame in zip(paths, create_longterm_daily_frames(), strict=True):
        write_dataframe_with_progress(frame, str(path))
    return tuple(str(path) for path in paths)
