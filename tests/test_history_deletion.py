"""Cascading removal follows revision dependencies, not chronological proximity."""

from types import SimpleNamespace

import pandas as pd
import pytest

from Source.datapreparation_app.datasets import register_dataset
from Source.datapreparation_app.history_deletion import plan_history_deletion, delete_history_nodes
from Source.datapreparation_app.project_io import ProjectSnapshot, save_project, load_project


def example():
    app = SimpleNamespace(data_frames={}, dataset_contexts={}, _analysis_workspaces=[], _comparison_windows=[])
    frame = pd.DataFrame({"signal": [1, 2]})
    register_dataset(app, "source", frame, history_operation="load_demo")
    root = app.dataset_contexts["source"].revision_id
    register_dataset(app, "branch", frame, history_operation="prepare", history_inputs=(root,))
    branch = app.dataset_contexts["branch"].revision_id
    app.operation_history.record("FFT", "branch", (branch,), output_revision=branch)
    app.operation_history.artifact_tables[app.operation_history.steps[-1].id] = {"values": frame.copy()}
    register_dataset(app, "sibling", frame, history_operation="prepare", history_inputs=(root,))
    return app


def test_deleting_branch_keeps_earlier_source_and_unrelated_sibling(tmp_path):
    app = example()
    step = app.operation_history.steps[1]
    plan = plan_history_deletion(app, step.id)
    assert len(plan.step_ids) == 2
    assert plan.dataset_paths == ("branch",)
    assert plan.result_count == 1
    closed = []
    app._analysis_workspaces.append(SimpleNamespace(close=lambda: closed.append("analysis")))
    app._comparison_windows.append(SimpleNamespace(close=lambda: closed.append("comparison")))
    delete_history_nodes(app, step.id, plan)
    assert closed == ["analysis", "comparison"]
    assert set(app.data_frames) == {"source", "sibling"}
    assert not app.operation_history.artifact_tables
    path = str(tmp_path / "remaining.evaldata")
    save_project(path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    assert set(load_project(path).data_frames) == {"source", "sibling"}


def test_snapshot_is_leaf_and_does_not_remove_input_or_later_sibling():
    app = example()
    step = app.operation_history.steps[2]
    plan = plan_history_deletion(app, step.id)
    assert plan.step_ids == frozenset({step.id})
    assert not plan.dataset_paths
    delete_history_nodes(app, step.id, plan)
    assert len(app.data_frames) == 3


def test_source_cascades_through_all_branches():
    app = example()
    plan = plan_history_deletion(app, app.operation_history.steps[0].id)
    assert len(plan.step_ids) == 4
    assert len(plan.dataset_paths) == 3


def test_metadata_removal_requires_rollback_and_stale_preview_is_rejected():
    app = example()
    revision = app.dataset_contexts["source"].revision_id
    app.operation_history.record("rename_dataset", "source", (revision,), output_revision=revision)
    with pytest.raises(ValueError, match="rollback"):
        plan_history_deletion(app, app.operation_history.steps[-1].id)
    root_id = app.operation_history.steps[0].id
    plan = plan_history_deletion(app, root_id)
    register_dataset(app, "new", app.data_frames["source"], history_operation="prepare", history_inputs=(revision,))
    with pytest.raises(ValueError, match="changed"):
        delete_history_nodes(app, root_id, plan)
    assert len(app.data_frames) == 4


def test_deleting_publish_removes_published_dataset_and_its_followups_only():
    app = example()
    branch = app.dataset_contexts["branch"].revision_id
    register_dataset(app, "published", app.data_frames["branch"], history_operation="publish", history_inputs=(branch,))
    published = app.dataset_contexts["published"].revision_id
    assert published != branch
    app.operation_history.record("moving_average", "published", (published,))
    publish_id = app.operation_history.steps[-2].id
    plan = plan_history_deletion(app, publish_id)
    assert len(plan.step_ids) == 2
    assert plan.dataset_paths == ("published",)
