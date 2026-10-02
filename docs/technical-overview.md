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
- `Source/datapreparation_app/`: load/prepare datasets, preview, split, ad-hoc plotting dialogs, launch analysis workspace, and host the lightweight comparison window over session datasets
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
2. Datapreparation app loads datasets and maintains the shared in-memory session dataset registry plus dataset contexts.
3. Preview and ad-hoc plotting use shared plot contracts/builders.
4. Prepared datasets can be opened in analysis workspace.
5. Analysis workspace performs operations through `Source/data_ops/*`, can publish its current working dataframe back into the shared session registry, and renders results through shared plotting infrastructure plus analysis-specific orchestration.
6. The comparison window reuses the shared session registry, plotting contracts, and summary helpers to overlay or subtract two or more datasets already present in the session.

## Session Data Flow Directions

The current minimal session-data model intentionally keeps the flow explicit:

- loaded file/demo -> session registry
- source dataset -> prepared dataset -> session registry
- source dataset -> split subframes -> session registry
- session dataset -> analysis workspace
- analysis working dataframe -> published dataset -> session registry
- selected session datasets -> comparison window
- selected compared dataset -> analysis workspace
- session dataset or analysis view -> export to disk

The important rule is that the analysis workspace does not mutate the shared session dataframe in place. It owns a local original/working copy pair, and publishing creates a new dataset entry back in the session registry.

## View Sync Rules

- `register_dataset(...)` updates the shared session dataset registry and dataset context registry together.
- After register/merge/split/publish/unload actions, the main dataset table is rebuilt and the relevant dataset is reselected.
- The main preparation preview, plot, and metadata panels always render from the currently selected session dataset.
- Open analysis workspaces keep their own dataframe copies after launch, so filter/derive/resample operations stay local to that workspace.
- The main window and analysis workspace share exactly three column categories: time/reference, signal, and metadata.
- Multiple signal and metadata columns are allowed. Assigning time/reference keeps one time column and reclassifies the previous time column as signal when numeric or metadata otherwise.
- Category edits in the main window propagate to already-open analysis workspaces only when their `session.source_path` matches the edited dataset path.
- Publishing from analysis creates a new dataset path in the main session registry; it does not replace the original analysis source dataset.
- The comparison window stores the dataset paths chosen at launch. Its `Refresh` button re-reads those same paths from the current session registry and updates common-column controls, plots, and summaries.
- A selected baseline is used for difference mode; each visible candidate is plotted as candidate minus baseline. Normalization and zero-start are display-only transforms and never mutate session data.
- The selected baseline uses a dashed line in overlay plots. In difference mode, the dashed zero-reference line is labeled with the baseline dataset name.
- The dedicated `Datasets` selector hides datasets from plots while retaining them in the comparison and summary. Its `All` and `None` controls provide quick bulk selection. The summary reports count, RMS, peak-to-peak, and deviation RMS for the selected signal.
- The signal selector uses the union of numeric columns across compared datasets. Partial channels are annotated with availability counts such as `pressure (2/3 datasets)`, and the status line reports dataset/channel combinations omitted from plotting. X-axis choices remain shared-only so every visible run uses the same reference axis.
- `Channels in grid` gives every selected signal its own subplot in a balanced grid, with the visible datasets overlaid within each channel and unused cells hidden. With the option disabled, the existing combined overlay and vertically stacked difference layouts remain unchanged.
- `Highlight deviations` fills the area above the baseline in translucent red and the area below it in translucent blue. Overlay mode fills between baseline and candidate curves; difference mode fills between each difference curve and zero.
- `Show legend` is a comparison-window display override. It defaults to the configured plot style but can hide or restore all legends in the current comparison without changing the saved global style.
- `Trim to overlap` limits both overlay and difference plots to the x range shared by every visible dataset. `Index` compares positional samples; a shared numeric x/time column interpolates the baseline onto each candidate's x samples before calculating differences.
- Newly published datasets are new session entries, so they do not appear automatically inside already-open comparison windows; open a new comparison run when you want to include them.

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

- `deploy.py` handles local build bootstrap, py2exe bundle generation, and optional installer compilation.
- `setup.py` defines the py2exe package configuration.
- `installer.iss` defines the Inno Setup installer configuration.
- Build outputs are written to `Build/` and `Dist/`.

## Documentation Maintenance Note

If package boundaries or plotting responsibilities change, update this file together with boundary tests and CI gating rules in the same change.
