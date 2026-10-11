"""Safe append recipes, snapshot isolation, and explicit rejection cases."""

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from Source.datapreparation_app.datasets import register_dataset
from Source.datapreparation_app.append_workflow import plan_append, execute_append, replay_operation
from Source.datapreparation_app.project_io import ProjectSnapshot, save_project, load_project
from Source.data_ops.signals import apply_signal_filter
from Source.data_ops.spectral import compute_fft_spectrum


def example(legacy_publish=False):
    app = SimpleNamespace(data_frames={}, dataset_contexts={})
    raw = pd.DataFrame({"time": np.arange(12, dtype=float), "signal": np.arange(12, dtype=float)})
    incoming = pd.DataFrame({"time": np.arange(12, 24, dtype=float), "signal": np.arange(12, 24, dtype=float)})
    for path, frame in (("day1.csv", raw), ("day2.csv", incoming)):
        register_dataset(app, path, frame, history_operation="load_file", column_roles={"time": "time"})
    source = app.dataset_contexts["day1.csv"].revision_id
    parameters = {"source_column": "signal", "output_column": "smooth", "window_size": 3}
    filtered = apply_signal_filter(raw, "signal", "moving_average", "smooth", window_size=3)
    revision = app.operation_history.record("moving_average", "day1.csv", (source,), parameters)
    register_dataset(app, "processed.csv", filtered, history_operation="publish", history_inputs=(revision,),
                     history_revision=revision if legacy_publish else None, column_roles={"time": "time"})
    result = compute_fft_spectrum(filtered, "smooth", reference_column="time")
    app.operation_history.record_result("FFT Amplitude", "processed.csv", revision, result, {})
    return app


