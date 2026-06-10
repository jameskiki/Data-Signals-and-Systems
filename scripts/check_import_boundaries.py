"""Run architecture boundary tests as a dedicated pre-check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print("Running:", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=ROOT)
    return completed.returncode


def main() -> int:
    return _run([sys.executable, "-m", "pytest", "Tests/test_import_boundaries.py", "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
