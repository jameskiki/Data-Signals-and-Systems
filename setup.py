"""py2exe build configuration for EvalData."""

from __future__ import annotations

import importlib.util
import pathlib
import re
import shutil

import py2exe


def _read_version() -> str:
    return pathlib.Path("VERSION").read_text(encoding="utf-8").strip()


def _package_dir(package_name: str) -> pathlib.Path:
    spec = importlib.util.find_spec(package_name)
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError(f"Unable to resolve package directory for {package_name}.")
    return pathlib.Path(next(iter(spec.submodule_search_locations)))


def _normalized_extension_stem(stem: str) -> str:
    # Wheels often suffix binary modules with ABI/platform tags (for example
    # "module.cp312-win_amd64"); py2exe expects dotted module names without tags.
    return re.sub(r"\.cp\d+[-_\w]*$", "", stem)


def _sync_package_binary_extensions(package_name: str, dist_lib_dir: pathlib.Path) -> int:
    source_dir = _package_dir(package_name)
    copied = 0

    for extension_file in source_dir.rglob("*.pyd"):
        relative = extension_file.relative_to(source_dir)
        module_parts = list(relative.parts)
        module_parts[-1] = _normalized_extension_stem(pathlib.Path(module_parts[-1]).stem)
        dotted_module = ".".join([package_name, *module_parts])
        target_file = dist_lib_dir / f"{dotted_module}.pyd"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if not target_file.exists():
            shutil.copy2(extension_file, target_file)
            copied += 1

    return copied


def _verify_required_binary_modules(dist_lib_dir: pathlib.Path) -> None:
    required_modules = [
        "numpy._core._multiarray_umath",
        "scipy.special.cython_special",
        "scipy.stats._stats",
        "scipy.special._ufuncs",
    ]
    missing = []
    for module_name in required_modules:
        if not (dist_lib_dir / f"{module_name}.pyd").exists():
            missing.append(module_name)

    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            "Missing required compiled module(s) in packaged output: "
            f"{missing_list}."
        )


def main() -> None:
    pathlib.Path("Dist/EvalData").mkdir(parents=True, exist_ok=True)
    dist_lib_dir = pathlib.Path("Dist/EvalData/lib")
    py2exe.freeze(
        windows=[{"script": "EvalData.py", "dest_base": "EvalData"}],
        zipfile="lib/library.zip",
        options={
            "dist_dir": "Dist/EvalData",
            "compressed": 1,
            "optimize": 1,
            "bundle_files": 3,
            "includes": [
                "matplotlib.backends.backend_tkagg",
                "scipy",
                "scipy.signal",
                "scipy.special.cython_special",
                "unittest",
            ],
            "packages": [
                "numpy",
                "pandas",
                "matplotlib",
                "scipy",
                "tkinter",
                "Source",
            ],
            "excludes": ["pytest"],
        },
        version_info={
            "version": _read_version(),
            "description": "EvalData signals and systems toolkit",
            "product_name": "EvalData",
            "product_version": _read_version(),
        },
    )

    copied_total = 0
    for package in ("scipy", "numpy", "pandas", "matplotlib"):
        copied_total += _sync_package_binary_extensions(package, dist_lib_dir)
    _verify_required_binary_modules(dist_lib_dir)
    print(f"Synchronized {copied_total} compiled extension module(s) into {dist_lib_dir}.")


if __name__ == "__main__":
    main()
