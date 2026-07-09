"""Runtime path and migration helpers used by packaged and local app launches."""

from __future__ import annotations

import os
import pathlib
import shutil


APP_DIR_NAME = "EvalData"


def _is_windows() -> bool:
    return os.name == "nt"


def _windows_appdata_base_dir() -> pathlib.Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return pathlib.Path(appdata)
    return pathlib.Path.home() / "AppData" / "Roaming"


def get_legacy_state_dir() -> pathlib.Path:
    return pathlib.Path.home() / ".evaldata"


def get_legacy_cache_dir() -> pathlib.Path:
    return pathlib.Path.home() / ".evaldata_cache"


def get_state_dir() -> pathlib.Path:
    if _is_windows():
        return _windows_appdata_base_dir() / APP_DIR_NAME
    return get_legacy_state_dir()


def get_matplotlib_cache_dir() -> pathlib.Path:
    if _is_windows():
        return get_state_dir() / "cache" / "matplotlib"
    return get_legacy_cache_dir() / "matplotlib"


def _copy_tree_non_destructive(source: pathlib.Path, destination: pathlib.Path) -> None:
    if not source.exists() or not source.is_dir():
        return

    for item in source.rglob("*"):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not item.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(item, target)


def migrate_legacy_user_data() -> None:
    target_state = get_state_dir()
    target_state.mkdir(parents=True, exist_ok=True)

    if not _is_windows():
        return

    legacy_state = get_legacy_state_dir()
    if legacy_state.exists():
        _copy_tree_non_destructive(legacy_state, target_state)

    legacy_matplotlib_cache = get_legacy_cache_dir() / "matplotlib"
    if legacy_matplotlib_cache.exists():
        _copy_tree_non_destructive(legacy_matplotlib_cache, get_matplotlib_cache_dir())


def configure_runtime_environment() -> None:
    """Prepare migration-safe runtime paths before importing plotting modules."""

    migrate_legacy_user_data()
    matplotlib_cache = get_matplotlib_cache_dir()
    matplotlib_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))
