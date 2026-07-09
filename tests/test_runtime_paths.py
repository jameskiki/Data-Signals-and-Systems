"""Tests for runtime path migration and environment setup helpers."""

from __future__ import annotations

from Source.shared import runtime_paths


def test_get_state_dir_uses_appdata_on_windows(monkeypatch, tmp_path):
    appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setattr(runtime_paths, "_is_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(appdata))

    assert runtime_paths.get_state_dir() == appdata / "EvalData"


def test_migrate_legacy_user_data_copies_files_without_overwrite(monkeypatch, tmp_path):
    home_dir = tmp_path / "home"
    appdata = tmp_path / "AppData" / "Roaming"
    legacy_state = home_dir / ".evaldata"
    legacy_cache = home_dir / ".evaldata_cache" / "matplotlib"

    legacy_state.mkdir(parents=True)
    legacy_cache.mkdir(parents=True)
    (legacy_state / "ui_state.json").write_text('{"show_grid": false}', encoding="utf-8")
    (legacy_cache / "fontlist-v390.json").write_text("legacy-cache", encoding="utf-8")

    target_state = appdata / "EvalData"
    target_state.mkdir(parents=True)
    (target_state / "ui_state.json").write_text('{"show_grid": true}', encoding="utf-8")

    monkeypatch.setattr(runtime_paths.pathlib.Path, "home", lambda: home_dir)
    monkeypatch.setattr(runtime_paths, "_is_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(appdata))

    runtime_paths.migrate_legacy_user_data()

    assert (target_state / "ui_state.json").read_text(encoding="utf-8") == '{"show_grid": true}'
    assert (target_state / "cache" / "matplotlib" / "fontlist-v390.json").exists()


def test_configure_runtime_environment_sets_mplconfigdir(monkeypatch, tmp_path):
    appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setattr(runtime_paths, "_is_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)

    runtime_paths.configure_runtime_environment()

    expected_dir = appdata / "EvalData" / "cache" / "matplotlib"
    assert expected_dir.exists()
    assert runtime_paths.os.environ["MPLCONFIGDIR"] == str(expected_dir)
