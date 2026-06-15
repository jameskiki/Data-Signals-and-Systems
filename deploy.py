"""
deploy.py

Script to set up a virtual environment, install dependencies, and build the EvalData executable using PyInstaller.
"""

import subprocess
import sys
import os
from collections.abc import Sequence

VENV_DIR = ".venv"
PYTHON_EXE = os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "python")
PYINSTALLER_EXE = os.path.join(VENV_DIR, "Scripts", "pyinstaller.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "pyinstaller")
REQUIREMENTS_FILE = "requirements.txt"

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

def main() -> None:
    """
    Set up venv, install dependencies, and build executable.
    """
    # Create venv if it doesn't exist
    if not os.path.exists(PYTHON_EXE):
        run([sys.executable, "-m", "venv", VENV_DIR])

    # Upgrade pip
    run([PYTHON_EXE, "-m", "pip", "install", "--upgrade", "pip"])

    # Install pinned project dependencies from a single source of truth.
    run([PYTHON_EXE, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])

    # Build EXE into the repository's renamed artifact folders.
    run([PYINSTALLER_EXE, "EvalData.spec", "--workpath", "Build", "--distpath", "Dist"])

if __name__ == "__main__":
    main()