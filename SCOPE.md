## Data Passed Between Apps

**Data Preparation → Analysis:**
- The datapreparation app passes the following to the analysis app (AnalysisWorkspace):
	- A pandas DataFrame containing the prepared dataset (cleaned, structured measurement data).
	- Associated metadata, including:
		- The dataset path (string, used as a key/label)
		- Column roles (dictionary mapping column names to semantic roles)
		- Optional dataset description (string)
	- All data is passed in memory (not via files), using direct function/class calls.

**(Planned) Data Preparation/Analysis → Systems App:**
- The future systems app will require a well-defined interface to accept:
	- One or more pandas DataFrames (prepared or processed data)
	- Relevant metadata (column roles, units, descriptions)
	- Possibly model parameters or configuration objects
- The exact interface will be specified as the systems app is developed, but the goal is to maintain in-memory, structured data exchange for seamless integration.
## Planned Features / Future Work

The following features are planned for future development and are not yet implemented:

- **Systems Section**
	- Model building (system modeling from data or first principles)
	- Simulation of system behavior
	- System identification (parameter estimation, model fitting)
	- Integration of simulation and identification results with analysis workflows


# Application Scope: Test Stand Data Analysis

## Workflow Overview

The application is structured as a modular, GUI-driven toolkit with multiple tightly integrated apps:

- **Data Preparation App**: Users import, parse, and clean measurement data (CSV, Excel, etc.). Data is loaded into memory as pandas DataFrames and managed within the app.
- **Analysis App**: When analysis is requested, the Data Preparation App launches an Analysis Workspace, passing the selected DataFrame and metadata directly in memory (not via files). All analysis, visualization, and reporting is performed on this in-memory data.
- **(Planned) Systems App**: Will extend the workflow to support system modeling, simulation, and identification, likely by accepting prepared/processed data in memory or via a well-defined interface.

**Key Points:**
- Data handoff between apps is in-memory (DataFrame objects), not file-based.
- The workflow is orchestrated by the GUI; users do not manually export/import files between apps.
- Extensibility for future apps (e.g., systems modeling) will require clear, documented interfaces for in-memory data exchange and/or serialization as needed.

**Typical User Flow:**
1. Load and prepare data in the Data Preparation App.
2. Launch analysis on selected data, opening an Analysis Workspace.
3. (Future) Pass prepared/processed data to the Systems App for modeling or simulation.
4. Review, visualize, and export results as needed.

This design ensures a seamless, interactive workflow and supports future extensibility while maintaining reproducibility and modularity.

## Purpose and Goals
This application is designed to analyze, visualize, and report on data from engineering test stands. It aims to streamline the evaluation process, provide reproducible results, and support engineering decision-making.

## Key Features

### Core Functionalities
- Import measurement data from CSV, Excel, and other supported formats
- Parse and validate input data structure
- Data cleaning (handling missing values, outlier detection)
- Data filtering (low-pass, high-pass, band-pass, custom filters)
- Preprocessing (resampling, normalization, detrending)
- Cycle and event detection in time series
- Signal processing (FFT, Welch, spectral analysis)
- Statistical analysis (mean, median, std, correlation, etc.)
- Summary statistics and report generation
- Interactive plotting (time series, histograms, scatter plots, etc.)
- Automated batch plotting and figure export (PNG, PDF, SVG)
- Export of results (tables, figures, processed data)
- Configurable analysis workflows (via config files or UI)
- Logging of analysis steps and parameters for reproducibility
- Version-controlled outputs (results linked to code and config version)

### Extensibility
- Modular architecture for adding new analysis modules
- Clear API for integrating custom data processing or visualization steps

### User Interface
- Graphical user interface (GUI) for interactive analysis
- Non-blocking status bar with severity-aware notifications (`NotificationManager`, `StatusBar`)
- Cycle review workflow with interactive include/exclude of detected cycles

### Documentation & Help

**Documentation Structure Note:**
Practical, high-level usage and context should be documented in Markdown (docs/). Detailed algorithmic explanations and derivations should be documented in LaTeX (docs/latex/). This ensures clarity and separation between user guidance and technical reference.

## Testing & Quality Assurance

The application includes the following testing and quality assurance practices:
- Automated unit tests for core data processing and analysis modules (see the tests/ directory)
- Test coverage for key algorithms and data workflows
- Manual validation of GUI features and plotting outputs
- Continuous improvement of tests as new features are added

All contributors are encouraged to add or update tests when modifying or extending the codebase.

---

## Non-Features (Out of Scope)
- Real-time data acquisition or control
- Direct hardware interfacing
- Web-based or cloud deployment (local desktop only)
- Support for non-engineering/scientific data
- Proprietary or closed-source algorithms

## Target Users
- Test engineers and researchers working with engineering test stands
- Data analysts in mechanical engineering
- Developers extending or maintaining the analysis toolkit

## Usage Scenarios
- Batch analysis of test stand data for reporting
- Interactive exploration of measurement signals
- Automated generation of figures for documentation
- Extension with new analysis modules by developers

## Architectural Boundaries
- Python-based, modular codebase
- Local file-based data and configuration
- GUI interface only (no CLI, no web frontend)
- Use of open-source scientific libraries (NumPy, SciPy, matplotlib, etc.)

## Allowed Technologies
- Python 3.x
- Standard scientific Python stack (NumPy, SciPy, pandas, matplotlib)
- PyInstaller for packaging
- VS Code for development

## Change Management
- All changes to this scope must be tracked in version control
- Scope document should be referenced in prompt templates and developer documentation

---
_Last updated: 2026-06-01_