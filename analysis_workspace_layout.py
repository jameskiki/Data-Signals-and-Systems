"""Tk layout builders for the analysis workspace."""

import tkinter as tk
from tkinter import ttk

from analysis_workspace_state import DERIVED_OPERATIONS, FFT_WINDOW_OPTIONS, PREVIEW_ROW_LIMIT, UI_FREQUENCY_ANALYSIS_METHODS
from data_ops.models import SIGNAL_FILTER_OPERATIONS


def build_analysis_workspace_ui(workspace) -> None:
    """Build the full analysis workspace UI."""

    main_pane = ttk.Panedwindow(workspace.window, orient=tk.HORIZONTAL)
    main_pane.pack(fill=tk.BOTH, expand=True)

    sidebar = ttk.LabelFrame(main_pane, text="Workspace Context", padding=5)
    notebook_container = ttk.LabelFrame(main_pane, text="Analysis Tools", padding=5)
    plot_panel = ttk.LabelFrame(main_pane, text="Live Plot", padding=5)
    main_pane.add(sidebar, weight=1)
    main_pane.add(notebook_container, weight=1)
    main_pane.add(plot_panel, weight=2)

    build_sidebar(workspace, sidebar)
    build_notebook(workspace, notebook_container)
    build_plot_panel(workspace, plot_panel)


def build_sidebar(workspace, parent: ttk.Frame) -> None:
    info_frame = ttk.LabelFrame(parent, text="Dataset")
    info_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(info_frame, textvariable=workspace.dataset_label_var, wraplength=220).pack(anchor="w", padx=5, pady=(5, 2))
    ttk.Label(info_frame, textvariable=workspace.original_shape_var).pack(anchor="w", padx=5, pady=2)
    ttk.Label(info_frame, textvariable=workspace.working_shape_var).pack(anchor="w", padx=5, pady=2)
    ttk.Label(info_frame, textvariable=workspace.numeric_columns_var).pack(anchor="w", padx=5, pady=(2, 5))
    ttk.Label(info_frame, textvariable=workspace.role_summary_var, wraplength=220, justify=tk.LEFT).pack(anchor="w", padx=5, pady=(0, 5))
    ttk.Label(info_frame, text="Active analysis column").pack(anchor="w", padx=5, pady=(5, 2))
    workspace.active_column_combo = ttk.Combobox(info_frame, textvariable=workspace.active_column_var, state="readonly")
    workspace.active_column_combo.pack(fill=tk.X, padx=5, pady=(0, 5))

    action_frame = ttk.LabelFrame(parent, text="Actions")
    action_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Button(action_frame, text="Reset Working Data", command=workspace._reset_working_data).pack(fill=tk.X, padx=5, pady=(5, 2))
    ttk.Button(action_frame, text="Export Current View", command=workspace._export_current_view).pack(fill=tk.X, padx=5, pady=2)
    ttk.Button(action_frame, text="Refresh Statistics", command=workspace._refresh_all_views).pack(fill=tk.X, padx=5, pady=(2, 5))

    context_pane = ttk.Panedwindow(parent, orient=tk.VERTICAL)
    context_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    overview_frame = ttk.LabelFrame(context_pane, text="Overview")
    history_frame = ttk.LabelFrame(context_pane, text="History")
    context_pane.add(overview_frame, weight=1)
    context_pane.add(history_frame, weight=1)

    workspace.sidebar_overview_text = tk.Text(overview_frame, wrap="word", height=12)
    workspace.sidebar_overview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
    overview_scrollbar = ttk.Scrollbar(overview_frame, orient=tk.VERTICAL, command=workspace.sidebar_overview_text.yview)
    overview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
    workspace.sidebar_overview_text.config(yscrollcommand=overview_scrollbar.set, state=tk.DISABLED)

    workspace.history_listbox = tk.Listbox(history_frame, height=20)
    workspace.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
    history_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=workspace.history_listbox.yview)
    history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
    workspace.history_listbox.config(yscrollcommand=history_scrollbar.set)


