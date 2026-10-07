"""Copy-on-write isolation and demand-driven summary refresh tests."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from Source.analysis_app.app import AnalysisWorkspace
from Source.analysis_app import app as app_module
from Source.analysis_app.state import AnalysisSession
from Source.data_ops.filtering import apply_simple_filter
from Source.data_ops.signals import apply_signal_filter, add_derived_column
from Source.data_ops.summary import summarize_dataframe


@pytest.mark.parametrize("operation", ["simple", "moving_average", "derived"])
def test_transforms_share_unchanged_columns_but_isolate_mutations(operation):
    source = pd.DataFrame({"signal": [1.0, 2.0, 3.0], "other": [10.0, 20.0, 30.0]})
    if operation == "simple":
        result = apply_simple_filter(source, "signal", "result", minimum_value="2")
        expected = [np.nan, 2.0, 3.0]
    elif operation == "moving_average":
        result = apply_signal_filter(source, "signal", "moving_average", "result", window_size=3)
        expected = [1.5, 2.0, 2.5]
    else:
        result = add_derived_column(source, "delta", "signal", "result")
        expected = [np.nan, 1.0, 1.0]
    assert np.shares_memory(source["other"].to_numpy(), result["other"].to_numpy())
    np.testing.assert_allclose(result["result"], expected, equal_nan=True)
    result.loc[0, "other"] = -100
    assert source.loc[0, "other"] == 10
    source.loc[1, "signal"] = -200
    assert result.loc[1, "signal"] == 2


def test_overwriting_source_column_does_not_mutate_original():
    source = pd.DataFrame({"signal": [1.0, 2.0, 3.0]})
    result = apply_signal_filter(source, "signal", "moving_average", "signal", window_size=3)
    assert source["signal"].tolist() == [1.0, 2.0, 3.0]
    assert result["signal"].tolist() == [1.5, 2.0, 2.5]


def test_working_frame_replacement_shares_data_and_keeps_caller_isolated():
    workspace = AnalysisWorkspace.__new__(AnalysisWorkspace)
    frame = pd.DataFrame({"signal": [1.0, 2.0]})
    workspace.session = AnalysisSession("run", frame.copy(deep=False), frame.copy(deep=False))
    workspace.column_roles = {"signal": "signal"}
    workspace.fft_summary_var = SimpleNamespace(set=lambda _: None)
    workspace.cycle_summary_var = SimpleNamespace(set=lambda _: None)
    workspace._default_frequency_summary_text = lambda: ""
    for name in (
        "_update_frequency_diagnostics", "_clear_fft_results", "_clear_cycle_results",
        "_refresh_all_views", "_set_default_output_names", "_refresh_role_widget_styles",
        "_refresh_live_plot",
    ):
        setattr(workspace, name, lambda *args, **kwargs: None)
    update = frame.copy(deep=False)
    workspace._replace_working_frame(update)
    assert np.shares_memory(update["signal"].to_numpy(), workspace.session.working_frame["signal"].to_numpy())
    workspace.session.working_frame.loc[0, "signal"] = 100
    assert update.loc[0, "signal"] == 1
    assert workspace.session.original_frame.loc[0, "signal"] == 1
    assert workspace.session.working_revision == 1


def test_summary_details_computed_only_on_demand_and_cached_by_revision(monkeypatch):
    frame = pd.DataFrame({"signal": [1.0, 2.0], "other": [3.0, 4.0]})
    workspace = AnalysisWorkspace.__new__(AnalysisWorkspace)
    workspace.session = AnalysisSession("run", frame, frame.copy(deep=False))
    calls = []

    def summarize(dataframe, include_details=True):
        calls.append(include_details)
        return summarize_dataframe(dataframe, include_details=include_details)

    monkeypatch.setattr(app_module, "summarize_dataframe", summarize)
    workspace._ensure_current_summary(include_details=False)
    assert workspace.session.last_summary.statistics_frame.empty
    workspace._ensure_current_summary(include_details=False)
    workspace._ensure_current_summary()
    assert not workspace.session.last_summary.statistics_frame.empty
    workspace._ensure_current_summary()
    workspace._ensure_current_summary(include_details=False)
    assert calls == [False, True]
    workspace.session.working_revision += 1
    workspace._ensure_current_summary(include_details=False)
    assert calls == [False, True, False]
    assert workspace.session.last_summary_has_details is False


def test_statistics_tab_selection_requests_details():
    workspace = AnalysisWorkspace.__new__(AnalysisWorkspace)
    workspace.statistics_tab = "statistics"
    workspace.notebook = SimpleNamespace(select=lambda: "filter")
    calls = []
    workspace._refresh_summary_views = lambda: calls.append(True)
    workspace._handle_analysis_tab_changed()
    assert calls == []
    workspace.notebook.select = lambda: "statistics"
    workspace._handle_analysis_tab_changed()
    assert calls == [True]


def test_statistics_values_match_previous_full_resolution_contract():
    frame = pd.DataFrame({
        "a": [1.0, np.nan, 3.0, 4.0],
        "b": [5.0, 7.0, 9.0, 11.0],
        "empty": [np.nan] * 4,
        "single": [2.0, np.nan, np.nan, np.nan],
    })
    result = summarize_dataframe(frame)
    description = frame.describe()
    for column in frame.columns:
        row = result.statistics_frame.loc[column]
        assert row["count"] == description.loc["count", column]
        assert row["missing"] == frame[column].isna().sum()
        if row["count"]:
            assert row["min"] == description.loc["min", column]
            assert row["max"] == description.loc["max", column]
            assert row["mean"] == description.loc["mean", column]
            assert row["std"] == (description.loc["std", column] if row["count"] > 1 else 0)
            assert row["rms"] == np.sqrt((frame[column] ** 2).mean())
    pd.testing.assert_frame_equal(result.correlation_frame, frame.corr())
