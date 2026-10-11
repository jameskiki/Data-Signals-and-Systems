"""Dependency-aware deletion of datasets and result snapshots."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeletionPlan:
    step_ids: frozenset[str]
    dataset_paths: tuple[str, ...]
    result_count: int


def plan_history_deletion(app, step_id: str) -> DeletionPlan:
    history = app.operation_history
    selected = next((step for step in history.steps if step.id == step_id), None)
    if selected is None:
        raise ValueError("The selected history node no longer exists.")
    if selected.operation in {"rename_dataset", "assign_roles", "reinfer_roles", "workspace_roles"}:
        raise ValueError(
            "Metadata edits cannot be deleted individually: their current names/roles would also need rollback. "
            "Delete the dataset's input/processing node instead, or make a new metadata edit."
        )
    deleted = {step_id}
    removed_revisions: set[str] = set()
    for step in history.steps:
        if step.id in deleted or any(parent in removed_revisions for parent in step.input_revisions):
            deleted.add(step.id)
            if step.output_revision not in step.input_revisions:
                removed_revisions.add(step.output_revision)
    published_paths = {
        step.label for step in history.steps if step.id in deleted and step.operation == "publish"
    }
    paths = tuple(
        path for path, context in app.dataset_contexts.items()
        if context.revision_id in removed_revisions or (
            path in published_paths and any(
                step.id in deleted and step.operation == "publish" and step.label == path
                and step.output_revision == context.revision_id for step in history.steps
            )
        )
    )
    return DeletionPlan(
        frozenset(deleted), paths, sum(step_id in history.artifact_tables for step_id in deleted),
    )


def delete_history_nodes(app, step_id: str, expected: DeletionPlan) -> None:
    if plan_history_deletion(app, step_id) != expected:
        raise ValueError("Deletion dependencies changed. Preview the deletion again.")
    for workspace in list(app._analysis_workspaces):
        workspace.close()
    for window in list(app._comparison_windows):
        window.close()
    for path in expected.dataset_paths:
        app.data_frames.pop(path)
        app.dataset_contexts.pop(path)
    history = app.operation_history
    history.remove_steps(expected.step_ids)
