"""Versioned embedded project snapshots, saved without replacing live app state."""

import io
import json
import os
import tempfile
import zipfile
import hashlib
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from Source.shared.operation_history import OperationHistory
from .datasets import DatasetContext


@dataclass
class ProjectSnapshot:
    data_frames: dict[str, pd.DataFrame]
    dataset_contexts: dict[str, DatasetContext]
    history: OperationHistory


def _write_frame(archive: zipfile.ZipFile, name: str, frame: pd.DataFrame) -> str:
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=True), buffer, compression="snappy")
    payload = buffer.getvalue()
    archive.writestr(name, payload)
    return hashlib.sha256(payload).hexdigest()


def _read_frame(archive: zipfile.ZipFile, item: dict) -> pd.DataFrame:
    payload = archive.read(item["file"])
    if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
        raise ValueError("Project dataset/result checksum does not match.")
    return pq.read_table(io.BytesIO(payload)).to_pandas()


def read_app_version() -> str:
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def save_project(path: str, snapshot: ProjectSnapshot) -> None:
    """Write a temporary archive and atomically replace the destination on success."""
    if snapshot.data_frames.keys() != snapshot.dataset_contexts.keys():
        raise ValueError("Project datasets and contexts do not match.")
    manifest = {
        "format": "evaldata-project", "schema_version": 1,
        "history": [asdict(step) for step in snapshot.history.steps],
        "notes": dict(snapshot.history.notes),
        "report_selection": snapshot.history.report_selection,
        "datasets": [], "artifacts": [],
        "limitations": ["No unpublished workspace data, window layouts, or operation replay."],
        "versions": {
            "app": read_app_version(),
            "python": sys.version.split()[0], "pandas": pd.__version__, "pyarrow": pa.__version__,
        },
    }
    descriptor, temporary = tempfile.mkstemp(prefix=".evaldata-", suffix=".tmp", dir=os.path.dirname(os.path.abspath(path)))
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for index, (label, frame) in enumerate(snapshot.data_frames.items()):
                context = snapshot.dataset_contexts[label]
                name = f"datasets/{index}.parquet"
                digest = _write_frame(archive, name, frame)
                manifest["datasets"].append({
                    "label": label, "file": name, "dataset_id": context.dataset_id,
                    "revision_id": context.revision_id, "source_paths": context.source_paths,
                    "description": context.description, "column_roles": context.column_roles,
                    "sha256": digest,
                    "display_name": context.display_name,
                })
            for index, (step_id, tables) in enumerate(snapshot.history.artifact_tables.items()):
                for table_index, (table_name, frame) in enumerate(tables.items()):
                    name = f"artifacts/{index}-{table_index}.parquet"
                    digest = _write_frame(archive, name, frame)
                    manifest["artifacts"].append({"step_id": step_id, "table": table_name, "file": name, "sha256": digest})
            archive.writestr("manifest.json", json.dumps(manifest, allow_nan=False))
        load_project(temporary)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def load_project(path: str) -> ProjectSnapshot:
    """Validate the full project before returning any replacement state."""
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("format") != "evaldata-project" or manifest.get("schema_version") != 1:
            raise ValueError("Unsupported EvalData project format or schema version.")
        if not all(isinstance(manifest.get(key), list) for key in ("history", "datasets", "artifacts")):
            raise ValueError("Invalid project manifest collections.")
        history = OperationHistory.from_steps(manifest["history"])
        known_revisions = {step.output_revision for step in history.steps}
        step_ids = {step.id for step in history.steps}
        notes = manifest.get("notes", {})
        if not isinstance(notes, dict) or not all(
            isinstance(key, str) and key in step_ids and isinstance(value, str) for key, value in notes.items()
        ):
            raise ValueError("Invalid project decision notes.")
        history.notes.update(notes)
        choices = manifest.get("report_selection", {})
        if not isinstance(choices, dict):
            raise ValueError("Invalid project report selection.")
        for publish_id, overrides in choices.items():
            if not isinstance(overrides, dict):
                raise ValueError("Invalid project report selection.")
            history.report_candidates(publish_id)
            for step_id, enabled in overrides.items():
                history.set_report_node_enabled(publish_id, step_id, enabled)
        frames: dict[str, pd.DataFrame] = {}
        contexts: dict[str, DatasetContext] = {}
        dataset_ids: set[str] = set()
        for item in manifest["datasets"]:
            if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("label", "file", "dataset_id", "description")):
                raise ValueError("Invalid project dataset fields.")
            label = item["label"]
            revision = item.get("revision_id")
            roles = item.get("column_roles")
            sources = item.get("source_paths")
            display_name = item.get("display_name", "")
            if not isinstance(display_name, str):
                raise ValueError("Invalid project dataset display name.")
            if label in frames or item["dataset_id"] in dataset_ids or revision not in known_revisions:
                raise ValueError("Invalid project dataset identity or revision.")
            if not isinstance(roles, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in roles.items()):
                raise ValueError("Invalid project column roles.")
            if not isinstance(sources, list) or not all(isinstance(source, str) for source in sources):
                raise ValueError("Invalid project source paths.")
            frames[label] = _read_frame(archive, item)
            contexts[label] = DatasetContext(
                source_paths=sources, description=item["description"], column_roles=roles,
                revision_id=revision, dataset_id=item["dataset_id"],
                display_name=display_name,
            )
            dataset_ids.add(item["dataset_id"])
        for item in manifest["artifacts"]:
            if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("step_id", "table", "file")):
                raise ValueError("Invalid project result table.")
            if item["step_id"] not in step_ids:
                raise ValueError("Result table references unknown history step.")
            tables = history.artifact_tables.setdefault(item["step_id"], {})
            if item["table"] in tables:
                raise ValueError("Duplicate project result table.")
            tables[item["table"]] = _read_frame(archive, item)
        for step in history.steps:
            expected = json.loads(step.parameters_json).get("result_tables", [])
            if set(expected) != set(history.artifact_tables.get(step.id, {})):
                raise ValueError("Project analysis result tables are incomplete.")
    return ProjectSnapshot(frames, contexts, history)
