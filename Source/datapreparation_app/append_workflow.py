"""Explicit append/reapply workflow for a narrow, verified processing recipe."""

import json
import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from Source.data_ops.filtering import apply_simple_filter
from Source.data_ops.models import SIGNAL_FILTER_OPERATIONS
from Source.data_ops.signals import add_derived_column, apply_signal_filter
from Source.data_ops.time_axis import reference_axis_seconds
from Source.shared.column_roles import get_transformed_column_role, update_projected_column_roles
from Source.shared.operation_history import HistoryStep
from .datasets import build_virtual_dataset_path, collect_source_paths, register_dataset


DERIVED_OPERATIONS = {
    "delta", "ratio", "rolling_mean", "derivative", "normalized", "detrend",
    "integrate", "rms_envelope", "hilbert_envelope",
}


@dataclass(frozen=True)
class AppendPlan:
    target_path: str
    raw_path: str
    incoming_path: str
    operations: tuple[HistoryStep, ...]
    time_column: str
    warnings: tuple[str, ...]
    input_fingerprints: tuple[str, str, str]
    added_columns: tuple[str, ...]


def _frame_fingerprint(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes())
    digest.update(repr(list(zip(frame.columns, frame.dtypes.astype(str)))).encode("utf-8"))
    return digest.hexdigest()


def _compatible_dtype(old_dtype, new_dtype) -> bool:
    if old_dtype == new_dtype:
        return True
    if pd.api.types.is_datetime64_any_dtype(old_dtype) and pd.api.types.is_datetime64_any_dtype(new_dtype):
        return getattr(old_dtype, "tz", None) == getattr(new_dtype, "tz", None)
    if (
        pd.api.types.is_integer_dtype(old_dtype) and pd.api.types.is_integer_dtype(new_dtype)
        or pd.api.types.is_bool_dtype(old_dtype) and pd.api.types.is_bool_dtype(new_dtype)
    ):
        return getattr(old_dtype, "numpy_dtype", old_dtype) == getattr(new_dtype, "numpy_dtype", new_dtype)
    return False


def _combined_raw(old: pd.DataFrame, new: pd.DataFrame, added_columns: tuple[str, ...]) -> pd.DataFrame:
    incoming = new.copy(deep=False)
    for column in added_columns:
        dtype = incoming[column].dtype
        if pd.api.types.is_bool_dtype(dtype):
            incoming[column] = incoming[column].astype("boolean")
        elif pd.api.types.is_integer_dtype(dtype):
            bits = getattr(dtype, "numpy_dtype", dtype).itemsize * 8
            prefix = "UInt" if pd.api.types.is_unsigned_integer_dtype(dtype) else "Int"
            incoming[column] = incoming[column].astype(f"{prefix}{bits}")
    return pd.concat([old, incoming], ignore_index=True, sort=False)


def _creators(history) -> dict[str, HistoryStep]:
    return {
        step.output_revision: step for step in history.steps
        if step.output_revision not in step.input_revisions
    }


def _recipe(app, path: str) -> tuple[str, tuple[HistoryStep, ...]]:
    creators = _creators(app.operation_history)
    revision = app.dataset_contexts[path].revision_id
    operations: list[HistoryStep] = []
    visited: set[str] = set()
    while revision not in visited:
        visited.add(revision)
        step = creators.get(revision)
        if step is None or not step.tracked:
            raise ValueError("Incomplete/untracked history: cannot safely infer processing to reapply.")
        if step.operation in {"load_file", "load_demo", "append_raw"}:
            candidates = [
                key for key, context in app.dataset_contexts.items()
                if context.revision_id == revision
            ]
            if not candidates:
                raise ValueError("The original raw dataset is no longer in the project. Reload/reopen it first.")
            return candidates[0], tuple(reversed(operations))
        if step.operation == "publish" and len(step.input_revisions) == 1:
            # Publishing snapshots the working data without transforming it.
            revision = step.input_revisions[0]
            continue
        supported = step.operation in SIGNAL_FILTER_OPERATIONS or step.operation == "simple_filter"
        supported = supported or (
            step.operation.startswith("derived_") and step.operation[8:] in DERIVED_OPERATIONS
        )
        if not supported or len(step.input_revisions) != 1:
            raise ValueError(
                f"Cannot reapply '{step.operation}'. This prototype supports filters and derived signals only; "
                "preparation ranges, splits/merges, resampling, resets and manual selections require a new explicit recipe."
            )
        operations.append(step)
        revision = step.input_revisions[0]
    raise ValueError("Cyclic processing history.")