def build_notebook(workspace, parent: ttk.Frame) -> None:
    workspace.notebook = ttk.Notebook(parent)
    workspace.notebook.pack(fill=tk.BOTH, expand=True)

    workspace.preview_tab = ttk.Frame(workspace.notebook)
    workspace.filter_tab = ttk.Frame(workspace.notebook)
    workspace.derived_tab = ttk.Frame(workspace.notebook)
    workspace.frequency_tab = ttk.Frame(workspace.notebook)
    workspace.cycles_tab = ttk.Frame(workspace.notebook)
    workspace.statistics_tab = ttk.Frame(workspace.notebook)

    workspace.notebook.add(workspace.preview_tab, text="Preview")
    workspace.notebook.add(workspace.filter_tab, text="Filter")
    workspace.notebook.add(workspace.derived_tab, text="Derived Signals")
    workspace.notebook.add(workspace.frequency_tab, text="Frequency")
    workspace.notebook.add(workspace.cycles_tab, text="Cycles")
    workspace.notebook.add(workspace.statistics_tab, text="Statistics")

    build_preview_tab(workspace)
    build_filter_tab(workspace)
    build_derived_tab(workspace)
    build_frequency_tab(workspace)
    build_cycles_tab(workspace)
    build_statistics_tab(workspace)


def build_plot_panel(workspace, parent: ttk.LabelFrame) -> None:
    controls = ttk.Frame(parent)
    controls.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    ttk.Label(controls, text="X-axis").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.plot_x_combo = ttk.Combobox(controls, textvariable=workspace.plot_x_var, state="readonly")
    workspace.plot_x_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Y columns").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
    plot_selector_row = ttk.Frame(controls)
    plot_selector_row.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    plot_selector_row.columnconfigure(0, weight=1)

    workspace.plot_y_selector_button = ttk.Menubutton(
        plot_selector_row,
        textvariable=workspace.plot_y_selection_summary_var,
        direction="below",
    )
    workspace.plot_y_selector_button.grid(row=0, column=0, sticky="ew")
    workspace.plot_y_selector_menu = tk.Menu(workspace.plot_y_selector_button, tearoff=0)
    workspace.plot_y_selector_button.configure(menu=workspace.plot_y_selector_menu)
    workspace.plot_y_selector_button.state(["disabled"])

    plot_selector_actions = ttk.Frame(plot_selector_row)
    plot_selector_actions.grid(row=0, column=1, sticky="e", padx=(8, 0))
    ttk.Button(plot_selector_actions, text="All", width=6, command=workspace._select_all_plot_y_columns).pack(side=tk.LEFT)
    ttk.Button(plot_selector_actions, text="None", width=6, command=workspace._clear_selected_plot_y_columns).pack(
        side=tk.LEFT,
        padx=(6, 0),
    )

    ttk.Checkbutton(controls, text="Subplots", variable=workspace.plot_subplots_var).grid(
        row=2, column=0, sticky="w", padx=5, pady=5
    )
    ttk.Button(controls, text="Update Plot", command=workspace._update_plot).grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    controls.columnconfigure(1, weight=1)

    workspace.plot_notebook = ttk.Notebook(parent)
    workspace.plot_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    workspace.signal_plot_tab = ttk.Frame(workspace.plot_notebook)
    workspace.frequency_plot_tab = ttk.Frame(workspace.plot_notebook)
    workspace.cycle_plot_tab = ttk.Frame(workspace.plot_notebook)
    workspace.plot_notebook.add(workspace.signal_plot_tab, text="Signal Plot")
    workspace.plot_notebook.add(workspace.frequency_plot_tab, text="Frequency Plot")
    workspace.plot_notebook.add(workspace.cycle_plot_tab, text="Cycle Plot")

    workspace.plot_container = ttk.Frame(workspace.signal_plot_tab)
    workspace.plot_container.pack(fill=tk.BOTH, expand=True)
    workspace.frequency_plot_container = ttk.Frame(workspace.frequency_plot_tab)
    workspace.frequency_plot_container.pack(fill=tk.BOTH, expand=True)
    workspace.cycle_plot_container = ttk.Frame(workspace.cycle_plot_tab)
    workspace.cycle_plot_container.pack(fill=tk.BOTH, expand=True)


