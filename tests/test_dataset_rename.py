"""Display names change independently of paths, revisions, and dataframe data."""

from types import SimpleNamespace

import pandas as pd
import pytest

from Source.datapreparation_app.datasets import register_dataset, rename_dataset, dataset_display_name
from Source.datapreparation_app.project_io import ProjectSnapshot, save_project, load_project


def test_rename_preserves_identity_data_and_project_round_trip(tmp_path):
    app = SimpleNamespace(data_frames={}, dataset_contexts={})
    frame = pd.DataFrame({"signal": [1, 2]})
    register_dataset(app, "source.csv", frame, history_operation="load_file")
    context = app.dataset_contexts["source.csv"]
    identity = context.dataset_id, context.revision_id
    rename_dataset(app, "source.csv", "  Long-term run: day 1  ")
    assert dataset_display_name("source.csv", context) == "Long-term run: day 1"
    assert (context.dataset_id, context.revision_id) == identity
    assert app.data_frames["source.csv"] is frame
    assert app.operation_history.steps[-1].operation == "rename_dataset"
    path = str(tmp_path / "project.evaldata")
    save_project(path, ProjectSnapshot(app.data_frames, app.dataset_contexts, app.operation_history))
    restored = load_project(path)
    assert restored.dataset_contexts["source.csv"].display_name == "Long-term run: day 1"
    assert "source.csv" in restored.data_frames
    pd.testing.assert_frame_equal(restored.data_frames["source.csv"], frame)


@pytest.mark.parametrize("name", ["", "   ", "bad\nname"])
def test_invalid_rename_does_not_change_name_or_history(name):
    app = SimpleNamespace(data_frames={}, dataset_contexts={})
    register_dataset(app, "source.csv", pd.DataFrame({"signal": [1]}), history_operation="load_file")
    with pytest.raises(ValueError, match="non-empty"):
        rename_dataset(app, "source.csv", name)
    assert dataset_display_name("source.csv", app.dataset_contexts["source.csv"]) == "source.csv"
    assert len(app.operation_history.steps) == 1