def replay_operation(frame: pd.DataFrame, roles: dict[str, str], step: HistoryStep) -> tuple[pd.DataFrame, dict[str, str]]:
    parameters = json.loads(step.parameters_json)
    required = {"source_column", "output_column"}
    if step.operation == "simple_filter":
        required.update({"minimum", "maximum", "keep_missing"})
    elif step.operation in {"moving_average", "median", "high_pass"}:
        required.add("window_size")
    elif step.operation == "exponential_smoothing":
        required.add("alpha")
    elif step.operation.startswith("butterworth"):
        required.update({"cutoff_hz", "sample_spacing", "filter_order"})
    elif step.operation.startswith("derived_"):
        required.update({"reference_column", "window_size"})
    if not required.issubset(parameters):
        raise ValueError(f"Incomplete parameters for '{step.operation}'; automatic reapplication is blocked.")
    source = parameters["source_column"]
    output = parameters["output_column"]
    if step.operation == "simple_filter":
        result = apply_simple_filter(
            frame, source, output, parameters["minimum"], parameters["maximum"], parameters["keep_missing"],
        )
    elif step.operation in SIGNAL_FILTER_OPERATIONS:
        result = apply_signal_filter(
            frame, source, step.operation, output,
            window_size=parameters.get("window_size", 5), alpha=parameters.get("alpha", 0.2),
            cutoff_hz=parameters.get("cutoff_hz", 1.0), sample_spacing=parameters.get("sample_spacing", 0.0),
            filter_order=parameters.get("filter_order", 4),
        )
    elif step.operation.startswith("derived_") and step.operation[8:] in DERIVED_OPERATIONS:
        result = add_derived_column(
            frame, step.operation[8:], source, output,
            second_column=parameters["reference_column"], window_size=parameters["window_size"],
        )
    else:
        raise ValueError(f"Unsupported recipe operation: {step.operation}")
    return result, update_projected_column_roles(
        roles, result, {output.strip(): get_transformed_column_role(roles, source)},
    )


def plan_append(app, target_path: str, incoming_path: str) -> AppendPlan:
    if target_path == incoming_path:
        raise ValueError("Select a different incoming dataset.")
    raw_path, operations = _recipe(app, target_path)
    incoming_raw, incoming_operations = _recipe(app, incoming_path)
    if incoming_operations or incoming_raw != incoming_path:
        raise ValueError("Incoming data must be raw, not an already processed dataset.")
    old = app.data_frames[raw_path]
    new = app.data_frames[incoming_path]
    if old.empty or new.empty:
        raise ValueError("Both raw datasets must contain rows.")
    if not old.columns.is_unique or not new.columns.is_unique:
        raise ValueError("Raw datasets must have unique column names.")
    missing = [column for column in old.columns if column not in new.columns]
    if missing:
        raise ValueError("Incoming dataset is missing existing columns: " + ", ".join(map(str, missing)))
    added_columns = tuple(column for column in new.columns if column not in old.columns)
    recipe_outputs = {json.loads(step.parameters_json).get("output_column") for step in operations}
    collisions = recipe_outputs.intersection(added_columns)
    if collisions:
        raise ValueError("New columns conflict with processing output names: " + ", ".join(sorted(collisions)))
    mismatches = [
        f"{column}: existing {old[column].dtype}, incoming {new[column].dtype}"
        for column in old.columns if not _compatible_dtype(old[column].dtype, new[column].dtype)
    ]
    if mismatches:
        raise ValueError(
            "Raw column types differ:\n" + "\n".join(mismatches)
            + "\nConvert these columns to matching types before appending. "
            "Equivalent datetime storage resolutions are allowed."
        )
    roles = app.dataset_contexts[raw_path].column_roles
    time_columns = [column for column, role in roles.items() if role == "time" and column in old.columns]
    if len(time_columns) != 1:
        raise ValueError("Assign exactly one time column on the raw source before appending.")
    time_column = time_columns[0]
    if app.dataset_contexts[incoming_path].column_roles.get(time_column) != "time":
        raise ValueError("Incoming data must use the same time-column role.")
    for column in added_columns:
        if app.dataset_contexts[incoming_path].column_roles.get(column) == "time":
            raise ValueError(f"New column '{column}' is marked as another time axis. Assign a non-time role first.")
    old_time = reference_axis_seconds(old[time_column])
    new_time = reference_axis_seconds(new[time_column])
    for values in (old_time, new_time):
        if not np.isfinite(values.to_numpy(dtype=float)).all() or not values.diff().dropna().gt(0).all():
            raise ValueError("Time values must be finite, unique, and strictly increasing within each input.")
    boundary = float(new_time.iloc[0] - old_time.iloc[-1])
    if boundary <= 0:
        raise ValueError("Incoming timestamps overlap or precede the existing run. Overlaps are not deduplicated.")
    warnings: list[str] = []
    spacings = [values.diff().dropna().to_numpy(dtype=float) for values in (old_time, new_time)]
    diffs = np.concatenate(spacings)
    if diffs.size:
        typical = float(np.median(diffs))
        if boundary > typical and not np.isclose(boundary, typical, rtol=1e-6, atol=1e-9):
            warnings.append(f"Time gap at append boundary: {boundary:g} seconds (typical spacing {typical:g}).")
        elif not np.isclose(boundary, typical, rtol=1e-6, atol=1e-9):
            warnings.append(f"Spacing changes at append boundary: {boundary:g} seconds (typical {typical:g}).")
        if not np.allclose(diffs, typical, rtol=1e-6, atol=1e-9):
            warnings.append("Input spacing is irregular or changes between files.")
    if warnings and operations:
        warnings.append("Filters/derived signals operate across gaps as adjacent rows; inspect the result carefully.")
    if added_columns:
        warnings.append(
            "New columns: " + ", ".join(added_columns)
            + ". Earlier rows will be missing; no processing is automatically added for these columns."
        )
    replayed = old
    replay_roles = dict(roles)
    for step in operations:
        replayed, replay_roles = replay_operation(replayed, replay_roles, step)
    try:
        pd.testing.assert_frame_equal(replayed, app.data_frames[target_path], check_flags=False)
    except AssertionError as error:
        raise ValueError("Recorded recipe no longer reproduces the selected dataset. Automatic reapplication is blocked.") from error
    return AppendPlan(
        target_path, raw_path, incoming_path, operations, time_column, tuple(warnings),
        tuple(_frame_fingerprint(app.data_frames[path]) for path in (raw_path, incoming_path, target_path)),
        added_columns,
    )


