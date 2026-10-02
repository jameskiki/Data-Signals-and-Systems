"""Tests for shared.column_roles — role inference and column utilities."""

import pandas as pd

from Source.shared.column_roles import (
    get_available_column_roles,
    get_column_role,
    get_column_role_cell_colors,
    get_column_role_colors,
    get_column_role_label,
    get_preferred_role_column,
    get_role_label,
    get_transformed_column_role,
    infer_column_roles,
    infer_non_time_column_role,
    project_column_roles,
    sort_columns_by_role,
    summarize_column_roles,
    update_projected_column_roles,
)


# ── infer_column_roles ─────────────────────────────────────────────────────────


class TestInferColumnRoles:
    def test_time_column_by_name(self):
        df = pd.DataFrame({"time_s": [0.0, 1.0], "value": [1.0, 2.0]})
        roles = infer_column_roles(df)
        assert roles["time_s"] == "time"

    def test_timestamp_column_by_name(self):
        df = pd.DataFrame({"timestamp": [0.0, 1.0], "value": [1.0, 2.0]})
        roles = infer_column_roles(df)
        assert roles["timestamp"] == "time"

    def test_datetime_dtype_inferred_as_time(self):
        df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01", "2024-01-02"]), "x": [1, 2]})
        roles = infer_column_roles(df)
        assert roles["ts"] == "time"

    def test_input_and_output_columns_are_signals(self):
        df = pd.DataFrame({"input_voltage": [1.0], "output_current": [2.0]})
        roles = infer_column_roles(df)
        assert roles["input_voltage"] == "signal"
        assert roles["output_current"] == "signal"

    def test_numeric_response_column_is_signal(self):
        df = pd.DataFrame({"response_y": [1.0]})
        roles = infer_column_roles(df)
        assert roles["response_y"] == "signal"

    def test_metadata_column_by_name(self):
        df = pd.DataFrame({"status": ["ok"], "label": ["a"]})
        roles = infer_column_roles(df)
        assert roles["status"] == "metadata"
        assert roles["label"] == "metadata"

    def test_numeric_unknown_column_defaults_to_signal(self):
        df = pd.DataFrame({"sensor_42": [1.0, 2.0]})
        roles = infer_column_roles(df)
        assert roles["sensor_42"] == "signal"

    def test_non_numeric_unknown_column_defaults_to_metadata(self):
        df = pd.DataFrame({"category": ["a", "b"]})
        roles = infer_column_roles(df)
        assert roles["category"] == "metadata"

    def test_preferred_roles_take_precedence(self):
        df = pd.DataFrame({"time_s": [0.0], "sensor": [1.0]})
        roles = infer_column_roles(df, preferred_roles={"time_s": "signal"})
        assert roles["time_s"] == "signal"

    def test_legacy_preferred_role_is_reinferred(self):
        df = pd.DataFrame({"sensor": [1.0, 2.0]})
        roles = infer_column_roles(df, preferred_roles={"sensor": "output"})
        assert roles["sensor"] == "signal"

    def test_all_columns_are_covered(self):
        df = pd.DataFrame({"a": [1], "b": ["x"], "c": pd.to_datetime(["2024-01-01"])})
        roles = infer_column_roles(df)
        assert set(roles.keys()) == {"a", "b", "c"}


# ── project_column_roles ──────────────────────────────────────────────────────


class TestProjectColumnRoles:
    def test_preserves_known_roles(self):
        df = pd.DataFrame({"time_s": [0.0], "sensor": [1.0]})
        original = {"time_s": "time", "sensor": "signal"}
        projected = project_column_roles(original, df)
        assert projected["time_s"] == "time"
        assert projected["sensor"] == "signal"

    def test_drops_roles_for_removed_columns(self):
        df = pd.DataFrame({"time_s": [0.0]})
        original = {"time_s": "time", "old_col": "signal"}
        projected = project_column_roles(original, df)
        assert "old_col" not in projected

    def test_new_columns_are_inferred(self):
        df = pd.DataFrame({"time_s": [0.0], "new_sensor": [1.0]})
        original = {"time_s": "time"}
        projected = project_column_roles(original, df)
        assert "new_sensor" in projected


# ── update_projected_column_roles ─────────────────────────────────────────────


class TestUpdateProjectedColumnRoles:
    def test_overrides_are_applied(self):
        df = pd.DataFrame({"time_s": [0.0], "sensor": [1.0]})
        original = {"time_s": "time", "sensor": "signal"}
        updated = update_projected_column_roles(original, df, role_overrides={"sensor": "metadata"})
        assert updated["sensor"] == "metadata"

    def test_override_for_missing_column_is_ignored(self):
        df = pd.DataFrame({"time_s": [0.0]})
        original = {"time_s": "time"}
        updated = update_projected_column_roles(original, df, role_overrides={"ghost_col": "signal"})
        assert "ghost_col" not in updated

    def test_legacy_override_is_ignored(self):
        df = pd.DataFrame({"sensor": [1.0]})
        updated = update_projected_column_roles({"sensor": "signal"}, df, {"sensor": "output"})
        assert updated["sensor"] == "signal"


