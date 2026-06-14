"""Tk layout builders for the analysis workspace."""

import tkinter as tk
from tkinter import ttk

from Source.shared.documentation_links import DOCUMENTATION_LINKS
from Source.shared.status_widget import StatusBar
from .state import DERIVED_OPERATIONS, FFT_WINDOW_OPTIONS, PREVIEW_ROW_LIMIT, UI_FREQUENCY_ANALYSIS_METHODS
from Source.data_ops.models import SIGNAL_FILTER_OPERATIONS


def build_analysis_workspace_ui(workspace) -> None:
    """Build the full analysis workspace UI."""

    menu_bar = tk.Menu(workspace.window)
    help_menu = tk.Menu(menu_bar, tearoff=0)
    for documentation_link in DOCUMENTATION_LINKS:
        help_menu.add_command(
            label=documentation_link.label,
            command=lambda relative_path=documentation_link.relative_path: workspace.open_documentation(relative_path),
        )
    menu_bar.add_cascade(label="Help", menu=help_menu)
    workspace.window.config(menu=menu_bar)

    main_frame = ttk.Frame(workspace.window, padding=5)
    main_frame.pack(fill=tk.BOTH, expand=True)

    main_pane = ttk.Panedwindow(main_frame, orient=tk.HORIZONTAL)
    main_pane.pack(fill=tk.BOTH, expand=True)

    left_pane = ttk.Panedwindow(main_pane, orient=tk.VERTICAL)
    context_panel = ttk.LabelFrame(left_pane, text="Workspace Context", padding=5)
    notebook_container = ttk.LabelFrame(left_pane, text="Analysis Tools", padding=5)
    plot_panel = ttk.LabelFrame(main_pane, text="Live Plot", padding=5)

    left_pane.add(context_panel, weight=1)
    left_pane.add(notebook_container, weight=3)
    main_pane.add(left_pane, weight=2)
    main_pane.add(plot_panel, weight=3)

    build_context_panel(workspace, context_panel)
    build_notebook(workspace, notebook_container)
    build_plot_panel(workspace, plot_panel)

    # Create and attach the status bar at the bottom
    workspace.status_bar = StatusBar(workspace.window, workspace.notifications)
    workspace.status_bar.pack(side=tk.BOTTOM, fill=tk.X)


def build_context_panel(workspace, parent: ttk.Frame) -> None:
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
    ttk.Button(action_frame, text="Refresh Statistics", command=workspace._refresh_summary_views).pack(fill=tk.X, padx=5, pady=(2, 5))

    overview_frame = ttk.LabelFrame(parent, text="Overview")
    overview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    workspace.sidebar_overview_text = tk.Text(overview_frame, wrap="word", height=8)
    workspace.sidebar_overview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
    overview_scrollbar = ttk.Scrollbar(overview_frame, orient=tk.VERTICAL, command=workspace.sidebar_overview_text.yview)
    overview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
    workspace.sidebar_overview_text.config(yscrollcommand=overview_scrollbar.set, state=tk.DISABLED)


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

    # --- Collapsible Plot Style panel ---
    _build_style_panel(workspace, parent)

    workspace.plot_notebook = ttk.Notebook(parent)
    workspace.plot_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    workspace.signal_plot_tab = ttk.Frame(workspace.plot_notebook)
    workspace.frequency_plot_tab = ttk.Frame(workspace.plot_notebook)
    workspace.cycle_plot_tab = ttk.Frame(workspace.plot_notebook)
    workspace.plot_notebook.add(workspace.signal_plot_tab, text="Time-series Plot")
    workspace.plot_notebook.add(workspace.frequency_plot_tab, text="Frequency Plot")
    workspace.plot_notebook.add(workspace.cycle_plot_tab, text="Cycle Plot")

    workspace.plot_container = ttk.Frame(workspace.signal_plot_tab)
    workspace.plot_container.pack(fill=tk.BOTH, expand=True)
    workspace.frequency_plot_container = ttk.Frame(workspace.frequency_plot_tab)
    workspace.frequency_plot_container.pack(fill=tk.BOTH, expand=True)
    workspace.cycle_plot_container = ttk.Frame(workspace.cycle_plot_tab)
    workspace.cycle_plot_container.pack(fill=tk.BOTH, expand=True)


