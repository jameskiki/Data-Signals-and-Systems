"""Tests for persisted shared UI state."""

from Source.shared import ui_state


class FakeVar:
    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def test_ui_state_loads_legacy_plot_style_file(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_state.tk, "BooleanVar", FakeVar)
    monkeypatch.setattr(ui_state.tk, "DoubleVar", FakeVar)
    monkeypatch.setattr(ui_state.tk, "IntVar", FakeVar)
    monkeypatch.setattr(ui_state.tk, "StringVar", FakeVar)

    state_dir = tmp_path / ".evaldata"
    state_dir.mkdir()
    legacy_path = state_dir / "plot_style.json"
    legacy_path.write_text('{"table_backend": "tksheet", "show_grid": false}', encoding="utf-8")

    monkeypatch.setattr(ui_state.pathlib.Path, "home", lambda: tmp_path)

    loaded = ui_state.UiStateVars()
    loaded.load_from_file(legacy_path)

    assert loaded.show_grid.get() is False