def build_preview_tab(workspace) -> None:
    ttk.Label(
        workspace.preview_tab,
        text=f"Showing the first {PREVIEW_ROW_LIMIT} rows of the current working dataframe.",
    ).pack(anchor="w", padx=5, pady=(5, 0))
    workspace.preview_container = ttk.Frame(workspace.preview_tab)
    workspace.preview_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


def build_filter_tab(workspace) -> None:
    filter_notebook = ttk.Notebook(workspace.filter_tab)
    filter_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    simple_filter_tab = ttk.Frame(filter_notebook)
    signal_filter_tab = ttk.Frame(filter_notebook)
    filter_notebook.add(simple_filter_tab, text="Simple Filtering")
    filter_notebook.add(signal_filter_tab, text="Signal Processing")

    build_simple_filter_tab(workspace, simple_filter_tab)
    build_signal_filter_tab(workspace, signal_filter_tab)


def build_simple_filter_tab(workspace, parent: ttk.Frame) -> None:
    controls = ttk.Frame(parent, padding=10)
    controls.pack(fill=tk.BOTH, expand=True)

    ttk.Label(controls, text="Active column").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.filter_active_column_label = tk.Label(controls, textvariable=workspace.active_column_var, anchor="w", padx=6, pady=3)
    workspace.filter_active_column_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(controls, text="Minimum").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.filter_min_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Maximum").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.filter_max_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    ttk.Checkbutton(controls, text="Keep missing values", variable=workspace.keep_missing_var).grid(
        row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5
    )

    ttk.Label(controls, text="Output column").grid(row=4, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.filter_output_name_var).grid(row=4, column=1, sticky="ew", padx=5, pady=5)

    ttk.Button(controls, text="Apply Simple Filter", command=workspace._apply_filter).grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10)
    )

    ttk.Label(
        controls,
        text="This masks only the active column. Other columns and row count remain unchanged.",
        justify=tk.LEFT,
    ).grid(row=6, column=0, columnspan=2, sticky="w", padx=5, pady=5)

    controls.columnconfigure(1, weight=1)


