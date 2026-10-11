"""In-memory provenance for the first workflow prototype."""

import json
import math
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pandas as pd


METADATA_OPERATIONS = frozenset({"rename_dataset", "assign_roles", "reinfer_roles", "workspace_roles"})
BEFORE_APPEND_KEY = "before_append"
BASED_ON_KEY = "based_on"


def before_append_step(step) -> str | None:
    """Return the append step id if this step was computed on data from before that append."""
    value = json.loads(step.parameters_json).get(BEFORE_APPEND_KEY)
    return value if isinstance(value, str) else None


def based_on_text(step) -> str:
    """Neutral description of the earlier data a step was computed on, or '' if it uses current data."""
    if before_append_step(step) is None:
        return ""
    basis = json.loads(step.parameters_json).get(BASED_ON_KEY)
    if not isinstance(basis, dict):
        return "based on the data before a later append"
    sources = ", ".join(str(item) for item in basis.get("sources", [])) or "earlier data"
    rows = basis.get("raw_rows")
    return f"based on {sources}" + (f" ({rows:,} raw rows)" if isinstance(rows, int) else "")


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
        # Editable decision notes (why a step/result mattered); not part of the immutable step record.
        self.notes: dict[str, str] = {}
        self.report_selection: dict[str, dict[str, bool]] = {}

    def report_candidates(self, publish_id: str) -> tuple[HistoryStep, ...]:
        publish = next((step for step in self._steps if step.id == publish_id and step.operation == "publish"), None)
        if publish is None:
            raise ValueError("Select an existing publish node for the report.")
        linked = json.loads(publish.parameters_json).get("workspace_steps", [])
        linked = linked if isinstance(linked, list) else []
        lineage_ids = {step.id for step in self.lineage(publish.output_revision)}
        return tuple(
            step for step in self._steps
            if step.id != publish_id and (step.id in lineage_ids or step.id in linked)
        )

    def report_node_enabled(self, publish_id: str, step_id: str) -> bool:
        candidates = self.report_candidates(publish_id)
        step = next((step for step in candidates if step.id == step_id), None)
        if step is None:
            raise ValueError("This node is not content for the selected report.")
        overrides = self.report_selection.get(publish_id, {})
        if step_id in overrides:
            return overrides[step_id]
        publish = next(step for step in self._steps if step.id == publish_id)
        linked = json.loads(publish.parameters_json).get("workspace_steps", [])
        linked = linked if isinstance(linked, list) else []
        return step_id in linked or step_id in self.notes or before_append_step(step) is not None

    def set_report_node_enabled(self, publish_id: str, step_id: str, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Report selection must be enabled or disabled.")
        self.report_node_enabled(publish_id, step_id)
        self.report_selection.setdefault(publish_id, {})[step_id] = enabled

    def set_note(self, step_id: str, text: str) -> None:
        if not any(step.id == step_id for step in self._steps):
            raise ValueError("The selected node no longer exists.")
        if text.strip():
            self.notes[step_id] = text.strip()
        else:
            self.notes.pop(step_id, None)

    def lineage(self, revision: str) -> tuple[HistoryStep, ...]:
        """Steps that produced ``revision`` plus steps recorded on those revisions (results, views, metadata)."""
        revisions = {revision}
        changed = True
        while changed:
            changed = False
            for step in self._steps:
                if step.output_revision in revisions and not set(step.input_revisions) <= revisions:
                    revisions.update(step.input_revisions)
                    changed = True
        return tuple(step for step in self._steps if step.output_revision in revisions)

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

    def rewrite_steps(self, replacements: dict[str, HistoryStep]) -> None:
        """Replace steps by id, then restore a stable topological order (parents before children)."""
        if any(step_id != step.id for step_id, step in replacements.items()):
            raise ValueError("History rewrite must keep step ids.")
        pending = [replacements.get(step.id, step) for step in self._steps]
        ordered: list[HistoryStep] = []
        known: set[str] = set()
        while pending:
            index = next(
                (index for index, step in enumerate(pending) if all(parent in known for parent in step.input_revisions)),
                None,
            )
            if index is None:
                raise ValueError("History rewrite would create a dangling or cyclic dependency.")
            step = pending.pop(index)
            ordered.append(step)
            known.add(step.output_revision)
        self._steps = ordered

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
            self.notes.pop(step_id, None)
            self.report_selection.pop(step_id, None)
        for choices in self.report_selection.values():
            for step_id in step_ids:
                choices.pop(step_id, None)

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