def test_append_reapplies_whole_run_preserves_old_fft_and_supports_next_delivery(tmp_path):
    app = example()
    old = app.data_frames["processed.csv"].copy()
    old_steps = app.operation_history.steps
    artifacts = app.operation_history.artifact_tables
    fft_id = old_steps[-1].id
    spectrum = artifacts[fft_id]["amplitudes"].copy()
    plan = plan_append(app, "processed.csv", "day2.csv")
    assert [step.operation for step in plan.operations] == ["moving_average"]
    assert not plan.warnings
    raw_path, processed_path = execute_append(app, plan)
    combined = pd.concat([app.data_frames["day1.csv"], app.data_frames["day2.csv"]], ignore_index=True)
    expected = apply_signal_filter(combined, "signal", "moving_average", "smooth", window_size=3)
    pd.testing.assert_frame_equal(app.data_frames[processed_path], expected)
    pd.testing.assert_frame_equal(app.data_frames["processed.csv"], old)
    pd.testing.assert_frame_equal(artifacts[fft_id]["amplitudes"], spectrum)
    assert app.operation_history.steps[:len(old_steps)] == old_steps
    assert app.data_frames[processed_path]["smooth"].iloc[11] != old["smooth"].iloc[11]
    append_step = next(step for step in app.operation_history.steps if step.operation == "append_raw")
    assert len(append_step.input_revisions) == 2
    path = str(tmp_path / "run.evaldata")
    save_project(path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    restored = load_project(path)
    app = SimpleNamespace(data_frames=restored.data_frames, dataset_contexts=restored.dataset_contexts,
                          operation_history=restored.history)
    register_dataset(app, "day3.csv", pd.DataFrame({"time": np.arange(24, 36, dtype=float),
                                                 "signal": np.arange(24, 36, dtype=float)}),
                     history_operation="load_file", column_roles={"time": "time"})
    next_plan = plan_append(app, processed_path, "day3.csv")
    assert next_plan.raw_path == raw_path
    _, next_processed = execute_append(app, next_plan)
    assert len(app.data_frames[next_processed]) == 36
    assert len(app.operation_history.artifact_tables) == 1


def test_publish_has_own_revision_and_legacy_shared_revision_still_appends():
    app = example()
    publish = app.operation_history.steps[-2]
    assert publish.operation == "publish"
    assert app.dataset_contexts["processed.csv"].revision_id == publish.output_revision
    assert publish.output_revision not in publish.input_revisions
    _, processed = execute_append(app, plan_append(app, "processed.csv", "day2.csv"))
    new_publish = app.operation_history.steps[-1]
    assert new_publish.operation == "publish"
    assert app.dataset_contexts[processed].revision_id == new_publish.output_revision
    legacy = example(legacy_publish=True)
    plan = plan_append(legacy, "processed.csv", "day2.csv")
    assert [step.operation for step in plan.operations] == ["moving_average"]


@pytest.mark.parametrize("case,match", [
    ("overlap", "overlap"), ("columns", "missing existing"), ("dtype", "types differ"),
    ("descending", "strictly increasing"), ("missing", "finite"),
])
def test_incompatible_append_is_rejected_without_mutation(case, match):
    app = example()
    incoming = app.data_frames["day2.csv"]
    if case == "overlap":
        incoming["time"] -= 1
    elif case == "columns":
        incoming.drop(columns="signal", inplace=True)
    elif case == "dtype":
        incoming["signal"] = incoming["signal"].astype("int64")
    elif case == "descending":
        incoming["time"] = incoming["time"].iloc[::-1].to_numpy()
    else:
        incoming.loc[0, "time"] = np.nan
    before = app.operation_history.steps
    with pytest.raises(ValueError, match=match):
        plan_append(app, "processed.csv", "day2.csv")
    assert app.operation_history.steps == before
    assert len(app.data_frames) == 3


def test_gap_warns_and_recipe_mismatch_blocks():
    app = example()
    app.data_frames["day2.csv"]["time"] += 10
    plan = plan_append(app, "processed.csv", "day2.csv")
    assert "Time gap" in plan.warnings[0]
    assert "adjacent rows" in plan.warnings[-1]
    app.data_frames["processed.csv"].loc[0, "smooth"] = -100
    with pytest.raises(ValueError, match="no longer reproduces"):
        plan_append(app, "processed.csv", "day2.csv")


@pytest.mark.parametrize("operation", ["prepare", "apply_kept_cycles", "untracked", "resample", "merge", "reset"])
def test_unsupported_or_untracked_step_blocks_recipe(operation):
    app = example()
    parent = app.dataset_contexts["processed.csv"].revision_id
    register_dataset(app, "unsupported.csv", app.data_frames["processed.csv"], history_operation=operation,
                     history_inputs=(parent,))
    with pytest.raises(ValueError, match="Cannot reapply|Incomplete"):
        plan_append(app, "unsupported.csv", "day2.csv")


def test_missing_raw_and_processed_incoming_are_rejected():
    app = example()
    with pytest.raises(ValueError, match="must be raw"):
        plan_append(app, "day1.csv", "processed.csv")
    app.data_frames.pop("day1.csv")
    app.dataset_contexts.pop("day1.csv")
    with pytest.raises(ValueError, match="no longer in the project"):
        plan_append(app, "processed.csv", "day2.csv")


def test_stale_plan_does_not_register_outputs():
    app = example()
    plan = plan_append(app, "processed.csv", "day2.csv")
    app.data_frames["day2.csv"]["time"] += 3
    before = app.operation_history.steps
    with pytest.raises(ValueError, match="changed after preview"):
        execute_append(app, plan)
    assert app.operation_history.steps == before


def test_changed_incoming_values_invalidate_preview():
    app = example()
    plan = plan_append(app, "processed.csv", "day2.csv")
    app.data_frames["day2.csv"].loc[0, "signal"] = 1000
    with pytest.raises(ValueError, match="changed after preview"):
        execute_append(app, plan)


def test_derived_and_range_filter_recipe_replays_recorded_parameters():
    app = example()
    frame = app.data_frames["day1.csv"]
    roles = app.dataset_contexts["day1.csv"].column_roles
    source = app.dataset_contexts["day1.csv"].revision_id
    for operation, parameters in [
        ("derived_derivative", {"source_column": "signal", "output_column": "rate",
                                "reference_column": "time", "window_size": 5}),
        ("simple_filter", {"source_column": "signal", "output_column": "masked",
                           "minimum": "3", "maximum": "", "keep_missing": False}),
    ]:
        app.operation_history.record(operation, "day1.csv", (source,), parameters)
        frame, roles = replay_operation(frame, roles, app.operation_history.steps[-1])
    np.testing.assert_allclose(frame["rate"].iloc[1:], 1)
    assert frame["masked"].iloc[:3].isna().all()


def test_missing_recipe_parameters_are_not_defaulted():
    app = example()
    source = app.dataset_contexts["day1.csv"].revision_id
    app.operation_history.record("moving_average", "source", (source,),
                                 {"source_column": "signal", "output_column": "smooth"})
    with pytest.raises(ValueError, match="Incomplete parameters"):
        replay_operation(app.data_frames["day1.csv"], {}, app.operation_history.steps[-1])


def test_append_datetime_precision_after_embedded_project_reopen(tmp_path):
    app = example()
    for path in ("day1.csv", "processed.csv", "day2.csv"):
        frame = app.data_frames[path]
        frame["time"] = pd.Timestamp("2026-10-01") + pd.to_timedelta(frame["time"], unit="s")
        frame["time"] = frame["time"].dt.as_unit("s")
    path = str(tmp_path / "run.evaldata")
    save_project(path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    restored = load_project(path)
    app = SimpleNamespace(data_frames=restored.data_frames, dataset_contexts=restored.dataset_contexts,
                          operation_history=restored.history)
    app.data_frames["day2.csv"]["time"] = app.data_frames["day2.csv"]["time"].dt.as_unit("s")
    assert app.data_frames["day1.csv"]["time"].dtype != app.data_frames["day2.csv"]["time"].dtype
    plan = plan_append(app, "processed.csv", "day2.csv")
    _, processed = execute_append(app, plan)
    assert len(app.data_frames[processed]) == 24
    assert app.data_frames[processed]["time"].diff().dropna().eq(pd.Timedelta(seconds=1)).all()


def test_type_error_identifies_column():
    app = example()
    app.data_frames["day2.csv"]["signal"] = app.data_frames["day2.csv"]["signal"].astype("int64")
    with pytest.raises(ValueError, match="signal: existing float64, incoming int64"):
        plan_append(app, "processed.csv", "day2.csv")


def test_added_columns_keep_missing_history_roles_and_repeat_append(tmp_path):
    app = example()
    app.data_frames["day2.csv"]["sensor"] = np.arange(12, dtype="int64")
    app.data_frames["day2.csv"]["flag"] = True
    app.dataset_contexts["day2.csv"].column_roles.update(sensor="signal", flag="metadata")
    plan = plan_append(app, "processed.csv", "day2.csv")
    assert plan.added_columns == ("sensor", "flag")
    assert "Earlier rows will be missing" in plan.warnings[-1]
    raw_path, processed_path = execute_append(app, plan)
    result = app.data_frames[processed_path]
    assert result["sensor"].iloc[:12].isna().all()
    assert result["flag"].iloc[:12].isna().all()
    assert str(result["sensor"].dtype) == "Int64"
    assert str(result["flag"].dtype) == "boolean"
    assert result["sensor"].iloc[12:].tolist() == list(range(12))
    assert app.dataset_contexts[processed_path].column_roles["sensor"] == "signal"
    step = next(step for step in app.operation_history.steps if step.operation == "append_raw")
    assert json.loads(step.parameters_json)["added_columns"] == ["sensor", "flag"]
    path = str(tmp_path / "project.evaldata")
    save_project(path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    restored = load_project(path)
    app = SimpleNamespace(data_frames=restored.data_frames, dataset_contexts=restored.dataset_contexts,
                          operation_history=restored.history)
    register_dataset(app, "day3.csv", pd.DataFrame({
        "time": np.arange(24, 36, dtype=float), "signal": np.arange(24, 36, dtype=float),
        "sensor": np.arange(12, dtype="int64"), "flag": False,
    }), history_operation="load_file", column_roles={"time": "time"})
    _, third = execute_append(app, plan_append(app, processed_path, "day3.csv"))
    assert len(app.data_frames[third]) == 36
    assert app.data_frames[third]["sensor"].iloc[:12].isna().all()
    assert len(app.operation_history.artifact_tables) == 1


def test_new_sensor_cannot_overwrite_recipe_output():
    app = example()
    app.data_frames["day2.csv"]["smooth"] = 100
    with pytest.raises(ValueError, match="conflict"):
        plan_append(app, "processed.csv", "day2.csv")