def execute_append(app, plan: AppendPlan) -> tuple[str, str]:
    # Revalidate at execution so a stale preview never authorizes different data.
    current = plan_append(app, plan.target_path, plan.incoming_path)
    if current != plan:
        raise ValueError("Append inputs changed after preview. Review the operation list again.")
    raw = _combined_raw(app.data_frames[plan.raw_path], app.data_frames[plan.incoming_path], plan.added_columns)
    processed = raw
    roles = dict(app.dataset_contexts[plan.raw_path].column_roles)
    incoming_roles = app.dataset_contexts[plan.incoming_path].column_roles
    for column in plan.added_columns:
        role = incoming_roles.get(column)
        if role == "time":
            raise ValueError(f"New column '{column}' is marked as another time axis. Assign a non-time role first.")
        if role is not None:
            roles[column] = role
    raw_roles = dict(roles)
    for step in plan.operations:
        processed, roles = replay_operation(processed, roles, step)
    raw_path = build_virtual_dataset_path(app.data_frames, plan.raw_path, "appended_raw")
    processed_path = build_virtual_dataset_path(app.data_frames, raw_path, "processed")
    parents = tuple(app.dataset_contexts[path].revision_id for path in (plan.raw_path, plan.incoming_path))
    if any(parent is None for parent in parents):
        raise ValueError("Append inputs are missing revision identities.")
    register_dataset(
        app, raw_path, raw, source_paths=collect_source_paths(app, [plan.raw_path, plan.incoming_path]),
        description="Combined raw inputs; previous datasets and snapshot results are unchanged.",
        column_roles=raw_roles,
        history_operation="append_raw", history_inputs=parents,
        history_parameters={
            "time_column": plan.time_column, "warnings": list(plan.warnings),
            "added_columns": list(plan.added_columns), "earlier_rows_missing": len(app.data_frames[plan.raw_path]),
        },
    )
    if not plan.operations:
        return raw_path, raw_path
    revision = app.dataset_contexts[raw_path].revision_id
    for step in plan.operations:
        revision = app.operation_history.record(
            step.operation, processed_path, (revision,), json.loads(step.parameters_json),
        )
    register_dataset(
        app, processed_path, processed, source_paths=collect_source_paths(app, [raw_path]),
        description=f"Reapplied {len(plan.operations)} processing operations to combined raw data.",
        column_roles=roles, history_operation="publish", history_inputs=(revision,),
    )
    return raw_path, processed_path
