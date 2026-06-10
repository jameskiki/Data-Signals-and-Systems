"""Architecture boundary tests for import direction and plotting layering."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Source"


def _iter_python_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.py") if path.name != "__init__.py")


def _parse_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _contains_module(imports: set[str], module_prefix: str) -> bool:
    return any(name == module_prefix or name.startswith(module_prefix + ".") for name in imports)


def test_data_ops_has_no_tk_or_app_imports() -> None:
    data_ops_dir = SOURCE_ROOT / "data_ops"
    for path in _iter_python_files(data_ops_dir):
        imports = _parse_imports(path)
        assert not _contains_module(imports, "tkinter"), f"{path.name} must not import tkinter"
        assert not _contains_module(imports, "Source.analysis_app"), f"{path.name} must not import analysis_app"
        assert not _contains_module(imports, "Source.datapreparation_app"), f"{path.name} must not import datapreparation_app"


def test_shared_plot_modules_have_no_tk_or_app_imports() -> None:
    shared_dir = SOURCE_ROOT / "shared"
    for module_name in ("plot_utils.py", "plot_options.py"):
        path = shared_dir / module_name
        imports = _parse_imports(path)
        assert not _contains_module(imports, "tkinter"), f"{module_name} must not import tkinter"
        assert not _contains_module(imports, "Source.analysis_app"), f"{module_name} must not import analysis_app"
        assert not _contains_module(imports, "Source.datapreparation_app"), f"{module_name} must not import datapreparation_app"


def test_analysis_app_does_not_import_datapreparation_app() -> None:
    analysis_dir = SOURCE_ROOT / "analysis_app"
    for path in _iter_python_files(analysis_dir):
        imports = _parse_imports(path)
        assert not _contains_module(imports, "Source.datapreparation_app"), (
            f"{path.name} must not import datapreparation_app"
        )


def test_dataprep_imports_analysis_only_from_actions_launch_boundary() -> None:
    dataprep_dir = SOURCE_ROOT / "datapreparation_app"
    for path in _iter_python_files(dataprep_dir):
        imports = _parse_imports(path)
        has_analysis_import = _contains_module(imports, "Source.analysis_app")
        if path.name == "actions.py":
            continue
        assert not has_analysis_import, f"{path.name} must not import analysis_app"


def test_actions_launch_boundary_import_is_present() -> None:
    actions_path = SOURCE_ROOT / "datapreparation_app" / "actions.py"
    imports = _parse_imports(actions_path)
    assert _contains_module(imports, "Source.analysis_app.app"), (
        "actions.py should keep the sanctioned launch boundary import"
    )
