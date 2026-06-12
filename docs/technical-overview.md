# Technical Overview

## Purpose

This document describes the current EvalData repository architecture after the migration to the `Source/` package layout.

The project is organized around:

- `EvalData.py` as a thin launcher
- `Source/datapreparation_app/` as the preparation workspace
- `Source/analysis_app/` as the analysis workspace
- `Source/data_ops/` as reusable data and signal operations
- `Source/shared/` as shared plotting/UI contracts and infrastructure

## Current Package Map

- `EvalData.py`: thin application entry point
- `Source/datapreparation_app/`: load/prepare datasets, preview, split, ad-hoc plotting dialogs, launch analysis workspace
- `Source/analysis_app/`: filtering, derived signals, frequency analysis, cycle analysis, stats, export
- `Source/data_ops/`: pure operation modules (`signals`, `spectral`, `cycles`, `frame_ops`, `summary`, `filtering`, `io_ops`, `models`)
- `Source/shared/`: shared plot contracts/builders, embedded figure lifecycle, role/display helpers, notifications, docs links
- `tests/`: unit/app-layer/integration tests
- `.github/workflows/tests.yml`: CI test workflow and hard architecture boundary gate

## Layer Responsibilities

### Launcher Layer

- `EvalData.py` only starts the datapreparation app.

### App Layers

- `Source/datapreparation_app/` owns preparation workflow and preview behavior.
- `Source/analysis_app/` owns analysis workflow behavior.

### Reusable Operation Layer

- `Source/data_ops/` owns algorithmic operations and dataframe transformations.
- It must not depend on app packages.

### Shared Infrastructure Layer

- `Source/shared/` owns cross-app contracts and infrastructure for plotting/UI consistency.
- It must not depend on app packages.

## Plotting Architecture (Dual-App Depth Model)

Plotting is intentionally split into depths so responsibilities are clear for both apps.

### Depth 0: Shared Generic Plot Contracts and Builders

Owned by `Source/shared/`:

- `plot_options.py`: `PlotOptions` and `PlotStyle`
- `plot_utils.py`: generic figure building helpers (`create_plot_figure`, axis contract helpers)
- `display_format.py`: shared axis/value display formatting helpers

Depth 0 does not know app workflow state.

### Depth 1A: Analysis App Plot Orchestration

Owned by `Source/analysis_app/`:

- `plotting.py`: analysis-specific plot orchestration helpers used by the workspace class
- plotting orchestration and specialized rendering for time-series, frequency, and cycle views
- converts analysis session state into Depth 0 plot inputs

Examples live in `analysis_app/plotting.py`, are delegated from `analysis_app/app.py`, and are triggered by `analysis_app/handlers.py`.

### Depth 1B: Datapreparation App Plot Orchestration

Owned by `Source/datapreparation_app/`:

- preview plot orchestration and span-selection behavior
- converts preparation session state into Depth 0 plot inputs

Examples live in `datapreparation_app/plotting.py` and are triggered from `datapreparation_app/actions.py` and app delegates.

### Depth 2: UI-Specific Plot Windows and Embedded Canvas Lifecycle

Owned by app + shared infrastructure split:

- `datapreparation_app/plotting.py`: plot option dialog and detached plot windows
- `datapreparation_app/preview.py`: table preview helpers and plotting compatibility wrappers
- `shared/base_app_shell.py`: shared embedded figure lifecycle helper used by both apps

Depth 2 owns Tk canvas/window behavior, not algorithmic analysis.

## Import Boundary Policy

The repository now enforces architecture boundaries via `tests/test_import_boundaries.py` and CI.

### Required Rules

- `Source/data_ops/*` must not import app packages or Tk modules.
- `Source/shared/plot_utils.py` and `Source/shared/plot_options.py` must not import app packages or Tk modules.
- `Source/analysis_app/*` must not import `Source/datapreparation_app/*`.
- `Source/datapreparation_app/*` may reference analysis workspace only at the sanctioned launch boundary in `datapreparation_app/actions.py`.

## Runtime Flow

1. `EvalData.py` starts `Source.datapreparation_app.app.main()`.
2. Datapreparation app loads datasets and maintains dataset contexts.
3. Preview and ad-hoc plotting use shared plot contracts/builders.
4. Prepared datasets can be opened in analysis workspace.
5. Analysis workspace performs operations through `Source/data_ops/*` and renders results through shared plotting infrastructure plus analysis-specific orchestration.

## Testing and CI

- `tests/test_plot_utils.py`: shared plotting contract coverage
- `tests/test_base_app_shell.py`: embedded figure lifecycle behavior
- `tests/test_analysis_handlers.py`: analysis orchestration behavior
- `tests/test_workflows_integration.py`: preparation-to-analysis workflow coverage
- `tests/test_import_boundaries.py`: hard architecture boundary checks

CI order in `.github/workflows/tests.yml`:

1. `Import boundary checks (3.12)` (hard gate)
2. `Unit and app-layer tests (3.12)`
3. `Integration workflow tests (3.12)` (currently informational)

## Packaging and Build

- `deploy.py` handles local build bootstrap and PyInstaller invocation.
- `EvalData.spec` defines the PyInstaller package configuration.
- Build outputs are written to `Build/` and `Dist/`.

## Documentation Maintenance Note

If package boundaries or plotting responsibilities change, update this file together with boundary tests and CI gating rules in the same change.
