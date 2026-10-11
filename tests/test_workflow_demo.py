"""End-to-end workflow demo: load -> decision -> pipeline -> appends -> results -> report."""

import json

from Source.datapreparation_app.project_io import load_project
from Source.datapreparation_app.workflow_demo import create_workflow_demo_project
from Source.shared import longterm_demo
from Source.shared.operation_history import before_append_step


def test_workflow_demo_project_covers_load_to_report(tmp_path):
    demo = create_workflow_demo_project(str(tmp_path))
    snapshot = load_project(demo.project_path)
    history = snapshot.history
    operations = [step.operation for step in history.steps]
    assert operations.count("load_file") == 3
    assert operations.count("append_raw") == 2
    assert operations.count("publish") == 2
    assert operations.index("append_raw") < operations.index("moving_average")
    marked = [step.operation for step in history.steps if before_append_step(step)]
    assert marked == ["cycle_analysis"]
    raw_fft = next(step for step in history.steps if step.operation == "FFT Amplitude")
    assert "Decision" in history.notes[raw_fft.id]
    report_label = next(step.label for step in reversed(history.steps) if step.operation == "publish")
    assert len(snapshot.data_frames[report_label]) == 3 * longterm_demo.DAILY_SAMPLE_COUNT
    slow = next(step for step in history.steps if step.operation == "Cycle Analysis (12-hour measurement)")
    parameters = json.loads(slow.parameters_json)
    assert parameters["cycle_length"] == 43_200
    assert parameters["cycle_count"] == 6
    assert parameters["source_column"] == "measurement_detrended"
    assert parameters["dropped_rows"] == 0
    publish = next(step for step in reversed(history.steps) if step.operation == "publish")
    assert slow.id in json.loads(publish.parameters_json)["workspace_steps"]
    assert slow.id in history.artifact_tables
    content = open(demo.report_path, encoding="utf-8").read()
    for text in ("Decision Trail", "Result #", "View #", "Evidence #", "Long-term run - report", "Evidence based on"):
        assert text in content
    assert "Cycle Analysis (12-hour measurement)" in content
    assert "does not isolate it" in content
