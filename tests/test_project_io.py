"""Embedded project round trips, result provenance, and safe-save failures."""

import json
import zipfile
from dataclasses import asdict
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from Source.datapreparation_app import project_io
from Source.datapreparation_app.datasets import register_dataset
from Source.shared.operation_history import OperationHistory
from Source.data_ops.spectral import (
    compute_fft_spectrum, compute_welch_psd, compute_coherence_spectrum,
    compute_transfer_estimate, compute_spectrogram,
)
from Source.data_ops.cycles import compute_fixed_length_cycle_analysis


def snapshot():
    app = SimpleNamespace(data_frames={}, dataset_contexts={})
    frame = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=128, freq="ms", tz="UTC"),
        "signal": np.sin(np.arange(128) / 10),
        "reference": np.cos(np.arange(128) / 10),
        "count": pd.Series([1, None] * 64, dtype="Int64"),
    })
    frame.index = pd.Index(np.arange(128) + 100, name="sample")
    register_dataset(app, "moved-source.csv", frame, column_roles={"time": "time", "signal": "signal"},
                     history_operation="load_file")
    return project_io.ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history)


@pytest.mark.parametrize("method", ["fft", "welch", "coherence", "transfer", "spectrogram", "cycles"])
def test_project_preserves_frames_identity_roles_history_and_results(tmp_path, method):
    original = snapshot()
    frame = original.data_frames["moved-source.csv"]
    kwargs = {"dataframe": frame, "source_column": "signal", "sample_spacing": 0.001}
    if method == "cycles":
        result = compute_fixed_length_cycle_analysis(frame, "signal", 16)
    elif method == "fft":
        result = compute_fft_spectrum(**kwargs)
    elif method == "spectrogram":
        result = compute_spectrogram(**kwargs, segment_length=32)
    elif method == "welch":
        result = compute_welch_psd(**kwargs, segment_length=32)
    elif method == "coherence":
        result = compute_coherence_spectrum(**kwargs, comparison_column="reference", segment_length=32)
    else:
        result = compute_transfer_estimate(**kwargs, comparison_column="reference", segment_length=32)
    revision = original.dataset_contexts["moved-source.csv"].revision_id
    original.history.record_result(method, "moved-source.csv", revision, result, {})
    path = str(tmp_path / "project.evaldata")
    project_io.save_project(path, original)
    restored = project_io.load_project(path)
    pd.testing.assert_frame_equal(restored.data_frames["moved-source.csv"], frame)
    assert restored.dataset_contexts["moved-source.csv"].dataset_id == original.dataset_contexts["moved-source.csv"].dataset_id
    assert restored.dataset_contexts["moved-source.csv"].column_roles == original.dataset_contexts["moved-source.csv"].column_roles
    assert restored.history.steps == original.history.steps
    step_id = restored.history.steps[-1].id
    for name, table in original.history.artifact_tables[step_id].items():
        pd.testing.assert_frame_equal(restored.history.artifact_tables[step_id][name], table)
    assert not list(tmp_path.glob(".evaldata-*.tmp"))


def test_failed_save_preserves_existing_project_and_cleans_temporary(tmp_path, monkeypatch):
    path = tmp_path / "project.evaldata"
    project_io.save_project(str(path), snapshot())
    before = path.read_bytes()
    def fail(*args):
        raise OSError("disk failure")
    monkeypatch.setattr(project_io, "_write_frame", fail)
    with pytest.raises(OSError, match="disk failure"):
        project_io.save_project(str(path), snapshot())
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".evaldata-*.tmp"))


