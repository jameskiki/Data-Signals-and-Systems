# EvalData

EvalData is a Python desktop application for loading, preparing, previewing, and analyzing measurement datasets.

It provides:
- dataset import and summary views
- preparation workflows for row-range selection, column-role assignment, and dataset splitting
- overview plotting in the main window
- a dedicated analysis workspace for filtering, spectral analysis, and cycle-oriented exploration
- demo datasets for validating workflows and signal-processing behavior

## Requirements

- Python 3.12
- Windows-oriented setup and packaging

## Run Locally

Create and activate a virtual environment, install the dependencies, and launch the app:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python EvalData.py
```

## Build Executable

The repository includes a small helper script for setting up dependencies and building the executable with PyInstaller:

```powershell
python deploy.py
```

You can also build directly from the current environment:

```powershell
pyinstaller EvalData.py
```

## Project Layout

- `EvalData.py`: main application window and orchestration
- `analysis_workspace.py`: detailed per-dataset analysis window
- `evaldata_*.py`: layout, preview, plotting, demo, and preparation helpers
- `data_ops/`: pure dataframe and signal-processing helpers
- `deploy.py`: environment/bootstrap build helper

## Status

There is currently no automated test suite in the repository. Basic validation has been done through module import checks and compile-time smoke checks.

## Documentation

The main repository documentation is intentionally kept in Markdown for easy browsing on Git hosting. A later addition of a LaTeX-based technical manual remains a valid option for deeper documentation.