def build_signal_filter_tab(workspace, parent: ttk.Frame) -> None:
    controls = ttk.Frame(parent, padding=10)
    controls.pack(fill=tk.BOTH, expand=True)

    ttk.Label(controls, text="Active column").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.signal_filter_active_column_label = tk.Label(controls, textvariable=workspace.active_column_var, anchor="w", padx=6, pady=3)
    workspace.signal_filter_active_column_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(controls, text="Filter type").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    workspace.signal_filter_operation_combo = ttk.Combobox(
        controls,
        textvariable=workspace.signal_filter_operation_var,
        state="readonly",
        values=SIGNAL_FILTER_OPERATIONS,
    )
    workspace.signal_filter_operation_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Window size").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.signal_filter_window_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Alpha (exp. smoothing)").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.signal_filter_alpha_var).grid(row=3, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="New column name").grid(row=4, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.signal_filter_name_var).grid(row=4, column=1, sticky="ew", padx=5, pady=5)

    ttk.Button(controls, text="Apply Signal Filter", command=workspace._apply_signal_filter).grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10)
    )

    help_text = (
        "moving_average: low-pass smoothing\n"
        "median: spike-resistant smoothing\n"
        "exponential_smoothing: recursive low-pass filter\n"
        "high_pass: original signal minus low-pass trend"
    )
    ttk.Label(controls, text=help_text, justify=tk.LEFT).grid(row=6, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    controls.columnconfigure(1, weight=1)


def build_derived_tab(workspace) -> None:
    controls = ttk.Frame(workspace.derived_tab, padding=10)
    controls.pack(fill=tk.BOTH, expand=True)

    ttk.Label(controls, text="Active column").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.derived_active_column_label = tk.Label(controls, textvariable=workspace.active_column_var, anchor="w", padx=6, pady=3)
    workspace.derived_active_column_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(controls, text="Operation").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    workspace.derived_operation_combo = ttk.Combobox(
        controls,
        textvariable=workspace.derived_operation_var,
        state="readonly",
        values=DERIVED_OPERATIONS,
    )
    workspace.derived_operation_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Reference / second column").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    workspace.derived_reference_combo = ttk.Combobox(
        controls,
        textvariable=workspace.derived_reference_var,
        state="readonly",
    )
    workspace.derived_reference_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Window size").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.derived_window_var).grid(row=3, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="New column name").grid(row=4, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.derived_name_var).grid(row=4, column=1, sticky="ew", padx=5, pady=5)

    ttk.Button(controls, text="Create Derived Signal", command=workspace._apply_derived_signal).grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10)
    )

    help_text = (
        "delta: first difference\n"
        "ratio: source / second column\n"
        "rolling_mean: moving average\n"
        "derivative: dy / dx using a reference column or index\n"
        "normalized: z-score or mean-centered if std = 0"
    )
    ttk.Label(controls, text=help_text, justify=tk.LEFT).grid(row=6, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    controls.columnconfigure(1, weight=1)


def build_frequency_tab(workspace) -> None:
    controls = ttk.Frame(workspace.frequency_tab, padding=10)
    controls.pack(fill=tk.X, padx=5, pady=(5, 0))
    controls.columnconfigure(1, weight=1)

    ttk.Label(controls, text="Method").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.frequency_analysis_combo = ttk.Combobox(
        controls,
        textvariable=workspace.frequency_analysis_var,
        state="readonly",
        values=UI_FREQUENCY_ANALYSIS_METHODS,
    )
    workspace.frequency_analysis_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Signal").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    workspace.frequency_active_column_label = tk.Label(controls, textvariable=workspace.active_column_var, anchor="w", padx=6, pady=3)
    workspace.frequency_active_column_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(controls, text="X / reference").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    workspace.fft_reference_combo = ttk.Combobox(controls, textvariable=workspace.fft_reference_var, state="readonly")
    workspace.fft_reference_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    workspace.frequency_compare_label = ttk.Label(controls, text="Comparison signal")
    workspace.frequency_compare_label.grid(row=3, column=0, sticky="w", padx=5, pady=5)
    workspace.frequency_compare_combo = ttk.Combobox(
        controls,
        textvariable=workspace.frequency_compare_var,
        state="readonly",
    )
    workspace.frequency_compare_combo.grid(row=3, column=1, sticky="ew", padx=5, pady=5)

    workspace.fft_sample_spacing_label = ttk.Label(controls, text="Index step size")
    workspace.fft_sample_spacing_label.grid(row=4, column=0, sticky="w", padx=5, pady=5)
    workspace.fft_sample_spacing_entry = ttk.Entry(controls, textvariable=workspace.fft_sample_spacing_var)
    workspace.fft_sample_spacing_entry.grid(row=4, column=1, sticky="ew", padx=5, pady=5)

    workspace.fft_window_label = ttk.Label(controls, text="Window shape")
    workspace.fft_window_label.grid(row=5, column=0, sticky="w", padx=5, pady=5)
    workspace.fft_window_combo = ttk.Combobox(
        controls,
        textvariable=workspace.fft_window_var,
        state="readonly",
        values=FFT_WINDOW_OPTIONS,
    )
    workspace.fft_window_combo.grid(row=5, column=1, sticky="ew", padx=5, pady=5)

    workspace.welch_segment_length_label = ttk.Label(controls, text="Welch window length")
    workspace.welch_segment_length_label.grid(row=6, column=0, sticky="w", padx=5, pady=5)
    workspace.welch_segment_length_entry = ttk.Entry(controls, textvariable=workspace.welch_segment_length_var)
    workspace.welch_segment_length_entry.grid(row=6, column=1, sticky="ew", padx=5, pady=5)

    workspace.welch_overlap_fraction_label = ttk.Label(controls, text="Welch overlap")
    workspace.welch_overlap_fraction_label.grid(row=7, column=0, sticky="w", padx=5, pady=5)
    workspace.welch_overlap_fraction_entry = ttk.Entry(controls, textvariable=workspace.welch_overlap_fraction_var)
    workspace.welch_overlap_fraction_entry.grid(row=7, column=1, sticky="ew", padx=5, pady=5)

    ttk.Checkbutton(controls, text="Remove trend before analysis", variable=workspace.fft_detrend_var).grid(
        row=8,
        column=0,
        columnspan=2,
        sticky="w",
        padx=5,
        pady=5,
    )

    ttk.Button(controls, text="Analyze Spectrum", command=workspace._compute_fft).grid(
        row=9,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=5,
        pady=(5, 10),
    )

    ttk.Label(
        controls,
        text="Use X / reference when you have time or sample positions. Otherwise the Index step size is used.",
        justify=tk.LEFT,
    ).grid(row=10, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

    ttk.Label(workspace.frequency_tab, textvariable=workspace.fft_summary_var, wraplength=680, justify=tk.LEFT).pack(
        anchor="w",
        padx=10,
        pady=(0, 5),
    )
    ttk.Label(
        workspace.frequency_tab,
        textvariable=workspace.frequency_expectation_var,
        wraplength=680,
        justify=tk.LEFT,
    ).pack(anchor="w", padx=10, pady=(0, 8))

    pane = ttk.Panedwindow(workspace.frequency_tab, orient=tk.HORIZONTAL)
    pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    peaks_frame = ttk.LabelFrame(pane, text="Dominant Peaks")
    pane.add(peaks_frame, weight=1)

    workspace.fft_peaks_container = ttk.Frame(peaks_frame)
    workspace.fft_peaks_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


def build_statistics_tab(workspace) -> None:
    pane = ttk.Panedwindow(workspace.statistics_tab, orient=tk.VERTICAL)
    pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    stats_frame = ttk.LabelFrame(pane, text="Engineering Statistics")
    correlation_frame = ttk.LabelFrame(pane, text="Correlations")
    pane.add(stats_frame, weight=1)
    pane.add(correlation_frame, weight=1)

    workspace.stats_container = ttk.Frame(stats_frame)
    workspace.stats_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    workspace.correlation_container = ttk.Frame(correlation_frame)
    workspace.correlation_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


def build_cycles_tab(workspace) -> None:
    controls = ttk.Frame(workspace.cycles_tab, padding=10)
    controls.pack(fill=tk.X, padx=5, pady=(5, 0))
    controls.columnconfigure(1, weight=1)

    ttk.Label(controls, text="Active column").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.cycles_active_column_label = tk.Label(
        controls,
        textvariable=workspace.active_column_var,
        anchor="w",
        padx=6,
        pady=3,
    )
    workspace.cycles_active_column_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(controls, text="Mode").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    workspace.cycle_mode_combo = ttk.Combobox(
        controls,
        textvariable=workspace.cycle_mode_var,
        state="readonly",
        values=["fixed_length", "rising_edge"],
    )
    workspace.cycle_mode_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Reference").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    workspace.cycles_reference_combo = ttk.Combobox(controls, textvariable=workspace.cycle_reference_var, state="readonly")
    workspace.cycles_reference_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Cycle length").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.cycle_length_var).grid(row=3, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Threshold").grid(row=4, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.cycle_threshold_var).grid(row=4, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Max cycles").grid(row=5, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.cycle_max_cycles_var).grid(row=5, column=1, sticky="ew", padx=5, pady=5)

    ttk.Button(controls, text="Analyze Cycles", command=workspace._compute_cycle_analysis).grid(
        row=6,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=5,
        pady=(5, 10),
    )

    selection_row = ttk.Frame(controls)
    selection_row.grid(row=7, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 8))
    selection_row.columnconfigure(0, weight=1)
    selection_row.columnconfigure(1, weight=1)
    ttk.Button(selection_row, text="Select All Cycles", command=workspace._select_all_cycles).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 4),
    )
    ttk.Button(selection_row, text="Clear Selection", command=workspace._clear_selected_cycles).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=(4, 0),
    )

    ttk.Label(
        controls,
        text="Fixed length uses equal row blocks. Rising edge uses threshold crossings on the selected reference signal.",
        justify=tk.LEFT,
    ).grid(row=8, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

    ttk.Label(workspace.cycles_tab, textvariable=workspace.cycle_summary_var, wraplength=680, justify=tk.LEFT).pack(
        anchor="w",
        padx=10,
        pady=(0, 8),
    )

    pane = ttk.Panedwindow(workspace.cycles_tab, orient=tk.HORIZONTAL)
    pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    metrics_frame = ttk.LabelFrame(pane, text="Cycle Metrics")
    pane.add(metrics_frame, weight=1)

    workspace.cycle_metrics_container = ttk.Frame(metrics_frame)
    workspace.cycle_metrics_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