def _build_style_panel(workspace, parent: ttk.LabelFrame) -> None:
    """Build a collapsible Plot Style panel and attach it to parent."""

    _LEGEND_LOCATIONS = [
        "best", "upper right", "upper left", "lower right", "lower left",
        "upper center", "lower center", "center left", "center right", "center",
    ]
    _MARKERS = ["o", "s", "^", "v", "D", "+", "x", ".", "None"]
    _FONT_FAMILIES = ["sans-serif", "serif", "monospace"]

    style_vars = workspace.style_vars

    # Toggle button row
    toggle_frame = ttk.Frame(parent)
    toggle_frame.pack(fill=tk.X, padx=5, pady=(0, 2))

    _panel_visible = tk.BooleanVar(value=False)

    # Content frame (hidden by default)
    content_frame = ttk.LabelFrame(parent, text="Plot Style", padding=4)

    def _toggle():
        if _panel_visible.get():
            content_frame.pack_forget()
            _panel_visible.set(False)
            toggle_btn.config(text="▶ Plot Style")
        else:
            content_frame.pack(fill=tk.X, padx=5, pady=(0, 4), before=workspace.plot_notebook)
            _panel_visible.set(True)
            toggle_btn.config(text="▼ Plot Style")

    toggle_btn = ttk.Button(toggle_frame, text="▶ Plot Style", command=_toggle)
    toggle_btn.pack(side=tk.LEFT)

    # ── Row 0: checkbuttons ──────────────────────────────────────────────────
    check_row = ttk.Frame(content_frame)
    check_row.pack(fill=tk.X, pady=(2, 0))
    ttk.Checkbutton(check_row, text="Grid", variable=style_vars.show_grid).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Checkbutton(check_row, text="Subgrid", variable=style_vars.show_subgrid).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Checkbutton(check_row, text="Legend", variable=style_vars.show_legend).pack(side=tk.LEFT)

    # ── Row 1: alpha sliders ─────────────────────────────────────────────────
    alpha_row = ttk.Frame(content_frame)
    alpha_row.pack(fill=tk.X, pady=(4, 0))
    ttk.Label(alpha_row, text="Grid α").grid(row=0, column=0, sticky="w", padx=(0, 4))
    ttk.Scale(alpha_row, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
              variable=style_vars.grid_alpha).grid(row=0, column=1, sticky="ew", padx=(0, 12))
    ttk.Label(alpha_row, text="Subgrid α").grid(row=0, column=2, sticky="w", padx=(0, 4))
    ttk.Scale(alpha_row, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
              variable=style_vars.subgrid_alpha).grid(row=0, column=3, sticky="ew")
    alpha_row.columnconfigure(1, weight=1)
    alpha_row.columnconfigure(3, weight=1)

    # ── Row 2: line width / marker size spinboxes ────────────────────────────
    line_row = ttk.Frame(content_frame)
    line_row.pack(fill=tk.X, pady=(4, 0))

    vcmd_float = (parent.register(lambda v: _validate_float(v, 0.1, 50.0)), "%P")

    ttk.Label(line_row, text="Line width").grid(row=0, column=0, sticky="w", padx=(0, 4))
    ttk.Spinbox(
        line_row, from_=0.1, to=10.0, increment=0.1, width=6,
        textvariable=style_vars.line_width,
        validate="focusout", validatecommand=vcmd_float,
    ).grid(row=0, column=1, sticky="w", padx=(0, 12))
    ttk.Label(line_row, text="Marker size").grid(row=0, column=2, sticky="w", padx=(0, 4))
    ttk.Spinbox(
        line_row, from_=0.5, to=20.0, increment=0.5, width=6,
        textvariable=style_vars.marker_size,
        validate="focusout", validatecommand=vcmd_float,
    ).grid(row=0, column=3, sticky="w")

    # ── Row 3: fontsize spinboxes ─────────────────────────────────────────────
    font_row = ttk.Frame(content_frame)
    font_row.pack(fill=tk.X, pady=(4, 0))

    vcmd_int = (parent.register(lambda v: _validate_int(v, 4, 32)), "%P")

    for col, (label, var) in enumerate([
        ("Title", style_vars.title_fontsize),
        ("Label", style_vars.label_fontsize),
        ("Tick", style_vars.tick_fontsize),
        ("Legend", style_vars.legend_fontsize),
    ]):
        ttk.Label(font_row, text=label).grid(row=0, column=col * 2, sticky="w", padx=(0 if col == 0 else 8, 2))
        ttk.Spinbox(
            font_row, from_=4, to=32, increment=1, width=4,
            textvariable=var,
            validate="focusout", validatecommand=vcmd_int,
        ).grid(row=0, column=col * 2 + 1, sticky="w")

    # ── Row 4: comboboxes ─────────────────────────────────────────────────────
    combo_row = ttk.Frame(content_frame)
    combo_row.pack(fill=tk.X, pady=(4, 0))

    ttk.Label(combo_row, text="Font").grid(row=0, column=0, sticky="w", padx=(0, 4))
    ttk.Combobox(
        combo_row, textvariable=style_vars.font_family,
        values=_FONT_FAMILIES, state="readonly", width=12,
    ).grid(row=0, column=1, sticky="w", padx=(0, 12))

    ttk.Label(combo_row, text="Marker").grid(row=0, column=2, sticky="w", padx=(0, 4))
    ttk.Combobox(
        combo_row, textvariable=style_vars.marker,
        values=_MARKERS, state="readonly", width=6,
    ).grid(row=0, column=3, sticky="w", padx=(0, 12))

    ttk.Label(combo_row, text="Legend pos").grid(row=0, column=4, sticky="w", padx=(0, 4))
    ttk.Combobox(
        combo_row, textvariable=style_vars.legend_location,
        values=_LEGEND_LOCATIONS, state="readonly", width=12,
    ).grid(row=0, column=5, sticky="w")

    # ── Row 5: reset button ──────────────────────────────────────────────────
    reset_row = ttk.Frame(content_frame)
    reset_row.pack(fill=tk.X, pady=(6, 2))
    ttk.Button(
        reset_row, text="Reset to Defaults",
        command=style_vars.reset_to_defaults,
    ).pack(side=tk.RIGHT)


