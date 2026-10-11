"""Semantic history colors use operation meaning, not just tracked status."""

import pytest

from Source.shared.operation_history import OperationHistory
from Source.datapreparation_app.history_view import history_category, HISTORY_COLORS


@pytest.mark.parametrize("operation,expected", [
    ("load_demo", "input"), ("append_raw", "input"), ("merge", "input"),
    ("moving_average", "processing"), ("derived_derivative", "processing"),
    ("apply_kept_cycles", "processing"), ("rename_dataset", "metadata"),
    ("assign_roles", "metadata"), ("publish", "published"),
])
def test_operation_color_category(operation, expected):
    history = OperationHistory()
    history.record(operation, "dataset")
    assert history_category(history.steps[-1], history) == expected
    assert expected in HISTORY_COLORS


def test_result_and_untracked_styles_have_priority():
    history = OperationHistory()
    history.record("FFT Amplitude", "dataset")
    step = history.steps[-1]
    history.artifact_tables[step.id] = {}
    assert history_category(step, history) == "snapshot"
    history.record("moving_average", "dataset", tracked=False)
    assert history_category(history.steps[-1], history) == "untracked"
