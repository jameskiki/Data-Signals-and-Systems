"""Focused tests for datapreparation row-range filtering and span callbacks."""

from types import SimpleNamespace

import matplotlib.dates as mdates
import pandas as pd

from Source.datapreparation_app import app as dataprep_app


class DummyNotifications:
    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, message: str):
        self.warnings.append(message)


class RangeHarness:
    def __init__(self):
        self.notifications = DummyNotifications()
        self.data_frames: dict[str, pd.DataFrame] = {}
        self.dataset_contexts: dict[str, SimpleNamespace] = {}
        self.session = SimpleNamespace(row_range_start="", row_range_end="")
        self.selected_path: str | None = None
        self._row_range_update_in_progress = False

    def _set_row_range_values(self, start_text: str, end_text: str, *, update_vars: bool = True) -> None:
        _ = update_vars
        self.session.row_range_start = start_text
        self.session.row_range_end = end_text

    def _get_single_selected_file_path(self):
        return self.selected_path

    def _get_time_column(self, column_roles: dict[str, str]) -> str | None:
        for column_name, role in column_roles.items():
            if role == "time":
                return column_name
        return None

    def _get_row_range_filtered_frame(self, dataframe: pd.DataFrame, _column_roles: dict[str, str]) -> pd.DataFrame:
        return dataframe.iloc[:1].reset_index(drop=True)

    def _coerce_datetime_range_value(self, raw_value: str):
        return dataprep_app.DataPreparationApp._coerce_datetime_range_value(self, raw_value)

    def _format_span_time_value(self, span_value: float):
        return dataprep_app.DataPreparationApp._format_span_time_value(self, span_value)


def test_filter_by_time_range_numeric_bounds():
    harness = RangeHarness()
    dataframe = pd.DataFrame({"time_s": [0.0, 0.5, 1.0, 1.5, 2.0], "value": [0, 1, 2, 3, 4]})

    filtered = dataprep_app.DataPreparationApp._filter_by_time_range(harness, dataframe, "time_s", "0.5", "1.5")

    assert filtered["time_s"].tolist() == [0.5, 1.0, 1.5]
    assert harness.notifications.warnings == []


def test_filter_by_time_range_datetime_iso_bounds():
    harness = RangeHarness()
    dataframe = pd.DataFrame(
        {
            "time_s": pd.date_range("2026-01-01 00:00:00", periods=5, freq="h"),
            "value": [0, 1, 2, 3, 4],
        }
    )

    filtered = dataprep_app.DataPreparationApp._filter_by_time_range(
        harness,
        dataframe,
        "time_s",
        "2026-01-01 01:00:00",
        "2026-01-01 03:00:00",
    )

    assert len(filtered) == 3
    assert filtered["value"].tolist() == [1, 2, 3]
    assert harness.notifications.warnings == []


def test_filter_by_time_range_datetime_matplotlib_number_bounds():
    harness = RangeHarness()
    dataframe = pd.DataFrame(
        {
            "time_s": pd.date_range("2026-01-01 00:00:00", periods=5, freq="h"),
            "value": [0, 1, 2, 3, 4],
        }
    )

    start_value = mdates.date2num(dataframe["time_s"].iloc[1].to_pydatetime())
    end_value = mdates.date2num(dataframe["time_s"].iloc[3].to_pydatetime())
    filtered = dataprep_app.DataPreparationApp._filter_by_time_range(
        harness,
        dataframe,
        "time_s",
        str(start_value),
        str(end_value),
    )

    assert len(filtered) == 3
    assert filtered["value"].tolist() == [1, 2, 3]
    assert harness.notifications.warnings == []


def test_set_row_range_from_span_datetime_updates_entries_and_table(monkeypatch):
    harness = RangeHarness()
    source_path = "demo"
    dataframe = pd.DataFrame(
        {
            "time_s": pd.date_range("2026-01-01 00:00:00", periods=6, freq="h"),
            "value": [0, 1, 2, 3, 4, 5],
        }
    )
    harness.data_frames[source_path] = dataframe
    harness.dataset_contexts[source_path] = SimpleNamespace(column_roles={"time_s": "time", "value": "signal"})
    harness.selected_path = source_path

    table_refreshes: list[pd.DataFrame] = []
    monkeypatch.setattr(
        dataprep_app,
        "refresh_preview_table",
        lambda _app, preview_frame, _row_limit, _column_roles: table_refreshes.append(preview_frame),
    )

    start_value = mdates.date2num(dataframe["time_s"].iloc[1].to_pydatetime())
    end_value = mdates.date2num(dataframe["time_s"].iloc[4].to_pydatetime())

    dataprep_app.DataPreparationApp._set_row_range_from_span(harness, end_value, start_value)

    start_text = harness.session.row_range_start
    end_text = harness.session.row_range_end
    assert pd.to_datetime(start_text) <= pd.to_datetime(end_text)
    assert len(table_refreshes) == 1