def rewrite_manifest(path, update):
    with zipfile.ZipFile(path) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(contents["manifest.json"])
    update(manifest)
    contents["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in contents.items():
            archive.writestr(name, payload)


def test_report_selection_is_per_publish_persistent_and_cleaned_on_deletion(tmp_path):
    original = snapshot()
    history = original.history
    source = history.steps[0]
    history.set_note(source.id, "Data source decision")
    history.record("publish", "first.csv", (source.output_revision,), {"workspace_steps": [source.id]})
    first = history.steps[-1].id
    history.record("publish", "second.csv", (source.output_revision,), {"workspace_steps": [source.id]})
    second = history.steps[-1].id
    history.set_report_node_enabled(first, source.id, False)
    assert not history.report_node_enabled(first, source.id)
    assert history.report_node_enabled(second, source.id)
    with pytest.raises(ValueError):
        history.set_report_node_enabled(first, "unknown", True)
    with pytest.raises(ValueError):
        history.set_report_node_enabled(first, source.id, "yes")
    path = tmp_path / "choices.evaldata"
    project_io.save_project(str(path), original)
    restored = project_io.load_project(str(path)).history
    assert restored.report_selection == {first: {source.id: False}}
    restored.remove_steps(frozenset({first}))
    assert restored.report_selection == {}
    rewrite_manifest(path, lambda manifest: manifest.pop("report_selection"))
    legacy = project_io.load_project(str(path)).history
    assert legacy.report_node_enabled(first, source.id)


@pytest.mark.parametrize("choices", [
    [],
    {"missing": {}},
    {"TARGET": {"unknown": True}},
    {"TARGET": {"SOURCE": "yes"}},
])
def test_invalid_report_selection_is_rejected(tmp_path, choices):
    original = snapshot()
    history = original.history
    source = history.steps[0]
    history.record("publish", "first.csv", (source.output_revision,), {"workspace_steps": [source.id]})
    publish_id = history.steps[-1].id
    path = tmp_path / "choices.evaldata"
    project_io.save_project(str(path), original)
    converted = json.loads(json.dumps(choices).replace("TARGET", publish_id).replace("SOURCE", source.id))
    rewrite_manifest(path, lambda manifest: manifest.update(report_selection=converted))
    with pytest.raises(ValueError):
        project_io.load_project(str(path))


@pytest.mark.parametrize("change", [
    lambda m: m.update(schema_version=99),
    lambda m: m["history"][0].update(input_revisions=["missing"]),
    lambda m: m["datasets"][0].update(revision_id="missing"),
    lambda m: m["datasets"][0].update(sha256="bad"),
    lambda m: m["datasets"][0].update(file="missing.parquet"),
])
def test_corrupt_project_is_rejected(tmp_path, change):
    path = tmp_path / "project.evaldata"
    project_io.save_project(str(path), snapshot())
    rewrite_manifest(path, change)
    with pytest.raises((ValueError, KeyError)):
        project_io.load_project(str(path))


def test_result_snapshot_is_independent_of_original():
    project = snapshot()
    result = compute_fft_spectrum(project.data_frames["moved-source.csv"], "signal", sample_spacing=0.01)
    revision = project.dataset_contexts["moved-source.csv"].revision_id
    project.history.record_result("FFT", "source", revision, result, {})
    step = project.history.steps[-1]
    before = project.history.artifact_tables[step.id]["amplitudes"].copy()
    result.amplitudes[:] = -1
    pd.testing.assert_frame_equal(project.history.artifact_tables[step.id]["amplitudes"], before)
    assert step.output_revision == revision


def test_history_round_trip_and_duplicate_identity_rejection():
    history = OperationHistory()
    history.record("source", "source")
    raw = json.loads(json.dumps([asdict(step) for step in history.steps]))
    assert OperationHistory.from_steps(raw).steps == history.steps
    with pytest.raises(ValueError, match="identity"):
        OperationHistory.from_steps(raw + raw)


def test_missing_result_tables_are_rejected(tmp_path):
    project = snapshot()
    result = compute_fft_spectrum(project.data_frames["moved-source.csv"], "signal")
    project.history.record_result("FFT", "source", project.dataset_contexts["moved-source.csv"].revision_id, result, {})
    path = tmp_path / "project.evaldata"
    project_io.save_project(str(path), project)
    rewrite_manifest(path, lambda manifest: manifest.update(artifacts=[]))
    with pytest.raises(ValueError, match="incomplete"):
        project_io.load_project(str(path))


def test_failed_atomic_replace_preserves_existing_save(tmp_path, monkeypatch):
    project = snapshot()
    path = tmp_path / "project.evaldata"
    project_io.save_project(str(path), project)
    original = path.read_bytes()
    def fail(*args):
        raise PermissionError("destination locked")
    monkeypatch.setattr(project_io.os, "replace", fail)
    with pytest.raises(PermissionError, match="locked"):
        project_io.save_project(str(path), project)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".evaldata-*.tmp"))


def test_project_open_invalid_or_cancelled_does_not_mutate_session(tmp_path, monkeypatch):
    from Source.datapreparation_app import app as app_module

    current = snapshot()
    app = SimpleNamespace(
        root=object(), data_frames=current.data_frames, dataset_contexts=current.dataset_contexts,
        operation_history=current.history, _analysis_workspaces=[], _comparison_windows=[],
    )
    errors = []
    app.open_project_path = lambda selected: app_module.DataPreparationApp.open_project_path(app, selected)
    path = tmp_path / "project.evaldata"
    path.write_bytes(b"invalid")
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **kwargs: str(path))
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda *args, **kwargs: errors.append(args))
    app_module.DataPreparationApp.open_project(app)
    assert errors and app.operation_history is current.history
    project_io.save_project(str(path), snapshot())
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *args, **kwargs: False)
    app_module.DataPreparationApp.open_project(app)
    assert app.operation_history is current.history
    assert app.data_frames is current.data_frames


def test_assign_roles_records_effective_changes_without_new_data_revision():
    from Source.datapreparation_app import actions

    project = snapshot()
    app = SimpleNamespace(
        data_frames=project.data_frames, dataset_contexts=project.dataset_contexts, operation_history=project.history,
        session=SimpleNamespace(role_editor_column="reference", role_editor_value="time"),
        _get_single_selected_file_path=lambda message: "moved-source.csv",
        _propagate_role_updates=lambda *args: None,
        _set_role_editor_column=lambda *args, **kwargs: None,
        _set_role_editor_value=lambda *args, **kwargs: None,
        _refresh_dataset_preparation_views=lambda: None,
        notifications=SimpleNamespace(success=lambda *args: None),
    )
    revision = project.dataset_contexts["moved-source.csv"].revision_id
    actions.apply_selected_column_role(app)
    step = project.history.steps[-1]
    parameters = json.loads(step.parameters_json)
    assert step.operation == "assign_roles"
    assert step.output_revision == revision
    assert parameters["before"]["time"] == "time"
    assert parameters["after"]["reference"] == "time"
    assert parameters["after"]["time"] != "time"