def _validate_float(value: str, lo: float, hi: float) -> bool:
    """Spinbox focusout validator — accept any parseable float in [lo, hi]."""
    try:
        return lo <= float(value) <= hi
    except (ValueError, TypeError):
        return False


def _validate_int(value: str, lo: int, hi: int) -> bool:
    """Spinbox focusout validator — accept any parseable int in [lo, hi]."""
    try:
        return lo <= int(value) <= hi
    except (ValueError, TypeError):
        return False


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
    resample_tab = ttk.Frame(filter_notebook)
    filter_notebook.add(signal_filter_tab, text="Signal Processing")
    filter_notebook.add(resample_tab, text="Resample")
    filter_notebook.add(simple_filter_tab, text="Simple Filtering")

    build_simple_filter_tab(workspace, simple_filter_tab)
    build_signal_filter_tab(workspace, signal_filter_tab)
    build_resample_tab(workspace, resample_tab)


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

    # Window size frame (moving_average, median, high_pass)
    workspace.signal_filter_window_frame = ttk.Frame(controls)
    workspace.signal_filter_window_frame.columnconfigure(1, weight=1)
    ttk.Label(workspace.signal_filter_window_frame, text="Window size").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.signal_filter_window_frame, textvariable=workspace.signal_filter_window_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    workspace.signal_filter_window_frame.grid(row=2, column=0, columnspan=2, sticky="ew")

    # Alpha frame (exponential_smoothing)
    workspace.signal_filter_alpha_frame = ttk.Frame(controls)
    workspace.signal_filter_alpha_frame.columnconfigure(1, weight=1)
    ttk.Label(workspace.signal_filter_alpha_frame, text="Alpha (exp. smoothing)").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.signal_filter_alpha_frame, textvariable=workspace.signal_filter_alpha_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    workspace.signal_filter_alpha_frame.grid(row=3, column=0, columnspan=2, sticky="ew")

    # Butterworth frame (butterworth_lowpass / highpass / bandpass)
    workspace.signal_filter_butterworth_frame = ttk.Frame(controls)
    workspace.signal_filter_butterworth_frame.columnconfigure(1, weight=1)
    ttk.Label(workspace.signal_filter_butterworth_frame, text="Cutoff freq [Hz]").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.signal_filter_butterworth_frame, textvariable=workspace.signal_filter_cutoff_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    workspace.signal_filter_bandpass_frame = ttk.Frame(workspace.signal_filter_butterworth_frame)
    workspace.signal_filter_bandpass_frame.columnconfigure(1, weight=1)
    ttk.Label(workspace.signal_filter_bandpass_frame, text="High cutoff freq [Hz]").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.signal_filter_bandpass_frame, textvariable=workspace.signal_filter_cutoff_high_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    workspace.signal_filter_bandpass_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
    ttk.Label(workspace.signal_filter_butterworth_frame, text="Filter order").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.signal_filter_butterworth_frame, textvariable=workspace.signal_filter_order_var).grid(row=2, column=1, sticky="ew", padx=5, pady=5)
    ttk.Label(workspace.signal_filter_butterworth_frame, text="Sample spacing [s]").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.signal_filter_butterworth_frame, textvariable=workspace.signal_filter_spacing_var).grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(
        workspace.signal_filter_butterworth_frame,
        textvariable=workspace.signal_filter_spacing_status_var,
        fg="#1d4ed8",
    ).grid(row=3, column=2, sticky="w", padx=5, pady=5)
    workspace.signal_filter_butterworth_frame.grid(row=4, column=0, columnspan=2, sticky="ew")

    ttk.Label(controls, text="New column name").grid(row=5, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.signal_filter_name_var).grid(row=5, column=1, sticky="ew", padx=5, pady=5)

    ttk.Button(controls, text="Apply Signal Filter", command=workspace._apply_signal_filter).grid(
        row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10)
    )

    help_text = (
        "moving_average: low-pass smoothing\n"
        "median: spike-resistant smoothing\n"
        "exponential_smoothing: recursive low-pass filter\n"
        "high_pass: original signal minus low-pass trend\n"
        "butterworth_lowpass: zero-phase Butterworth LP\n"
        "butterworth_highpass: zero-phase Butterworth HP\n"
        "butterworth_bandpass: zero-phase Butterworth BP (set low and high cutoffs)\n"
        "  Butterworth filters need cutoff, order, and spacing"
    )
    ttk.Label(controls, text=help_text, justify=tk.LEFT).grid(row=7, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    controls.columnconfigure(1, weight=1)


def build_resample_tab(workspace, parent: ttk.Frame) -> None:
    controls = ttk.Frame(parent, padding=10)
    controls.pack(fill=tk.BOTH, expand=True)

    ttk.Label(controls, text="Time column").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.resample_time_combo = ttk.Combobox(controls, textvariable=workspace.resample_time_var, state="readonly")
    workspace.resample_time_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    ttk.Label(controls, text="Target spacing").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(controls, textvariable=workspace.resample_spacing_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(controls, textvariable=workspace.resample_spacing_status_var, fg="#1d4ed8").grid(
        row=1,
        column=2,
        sticky="w",
        padx=5,
        pady=5,
    )

    ttk.Button(controls, text="Resample to Uniform Grid", command=workspace._apply_resample).grid(
        row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10)
    )

    ttk.Label(
        controls,
        text="Interpolates all numeric columns onto an evenly-spaced time grid. "
             "This replaces the working dataframe. Use Reset to undo.",
        justify=tk.LEFT,
        wraplength=380,
    ).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5)
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
        "normalized: z-score or mean-centered if std = 0\n"
        "detrend: remove polynomial trend (order via window size 1-3)\n"
        "integrate: cumulative trapezoidal integration\n"
        "rms_envelope: rolling RMS with window size\n"
        "hilbert_envelope: amplitude envelope via Hilbert transform"
    )
    ttk.Label(controls, text=help_text, justify=tk.LEFT).grid(row=6, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    controls.columnconfigure(1, weight=1)


def build_frequency_tab(workspace) -> None:

    controls = ttk.Frame(workspace.frequency_tab, padding=10)
    controls.pack(fill=tk.X, padx=5, pady=(5, 0))
    controls.columnconfigure(1, weight=1)

    # Method selection
    ttk.Label(controls, text="Method").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.frequency_analysis_combo = ttk.Combobox(
        controls,
        textvariable=workspace.frequency_analysis_var,
        state="readonly",
        values=UI_FREQUENCY_ANALYSIS_METHODS,
    )
    workspace.frequency_analysis_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

    # Signal selection
    ttk.Label(controls, text="Signal").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    workspace.frequency_active_column_label = tk.Label(controls, textvariable=workspace.active_column_var, anchor="w", padx=6, pady=3)
    workspace.frequency_active_column_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)

    # Reference selection
    ttk.Label(controls, text="X / reference").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    workspace.fft_reference_combo = ttk.Combobox(controls, textvariable=workspace.fft_reference_var, state="readonly")
    workspace.fft_reference_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

    # Detrend and analyze
    ttk.Checkbutton(controls, text="Remove trend before analysis", variable=workspace.fft_detrend_var).grid(
        row=3,
        column=0,
        columnspan=2,
        sticky="w",
        padx=5,
        pady=5,
    )

    # --- Algorithm-specific frames ---
    # Comparison signal (Transfer/Coherence)
    workspace.comparison_frame = ttk.Frame(controls)
    workspace.frequency_compare_label = ttk.Label(workspace.comparison_frame, text="Comparison signal")
    workspace.frequency_compare_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.frequency_compare_combo = ttk.Combobox(
        workspace.comparison_frame,
        textvariable=workspace.frequency_compare_var,
        state="readonly",
    )
    workspace.frequency_compare_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    workspace.comparison_frame.grid(row=4, column=0, columnspan=2, sticky="ew")


    # --- General frequency options (shown for all methods) ---
    workspace.freq_general_frame = ttk.Frame(controls)
    workspace.fft_sample_spacing_label = ttk.Label(workspace.freq_general_frame, text="Index step size")
    workspace.fft_sample_spacing_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.fft_sample_spacing_entry = ttk.Entry(workspace.freq_general_frame, textvariable=workspace.fft_sample_spacing_var)
    workspace.fft_sample_spacing_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(workspace.freq_general_frame, textvariable=workspace.fft_sample_spacing_status_var, fg="#1d4ed8").grid(
        row=0,
        column=2,
        sticky="w",
        padx=5,
        pady=5,
    )

    workspace.fft_window_label = ttk.Label(workspace.freq_general_frame, text="Window shape")
    workspace.fft_window_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
    workspace.fft_window_combo = ttk.Combobox(
        workspace.freq_general_frame,
        textvariable=workspace.fft_window_var,
        state="readonly",
        values=FFT_WINDOW_OPTIONS,
    )
    workspace.fft_window_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    workspace.freq_general_frame.grid(row=5, column=0, columnspan=2, sticky="ew")

    # --- Welch-specific options (only for Welch, Transfer, Coherence) ---
    workspace.welch_specific_frame = ttk.Frame(controls)
    workspace.welch_segment_length_label = ttk.Label(workspace.welch_specific_frame, text="Welch window length")
    workspace.welch_segment_length_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.welch_segment_length_entry = ttk.Entry(workspace.welch_specific_frame, textvariable=workspace.welch_segment_length_var)
    workspace.welch_segment_length_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(workspace.welch_specific_frame, textvariable=workspace.welch_segment_length_status_var, fg="#1d4ed8").grid(
        row=0,
        column=2,
        sticky="w",
        padx=5,
        pady=5,
    )

    workspace.welch_overlap_fraction_label = ttk.Label(workspace.welch_specific_frame, text="Welch overlap")
    workspace.welch_overlap_fraction_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
    workspace.welch_overlap_fraction_entry = ttk.Entry(workspace.welch_specific_frame, textvariable=workspace.welch_overlap_fraction_var)
    workspace.welch_overlap_fraction_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    workspace.welch_specific_frame.grid(row=6, column=0, columnspan=2, sticky="ew")

    ttk.Button(controls, text="Analyze Spectrum", command=workspace._compute_fft).grid(
        row=7,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=5,
        pady=(5, 10),
    )

    ttk.Label(
        controls,
        text="FFT: single-shot spectrum. Welch: averaged PSD. Transfer Estimate / Coherence: two-signal relationship (set comparison signal). Spectrogram: time-frequency heatmap. Use X / reference for time-based spacing.",
        justify=tk.LEFT,
        wraplength=380,
    ).grid(row=8, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

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

    # Always visible
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
        values=["fixed_length", "rising_edge", "zero_crossing", "peak"],
    )
    workspace.cycle_mode_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    # --- Option frames ---
    # Fixed length
    workspace.cycle_fixed_frame = ttk.Frame(controls)
    ttk.Label(workspace.cycle_fixed_frame, text="Cycle length").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.cycle_fixed_frame, textvariable=workspace.cycle_length_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    tk.Label(workspace.cycle_fixed_frame, textvariable=workspace.cycle_length_status_var, fg="#1d4ed8").grid(
        row=0,
        column=2,
        sticky="w",
        padx=5,
        pady=5,
    )
    workspace.cycle_fixed_frame.grid(row=2, column=0, columnspan=2, sticky="ew")

    # Rising edge & zero crossing
    workspace.cycle_edge_frame = ttk.Frame(controls)
    ttk.Label(workspace.cycle_edge_frame, text="Reference").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.cycles_reference_combo = ttk.Combobox(workspace.cycle_edge_frame, textvariable=workspace.cycle_reference_var, state="readonly")
    workspace.cycles_reference_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    ttk.Label(workspace.cycle_edge_frame, text="Threshold").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.cycle_edge_frame, textvariable=workspace.cycle_threshold_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    workspace.cycle_edge_frame.grid(row=3, column=0, columnspan=2, sticky="ew")

    # Peak
    workspace.cycle_peak_frame = ttk.Frame(controls)
    ttk.Label(workspace.cycle_peak_frame, text="Reference").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    workspace.cycles_reference_combo_peak = ttk.Combobox(workspace.cycle_peak_frame, textvariable=workspace.cycle_reference_var, state="readonly")
    workspace.cycles_reference_combo_peak.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    ttk.Label(workspace.cycle_peak_frame, text="Prominence").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.cycle_peak_frame, textvariable=workspace.cycle_prominence_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    workspace.cycle_peak_frame.grid(row=4, column=0, columnspan=2, sticky="ew")

    # Max cycles (shown for all except fixed_length)
    workspace.cycle_max_frame = ttk.Frame(controls)
    ttk.Label(workspace.cycle_max_frame, text="Max cycles").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(workspace.cycle_max_frame, textvariable=workspace.cycle_max_cycles_var).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
    workspace.cycle_max_frame.grid(row=5, column=0, columnspan=2, sticky="ew")

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
    selection_row.columnconfigure(2, weight=1)
    selection_row.columnconfigure(3, weight=1)
    ttk.Button(selection_row, text="Exclude Selected", command=workspace._exclude_selected_cycles).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 4),
    )
    ttk.Button(selection_row, text="Restore Selected", command=workspace._restore_selected_cycles).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=4,
    )
    ttk.Button(selection_row, text="Restore All", command=workspace._restore_all_cycles).grid(
        row=0,
        column=2,
        sticky="ew",
        padx=4,
    )
    ttk.Button(selection_row, text="Clear Selection", command=workspace._clear_selected_cycles).grid(
        row=0,
        column=3,
        sticky="ew",
        padx=(4, 0),
    )

    metrics_toggle_frame = ttk.LabelFrame(controls, text="C2C Metrics")
    metrics_toggle_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 8))
    for column_index in range(3):
        metrics_toggle_frame.columnconfigure(column_index, weight=1)
    metric_toggle_specs = [
        ("mean", "Mean"),
        ("rms", "RMS"),
        ("peak_to_peak", "P2P"),
        ("min", "Min"),
        ("max", "Max"),
    ]
    for metric_index, (metric_key, metric_label) in enumerate(metric_toggle_specs):
        ttk.Checkbutton(
            metrics_toggle_frame,
            text=metric_label,
            variable=workspace.cycle_metric_toggle_vars[metric_key],
        ).grid(
            row=metric_index // 3,
            column=metric_index % 3,
            sticky="w",
            padx=5,
            pady=3,
        )

    ttk.Button(controls, text="Apply Kept Cycles To Working Data", command=workspace._apply_kept_cycles_to_working_data).grid(
        row=9,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=5,
        pady=(0, 8),
    )

    ttk.Label(
        controls,
        text="Fixed length: equal row blocks. Rising edge: threshold crossings. Zero crossing: sign-change points. Peak: successive signal peaks (set prominence to filter weak peaks).",
        justify=tk.LEFT,
        wraplength=380,
    ).grid(row=10, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 5))

    ttk.Label(workspace.cycles_tab, textvariable=workspace.cycle_summary_var, wraplength=680, justify=tk.LEFT).pack(
        anchor="w",
        padx=10,
        pady=(0, 8),
    )

    pane = ttk.Panedwindow(workspace.cycles_tab, orient=tk.HORIZONTAL)
    pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    metrics_frame = ttk.LabelFrame(pane, text="Cycle Metrics")
    pane.add(metrics_frame, weight=1)

    metrics_legend = ttk.Frame(metrics_frame)
    metrics_legend.pack(fill=tk.X, padx=5, pady=(5, 0))
    ttk.Label(metrics_legend, text="Legend:").pack(side=tk.LEFT)
    tk.Label(metrics_legend, text=" outlier ", bg="#fff7d6", fg="#7c2d12").pack(side=tk.LEFT, padx=(6, 4))
    tk.Label(metrics_legend, text=" excluded ", bg="#f1f5f9", fg="#64748b").pack(side=tk.LEFT, padx=4)
    tk.Label(metrics_legend, text=" excluded + outlier ", bg="#f8efe4", fg="#7c2d12").pack(side=tk.LEFT, padx=4)

    workspace.cycle_metrics_container = ttk.Frame(metrics_frame)
    workspace.cycle_metrics_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
