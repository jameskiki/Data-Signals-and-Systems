"""Continuous daily file boundaries and incremental project import checks."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from Source.shared.longterm_demo import create_longterm_daily_frames, write_longterm_demo_files
from Source.datapreparation_app.data_parser import DataParser
from Source.datapreparation_app.datasets import register_dataset
from Source.datapreparation_app.project_io import ProjectSnapshot, save_project, load_project
from Source.data_ops.io_ops import merge_selected_dataframes
from Source.data_ops.spectral import compute_fft_spectrum


def test_three_days_are_continuous_deterministic_and_have_late_anomaly():
    frames = create_longterm_daily_frames()
    assert len(frames) == 3
    assert [len(frame) for frame in frames] == [86_400] * 3
    combined = pd.concat(frames, ignore_index=True)
    assert combined["timestamp"].is_unique
    assert combined["timestamp"].diff().dropna().eq(pd.Timedelta(seconds=1)).all()
    assert combined["elapsed_s"].tolist() == list(range(259_200))
    assert combined["run_id"].nunique() == 1
    assert [int(frame["known_anomaly"].sum()) for frame in frames] == [0, 0, 600]
    assert combined["known_drift"].is_monotonic_increasing
    assert combined["known_drift"].iloc[-1] == 0.6
    np.testing.assert_allclose(frames[2]["measurement"], create_longterm_daily_frames()[2]["measurement"])
    noise = combined["measurement"] - combined["reference"] - combined["known_slow_cycle"] - combined["known_drift"]
    noise -= 2.5 * combined["known_anomaly"]
    assert noise.abs().max() < 0.2


def test_slow_half_day_cycle_is_visible_in_one_day_fft():
    day = create_longterm_daily_frames()[0]
    spectrum = compute_fft_spectrum(day, "known_slow_cycle", reference_column="elapsed_s")
    assert spectrum.dominant_frequency == pytest.approx(1 / (12 * 3600))
    assert spectrum.dominant_amplitude == pytest.approx(0.5)
    residual = day["measurement"] - day["reference"] - day["known_drift"]
    slow = compute_fft_spectrum(day.assign(residual=residual), "residual", reference_column="elapsed_s")
    assert slow.dominant_frequency == pytest.approx(1 / (12 * 3600))
    assert slow.dominant_amplitude == pytest.approx(0.5, abs=0.01)


def test_files_can_be_imported_incrementally_after_project_reopen(tmp_path):
    paths = write_longterm_demo_files(str(tmp_path / "incoming"))
    app = SimpleNamespace(data_frames={}, dataset_contexts={})
    day1, _, _ = DataParser.load_file(paths[0])
    spectrum = compute_fft_spectrum(day1, "reference", reference_column="timestamp")
    assert spectrum.sample_spacing == 1
    assert spectrum.nyquist_frequency == 0.5
    assert spectrum.dominant_frequency == pytest.approx(1 / 3600)
    assert spectrum.dominant_amplitude == pytest.approx(0.8)
    register_dataset(app, paths[0], day1, history_operation="load_file")
    project_path = str(tmp_path / "test.evaldata")
    save_project(project_path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    restored = load_project(project_path)
    app = SimpleNamespace(data_frames=restored.data_frames, dataset_contexts=restored.dataset_contexts,
                          operation_history=restored.history)
    for path in paths[1:]:
        frame, _, _ = DataParser.load_file(path)
        register_dataset(app, path, frame, history_operation="load_file")
    merged = merge_selected_dataframes(paths, app.data_frames)
    assert len(merged) == 259_200
    assert merged["timestamp"].diff().dropna().eq(pd.Timedelta(seconds=1)).all()
    assert len(app.operation_history.steps) == 3
    with pytest.raises(FileExistsError, match="already exist"):
        write_longterm_demo_files(str(tmp_path / "incoming"))
