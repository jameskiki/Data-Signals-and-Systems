"""In-memory provenance for the first workflow prototype."""

import json
import math
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class HistoryStep:
    id: str
    operation: str
    label: str
    input_revisions: tuple[str, ...]
    output_revision: str
    parameters_json: str
    timestamp: str
    tracked: bool


class OperationHistory:
    def __init__(self) -> None:
        self._steps: list[HistoryStep] = []
        self.artifact_tables: dict[str, dict[str, pd.DataFrame]] = {}

    def record_result(self, operation: str, label: str, revision: str, result, parameters: dict[str, object]) -> None:
        metadata: dict[str, object] = dict(parameters)
        tables: dict[str, pd.DataFrame] = {}
        for item in fields(result):
            value = getattr(result, item.name)
            if isinstance(value, pd.DataFrame):
                tables[item.name] = value.copy(deep=True)
            elif isinstance(value, np.ndarray):
                tables[item.name] = pd.DataFrame(value.copy())
            elif isinstance(value, float) and not math.isfinite(value):
                metadata[item.name] = None
            else:
                metadata[item.name] = value
        metadata["result_tables"] = list(tables)
        self.record(operation, label, (revision,), metadata, output_revision=revision)
        self.artifact_tables[self._steps[-1].id] = tables

    @classmethod
    def from_steps(cls, raw_steps: list[dict[str, object]]) -> "OperationHistory":
        history = cls()
        known: set[str] = set()
        ids: set[str] = set()
        for raw in raw_steps:
            if not isinstance(raw, dict) or set(raw) != set(HistoryStep.__dataclass_fields__):
                raise ValueError("Invalid project history record.")
            if not all(isinstance(raw[key], str) for key in (
                "id", "operation", "label", "output_revision", "parameters_json", "timestamp",
            )) or not isinstance(raw["tracked"], bool):
                raise ValueError("Invalid project history field type.")
            inputs = raw["input_revisions"]
            if not isinstance(inputs, list) or any(not isinstance(item, str) or item not in known for item in inputs):
                raise ValueError("Invalid project history parent link.")
            if raw["id"] in ids or not isinstance(json.loads(raw["parameters_json"]), dict):
                raise ValueError("Invalid project history identity or parameters.")
            step = HistoryStep(
                id=raw["id"], operation=raw["operation"], label=raw["label"],
                input_revisions=tuple(inputs), output_revision=raw["output_revision"],
                parameters_json=raw["parameters_json"], timestamp=raw["timestamp"], tracked=raw["tracked"],
            )
            history._steps.append(step)
            ids.add(step.id)
            known.add(step.output_revision)
        return history


    @property
    def steps(self) -> tuple[HistoryStep, ...]:
        return tuple(self._steps)

    def remove_steps(self, step_ids: frozenset[str]) -> None:
        remaining = [step for step in self._steps if step.id not in step_ids]
        known: set[str] = set()
        for step in remaining:
            if any(parent not in known for parent in step.input_revisions):
                raise ValueError("Deletion would leave a dangling history dependency.")
            known.add(step.output_revision)
        self._steps = remaining
        for step_id in step_ids:
            self.artifact_tables.pop(step_id, None)

    def record(
        self,
        operation: str,
        label: str,
        input_revisions: tuple[str, ...] = (),
        parameters: dict[str, object] | None = None,
        *,
        tracked: bool = True,
        output_revision: str | None = None,
    ) -> str:
        known = {step.output_revision for step in self._steps}
        if any(revision not in known for revision in input_revisions):
            raise ValueError("History input revision is not registered.")
        if output_revision is not None and output_revision not in known:
            raise ValueError("History output revision is not registered.")
        revision = output_revision or str(uuid4())
        encoded = json.dumps(parameters or {}, sort_keys=True, allow_nan=False)
        self._steps.append(HistoryStep(
            id=str(uuid4()), operation=operation, label=label,
            input_revisions=input_revisions, output_revision=revision,
            parameters_json=encoded,
            timestamp=datetime.now(timezone.utc).isoformat(), tracked=tracked,
        ))
        return revision


REPORT_VIEW_OPERATION = "report_view"


def remember_workspace_step(workspace, history: OperationHistory) -> None:
    """Remember steps recorded by an analysis workspace so publish can link them."""
    if history.steps:
        ids = getattr(workspace, "history_step_ids", None)
        if ids is None:
            ids = []
            workspace.history_step_ids = ids
        ids.append(history.steps[-1].id)


def record_workspace_result(workspace, operation: str, result, parameters: dict[str, object]) -> None:
    history = getattr(workspace, "operation_history", None)
    revision = getattr(workspace, "history_revision", None)
    if history is not None and revision is not None:
        history.record_result(operation, workspace.session.source_path, revision, result, parameters)
        remember_workspace_step(workspace, history)


def record_workspace_view(workspace, parameters: dict[str, object]) -> bool:
    """Record plot settings the report re-renders from the published data (no image is stored)."""
    history = getattr(workspace, "operation_history", None)
    revision = getattr(workspace, "history_revision", None)
    if history is None or revision is None:
        return False
    history.record(REPORT_VIEW_OPERATION, workspace.session.source_path, (revision,), parameters, output_revision=revision)
    remember_workspace_step(workspace, history)
    return True