# ── summarize_column_roles ────────────────────────────────────────────────────


class TestSummarizeColumnRoles:
    def test_empty_roles_returns_empty_string(self):
        assert summarize_column_roles({}) == ""

    def test_time_appears_in_summary(self):
        roles = {"time_s": "time", "sensor": "signal"}
        summary = summarize_column_roles(roles)
        assert "time=time_s" in summary

    def test_many_signals_truncated(self):
        roles = {f"sig_{i}": "signal" for i in range(5)}
        summary = summarize_column_roles(roles)
        assert "+2 more" in summary

    def test_metadata_count_shown(self):
        roles = {"a": "metadata", "b": "metadata"}
        summary = summarize_column_roles(roles)
        assert "metadata=2" in summary


# ── get_preferred_role_column ─────────────────────────────────────────────────


class TestGetPreferredRoleColumn:
    def test_returns_first_match(self):
        roles = {"t": "time", "s": "signal"}
        assert get_preferred_role_column(roles, "time") == "t"

    def test_returns_none_when_no_match(self):
        roles = {"s": "signal"}
        assert get_preferred_role_column(roles, "time") is None

    def test_filters_by_available_columns(self):
        roles = {"t": "time", "s": "signal"}
        result = get_preferred_role_column(roles, "time", available_columns=["s"])
        assert result is None


# ── get_column_role ───────────────────────────────────────────────────────────


class TestGetColumnRole:
    def test_returns_stored_role(self):
        assert get_column_role({"col": "signal"}, "col") == "signal"

    def test_defaults_to_metadata_for_unknown(self):
        assert get_column_role({}, "unknown_col") == "metadata"

    def test_legacy_role_defaults_to_metadata(self):
        assert get_column_role({"col": "output"}, "col") == "metadata"


class TestGetTransformedColumnRole:
    def test_time_source_produces_signal(self):
        assert get_transformed_column_role({"time_s": "time"}, "time_s") == "signal"

    def test_metadata_source_stays_metadata(self):
        assert get_transformed_column_role({"label": "metadata"}, "label") == "metadata"


# ── get_column_role_label ─────────────────────────────────────────────────────


class TestGetColumnRoleLabel:
    def test_known_role_returns_label(self):
        assert get_column_role_label({"col": "time"}, "col") == "TIME"

    def test_unknown_role_uppercased(self):
        assert get_column_role_label({}, "x") == "META"


# ── get_role_label ────────────────────────────────────────────────────────────


class TestGetRoleLabel:
    def test_all_standard_roles(self):
        for role in ("time", "signal", "metadata"):
            label = get_role_label(role)
            assert label == role.upper() or label in ("META",)

    def test_unknown_role_uppercased(self):
        assert get_role_label("custom") == "CUSTOM"


# ── get_available_column_roles ────────────────────────────────────────────────


class TestGetAvailableColumnRoles:
    def test_returns_list_of_strings(self):
        roles = get_available_column_roles()
        assert isinstance(roles, list)
        assert all(isinstance(r, str) for r in roles)

    def test_includes_standard_roles(self):
        roles = get_available_column_roles()
        assert roles == ["time", "signal", "metadata"]


# ── get_column_role_colors ────────────────────────────────────────────────────


class TestGetColumnRoleColors:
    def test_returns_two_hex_strings(self):
        bg, fg = get_column_role_colors("time")
        assert bg.startswith("#") and fg.startswith("#")

    def test_unknown_role_returns_metadata_colors(self):
        assert get_column_role_colors("unknown") == get_column_role_colors("metadata")

    def test_cell_colors_lighter_than_base(self):
        bg_base, _ = get_column_role_colors("time")
        bg_cell, _ = get_column_role_cell_colors("time")
        # Cell background should be lighter (higher average channel value)
        def avg_channel(hex_color: str) -> float:
            c = hex_color.lstrip("#")
            return sum(int(c[i:i+2], 16) for i in (0, 2, 4)) / 3
        assert avg_channel(bg_cell) >= avg_channel(bg_base)


# ── sort_columns_by_role ──────────────────────────────────────────────────────


class TestSortColumnsByRole:
    def test_signal_before_metadata_before_time(self):
        roles = {"t": "time", "s": "signal", "m": "metadata"}
        assert sort_columns_by_role(["t", "s", "m"], roles) == ["s", "m", "t"]


class TestInferNonTimeColumnRole:
    def test_numeric_column_is_signal(self):
        assert infer_non_time_column_role(pd.Series([1.0, 2.0])) == "signal"

    def test_text_column_is_metadata(self):
        assert infer_non_time_column_role(pd.Series(["a", "b"])) == "metadata"

    def test_alphabetical_within_same_role(self):
        roles = {"b_sig": "signal", "a_sig": "signal"}
        sorted_cols = sort_columns_by_role(["b_sig", "a_sig"], roles)
        assert sorted_cols == ["a_sig", "b_sig"]
