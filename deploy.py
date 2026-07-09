"""
deploy.py

Script to set up a virtual environment, install dependencies, and build the
EvalData executable using py2exe and Inno Setup.
"""

import pathlib
import shutil
import subprocess
import sys
import os
from collections.abc import Sequence

VENV_DIR = ".venv"
PYTHON_EXE = os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "python")
REQUIREMENTS_FILE = "requirements.txt"
VERSION_FILE = "VERSION"
SETUP_SCRIPT = "setup.py"
INNO_SCRIPT = "installer.iss"

def run(cmd: Sequence[str]) -> None:
    """
    Run a shell command and raise an error if it fails.
    """
    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Command failed with exit code {e.returncode}")
        sys.exit(e.returncode)


def read_version() -> str:
    """Read application version from the repository VERSION file."""

    return pathlib.Path(VERSION_FILE).read_text(encoding="utf-8").strip()


def find_iscc() -> str | None:
    """Locate the Inno Setup compiler if available on this machine."""

    env_override = os.environ.get("INNO_SETUP_ISCC")
    if env_override and os.path.exists(env_override):
        return env_override

    on_path = shutil.which("iscc")
    if on_path:
        return on_path

    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    if local_app_data:
        candidates.append(os.path.join(local_app_data, "Programs", "Inno Setup 6", "ISCC.exe"))
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None

def main() -> None:
    """
    Set up venv, install dependencies, and build executable/installer artifacts.
    """
    if os.name != "nt":
        print("Error: deploy.py supports Windows packaging only.")
        sys.exit(1)

    # Create venv if it doesn't exist
    if not os.path.exists(PYTHON_EXE):
        run([sys.executable, "-m", "venv", VENV_DIR])

    # Upgrade pip
    run([PYTHON_EXE, "-m", "pip", "install", "--upgrade", "pip"])

    # Install pinned project dependencies from a single source of truth.
    run([PYTHON_EXE, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])

    # Build py2exe artifact tree into Dist/EvalData.
    run([PYTHON_EXE, SETUP_SCRIPT])

    iscc = find_iscc()
    if not iscc:
        print("Warning: Inno Setup compiler not found; skipping installer build.")
        return

    version = read_version()
    run([iscc, f"/DAppVersion={version}", INNO_SCRIPT])

if __name__ == "__main__":
    main()