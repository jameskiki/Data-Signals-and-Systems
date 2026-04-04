# EvalData

EvalData is a Python desktop application for loading, preparing, previewing, and analyzing measurement datasets.

## Features

- dataset import and summary views
- preparation workflows for row-range selection, column-role assignment, and dataset splitting
- overview plotting in the main window
- a dedicated analysis workspace for filtering, spectral analysis, and cycle-oriented exploration
- demo datasets for validating workflows and signal-processing behavior

## Requirements

- Python 3.12
- Windows-oriented local setup and packaging

## Local Setup

Create and activate a virtual environment, install dependencies, and launch the app:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python EvalData.py
```

## Debugging In VS Code

The repository tracks `.vscode/launch.json` on purpose. It gives the project a shared debug profile that:

- starts `EvalData.py`
- runs from the workspace root
- uses the project-local `.venv` interpreter

That keeps debugger behavior aligned with the intended local setup.

## Build And Release

For a local executable build, use the helper script:

```powershell
python deploy.py
```

That script creates or reuses `.venv`, installs runtime dependencies plus PyInstaller, and builds the application.

You can also build directly from an activated environment:

```powershell
pyinstaller EvalData.py
```

Generated build artifacts are written to `build/` and `dist/` and are intentionally ignored by Git.

## Project Layout

- `EvalData.py`: main application window and orchestration
- `analysis_workspace.py`: detailed per-dataset analysis window
- `evaldata_*.py`: layout, preview, plotting, demo, and preparation helpers
- `data_ops/`: pure dataframe and signal-processing helpers
- `deploy.py`: environment/bootstrap build helper

## Validation Status

There is currently no automated test suite in the repository. The current baseline has been checked with module import smoke tests and a compile-time pass.

## Documentation Approach

The repository uses Markdown for the primary documentation so it renders directly on Git hosting. A later LaTeX-based technical manual remains a good option for deeper theory, figures, and formal documentation.
