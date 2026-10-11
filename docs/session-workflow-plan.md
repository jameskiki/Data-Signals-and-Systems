# Session History, Workflow View, and Reports

Status: prototype history, analysis result snapshots, embedded project
save/reopen, and a first publish-node HTML report implemented. Replay remains a proposal.

## Try the Prototype

Fastest look at the whole workflow: `Demo -> Generate Workflow Demo Project (Load to Report)...`
builds a finished project and report from the three-day demo files and opens the graph
(see [demo validation](demo-validation.md#end-to-end-workflow-demo-project)).

By hand:

1. Start the app and load the spectral reference demo from the Demo menu.
2. Choose columns and optionally a range, then create a prepared dataset.
3. Open its analysis workspace, select a signal, choose `moving_average`, set a
   window size, and apply the filter.
4. Publish the current view back to the main dataset list.
5. Open `View -> Workflow / Pipeline & Reports (Prototype)` in the main window.
6. Select a list entry or graph node to inspect its parameters and revision IDs.
   Use Refresh after more operations.
7. Select the original dataset and prepare another version to see a branch.

The graph and list share a red-green-deficiency-conscious palette: blue for
inputs/combined data, amber for processing, muted purple for snapshot results,
bluish green for published datasets, gray for metadata, and white with a black dashed border for untracked
operations. Selection adds a dark outline. Graph nodes include explicit category
labels, so category distinctions never depend on hue alone. This is not a claim
of formal accessibility certification.

The wider graph supports `Preview Node Deletion...`: affected nodes and
downstream revision dependents receive a thick dashed outline, and the details
pane lists affected datasets and result snapshots. A separate confirmation
removes them from the current session and closes analysis/comparison windows.
Source files and previously saved project files are untouched; save the project
again to persist the deletion. There is no undo.

Result snapshots are leaves: deleting one does not delete its input data.
Deleting an input/processing node cascades through its dependent branches, not
unrelated later operations. Metadata edits (names/roles) cannot be deleted
individually until state rollback is supported. Make a new metadata edit or
delete the owning data branch instead.

The graph and list currently cover file/demo loading, preparation, all signal
filters, simple range filters, derived signals, resampling, splits, merges,
resets, applied cycle selections, and publishing. Unspecified dataframe
replacements are still marked UNTRACKED.
Role assignments/re-inference and workspace role propagation are recorded.
Frequency and cycle computations retain their parameters and numeric result
tables. Manual cycle exclusion/restoration retains selected ranges and results.
Comparison display settings are not captured.
Preparation records requested range text and roles, selected columns, and output
shape; it is not a replayable range specification yet.

Unsaved history is lost when the app closes. Publishing creates its own revision and
graph node after the last workspace operation (no numeric transformation). Later work
on the published dataset hangs off that node; the node shows the current display name.
The publish node also links (dashed arrows) every operation recorded in that analysis
workspace — transforms, snapshot results and role edits — and its details list them.
These links are informational: deleting a linked snapshot keeps the publish node and
notes the missing step. Publishing again from the same workspace links the full list again.
Projects saved before this change keep their shared publish revision and still load.
Reloading a file creates a new identity.
Unloading a dataset leaves its history visible, but does not retain its data.
No replay, undo, or editable graph is included.

### Save and Reopen

1. Publish any workspace edits you want to retain in the main dataset list.
2. Use `Files -> Save Embedded Project...` to write a `.evaldata` file.
3. Close/restart the app, then use `Files -> Open Project...`.
4. Inspect restored datasets and history. Select an analysis step and click
   `Inspect Saved Result Tables` for a bounded table preview.

The project is a ZIP archive with a schema-versioned JSON manifest and typed
Parquet datasets/result tables. It retains dataset/revision identities, roles,
source labels, warnings, timestamps, runtime versions, and SHA-256 checksums of
embedded table payloads. It does not need the original source files to reopen.
These checksums identify saved snapshots, not original source-file bytes.

Saving validates a temporary archive before atomically replacing the target.
Opening validates before replacing live state and asks before discarding an
existing session. Unsupported schema versions, missing tables, and corrupt
payloads surface errors.

Only currently registered datasets are embedded, not every historical revision
or unpublished working frame. Analysis tables persist independently, even if
their intermediate input frame was not published. Reopened results are table
snapshots, not live analysis tabs. Windows/layouts and comparison state are not
restored. Save/open currently run synchronously and may pause the UI for large
projects; avoid treating this prototype as a large-file performance solution.

Datetime detection now validates the full non-empty column before conversion.
Below 80% valid timestamps it retains the original values; accepted conversions
with failures explicitly report how many values became missing. Load summaries
show these warnings, and load history retains them. Mixed formats can still be
rejected; the parser does not promise automatic date-format disambiguation.

Phase 2 covers dataframe transformations, datetime validation, role changes,
and standalone frequency/cycle artifacts. Persistent execution-failure records
remain future work. Phase 3 embeds snapshots; replay is not implemented.

## Goal

Make the work on a dataset understandable, then make it persistent and
repeatable. Start with something small that can be tried in the existing desktop
app. Keep the current preparation, analysis, and comparison workflows.

This is an incremental refactor, not a rewrite or a new workflow editor.
See [technical overview](technical-overview.md) for the current architecture.

## Starting Point

- Shared in-memory datasets, workspace copies, and publish-back snapshots exist.
- Source paths and descriptions exist, but structured operation history does not.
- Parquet saves data and column roles, not a complete project/session.
- Reporting is limited to a Transfer/Coherence text sidecar.
- Review baseline: 499 tests passed after restoring missing declared dependencies.
- A review probe found that initial-sample datetime detection can coerce most of
  a column into missing values without a conversion warning.

## 1. First Tryable Concept: History and a Small Workflow View

Deliver one narrow end-to-end demo path:

1. Load a built-in demo.
2. Create a prepared dataset.
3. Apply a moving-average filter in analysis.
4. Publish the result.
5. Open a History/Workflow window and inspect the steps and parameters.

Implementation direction:

- Add a small UI-independent history model with stable dataset/revision IDs.
  Keep paths as labels/source locations, not as permanent identity.
- Record operation name, input/output revision IDs, resolved parameters,
  timestamp, and available warnings.
- Use the existing dataframe registry; do not replace every session object.
- Show a chronological list with a selected-step detail pane and a simple
  top-to-bottom graph. Use existing Tk widgets/canvas, not a new graph framework.
- Record the preparation range/columns and actual moving-average parameters.
  A revision identifies data state; publishing links that state to a dataset
  entry rather than pretending to be another numeric transformation.
- Keep everything in memory for this prototype. Say explicitly that closing
  the app loses the history and that it cannot yet replay operations.
- Mark unsupported operations as untracked; never imply that the partial
  history is complete. This prototype is not an audit trail.

Acceptance:

- The demo path shows correct parent links and exact applied parameters.
- A second preparation from the source produces a visible branch.
- Existing dataset and workspace behavior remains unchanged.
- Targeted tests cover recording and links; manually try the demo and the view.

Feedback gate: ask the user to try the prototype and decide whether the
list/graph and level of detail are useful before extending the model.

## 2. Correctness and Wider History Coverage

- Fix datetime conversion validation and surface failed conversion counts.
  Test mixed-format and misleading-initial-sample cases.
- Record the remaining data changes: all filters, derived signals, resampling,
  splits, merges, resets, and applied cycle selections.
- Record role changes and analysis artifacts separately from data transforms.
  Include FFT/Welch parameters and manual cycle include/exclude decisions.
- Preserve references when datasets are unloaded or the same file is reloaded.
- Record failures as diagnostics, not as successful output revisions.
- Add a small operation execution/recording boundary only where needed; do not
  duplicate algorithms or build a general plugin framework.

Acceptance: no supported data change can silently leave the history incomplete;
tests cover branching, multi-input merges, resets, and failure behavior.

## 3. Save and Reopen a Project

Implemented simple format: a local `.evaldata` ZIP archive containing a versioned
JSON manifest and registered dataset/result Parquet snapshots.

- Persist IDs, parent links, operation records, roles, and saved results.
- Save the datasets needed to reopen the project; do not save a full dataframe
  after every operation.
- Store source fingerprints and application/algorithm versions.
- Validate missing/corrupt files and incompatible schemas with explicit errors.
- Use temporary files and safe replacement so an interrupted save does not
  destroy the last usable project.
- Restore datasets and history first; restoring every window/layout is deferred.

Decision made: embed registered datasets for portability. External-file
references are deferred.

Acceptance: save, close, reopen, and compare data/roles/history; test interrupted
saves and missing sources. Reopening snapshots is not yet operation replay.

## 4. First Automatic Report

First prototype implemented: select a publish node in `View -> Workflow / Pipeline & Reports (Prototype)`
choose the target in **Report for publish**, and click **Generate Selected Report...**. EvalData writes one
self-contained HTML file (plots embedded as PNG) and opens it in the browser.

Report content defaults to the linked workspace operations plus annotated lineage evidence.
The checkbox on each eligible node overrides inclusion separately for each publish.
Choices are saved in the project; exclusion does not remove data, run or undo a
calculation, or suppress the published-data provenance warnings. Compact/expanded
cards only affect graph display. Dotted connectors now show enabled content for
the selected report, while solid connectors retain the complete pipeline.

The report contains:

- Overview: published dataset name/path, source dataset, publish time and revision.
- The linked workspace operations in recorded order, with parameters.
- Published data: row/column counts, column roles, statistics on the full data,
  and stacked signal panels (columns produced by the linked operations first, in
  green; at most 6 panels; every Nth row shown above 5,000 rows, stated in the caption).
- One section per linked snapshot result: its parameters, a spectrum plot (log
  frequency axis, DC omitted), a spectrogram (log frequency axis, at most 300
  log-spaced frequency bins and 300 time bins) or a cycle result (representative
  cycle mean +/- std with min/max band, plus per-cycle mean/peak-to-peak/RMS over
  the run), and table previews (first 20 rows).
- One section per recorded report view (`Add View to Report` in the analysis
  workspace plot panel): the recorded columns, X column, zoomed X range, layout,
  and Y scale, redrawn from the published data. Only settings are stored, never
  an image, so the view stays reproducible and survives project save/reopen.
  Missing columns and empty ranges are reported; Y zoom, colors, and
  annotations are not recorded.

Visible warnings instead of silent substitution: results computed before later
operations ("earlier working state"), deleted linked steps, untracked steps,
publishes from before operation linking, and a published dataset that is no
longer loaded in that revision (data sections are then omitted).

Limits: no upstream lineage before the analysis workspace (load/prepare steps are
not in the report), no templates, PDF, batch or automatic triggers, no comparison
results, and no interpretation. Signal role inference decides which columns are
"signals" (e.g. `elapsed_s` is plotted in the long-term demo).

Original goals:
- Generate a deterministic HTML report on explicit user request.
- Start with a saved dataset revision, operation history, basic statistics, one
  selected plot, and available analysis results/warnings.
- Keep the renderer independent of live GUI widgets.
- Associate every table/figure/result with its input revision and parameters.
- Label reduced-resolution plots and omitted/untracked steps.
- Do not invent scientific conclusions or treat successful execution as quality
  approval.

Feedback gate: review a report generated from a built-in demo before adding
templates, PDF output, batch generation, or automatic generation triggers.

Acceptance: the report remains consistent after the working dataset changes,
and missing results are visible rather than silently substituted.

## Append Recipes and Proposed Analysis Window Grouping

First append/reapply prototype implemented for filters and derived signals.
See the [append walkthrough and limits](user-guide.md#append-and-reapply-processing).
The analysis window grouping below remains a proposal.

User-endorsed direction:

- Separate reusable transformations from results computed for a particular
  dataset revision. History remains the record of what happened; a recipe
  specifies what should be reapplied.
- Append compatible raw inputs as a new combined revision *upstream* of the
  existing processing chain (user decision: true history rewrite rather than a
  duplicated chain). The chain's nodes and revision ids are kept, the first
  node is re-pointed, and datasets on the chain are recomputed in place.
- Preview an explicit "Operations to reapply" list before processing. Initially
  support filters and derived signals; unsupported transformations block
  automatic processing with an explanation rather than being silently skipped.
- Recompute supported transformations over the full combined run, not just the
  incoming rows, so rolling/filter boundary behavior remains consistent.
- Keep FFT/Welch, statistics, report views and branches computed on the old data
  unchanged, but mark them `before_append` so graph and reports say they only
  describe the earlier data. New result computation is explicit.
- Known cost of the rewrite: the history no longer shows what the chain looked
  like before the append (timestamps stay truthful, list order becomes
  topological), and previous processed values are discarded.
- Do not carry manual cycle exclusions or selected ranges forward automatically.

Consider splitting the analysis window into two clearly labeled groups:

1. **Reusable processing / ongoing workflow**: filters and derived signals that
   can be selected for reapplication when more data arrives.
2. **Snapshot results**: spectra, statistics, cycle results, and reports tied to
   a particular input revision, with that revision visible.

"Ongoing" means reusable processing across incremental file deliveries, not
live acquisition or continuously executing analysis. Snapshot methods may
eventually have reusable calculation settings, but each execution still creates
a separate revision-bound result. The grouping should clarify this distinction,
not imply that every filter is safe to reuse or every snapshot must be frozen
forever.

Feedback gate: sketch or prototype the grouping in the existing window before
a broad layout refactor. Confirm labels, recipe selection behavior, and how
unsupported steps are explained with the user.

## 5. Later: Replay, Reusable Workflows, and Performance

Only after the earlier concepts are useful:

- Replay a small supported operation sequence against verified inputs and
  compare its results with saved snapshots.
- Define behavior for changed source files or algorithm versions; never promise
  identical results across versions without verification.
- Separate a reusable recipe from the historical record of one execution.
- Benchmark load-to-first-plot, peak memory, and export on representative
  synthetic inputs before choosing further I/O changes.
- Remove summary-only concatenation where equivalent aggregate summaries can
  preserve behavior. Move demonstrably blocking work off the UI thread with
  clear progress/error handling.

Ask before introducing cancellation policies, automatic report triggers, batch
scope, or editable workflow graphs.

## Deliberately Deferred

- Drag-and-drop workflow editing.
- Full undo/redo and storing every intermediate dataframe.
- A database/event-sourcing framework or broad session rewrite.
- PDF infrastructure, scheduled reports, and AI-written interpretations.
- New Systems App functionality.

## Working Rules

- Work on `concept/session-history-workflow`, based on the current comparison
  development branch. Do not assume this branch contains only changes from main.
- Implement one milestone at a time, with a demo walkthrough and targeted tests.
- Ask at the feedback/decision gates and whenever behavior or scope is unclear.
- Update user documentation as each feature becomes real; do not describe this
  plan as implemented functionality.
