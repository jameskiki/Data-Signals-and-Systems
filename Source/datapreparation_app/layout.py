"""Tk layout builders for the main data analysis application."""

import tkinter as tk
from tkinter import ttk

from Source.shared.documentation_links import DOCUMENTATION_LINKS
from Source.shared.status_widget import StatusBar
from .demo import DEMO_DATASET_SPECS, build_demo_menu_description_lines


def build_main_ui(app, preview_row_limit: int) -> None:
    """Build the main application window UI."""

    menu_bar = tk.Menu(app.root)

    file_menu = tk.Menu(menu_bar, tearoff=0)
    demo_menu = tk.Menu(file_menu, tearoff=0)
    file_menu.add_command(label="Load Files", command=app.load_files)
    for spec in DEMO_DATASET_SPECS:
        spec_menu = tk.Menu(demo_menu, tearoff=0)
        spec_menu.add_command(label=spec.menu_label, state="disabled")
        spec_menu.add_separator()
        for line in build_demo_menu_description_lines(spec):
            spec_menu.add_command(label=line, state="disabled")
        spec_menu.add_separator()
        spec_menu.add_command(
            label="Load This Demo",
            command=lambda demo_key=spec.key: app._load_demo_dataset(demo_key),
        )
        demo_menu.add_cascade(label=spec.menu_label, menu=spec_menu)
    demo_menu.add_separator()
    demo_menu.add_command(label="Load All Demo/Test Signals", command=app.load_all_demo_test_signals)
    file_menu.add_cascade(label="Load Demo/Test Signal", menu=demo_menu)
    file_menu.add_command(label="Unload File", command=app.unload_selected_files)
    file_menu.add_separator()
    file_menu.add_command(label="Merge Selected Files", command=app.merge_selected_files)
    file_menu.add_command(label="Export Clean Data", command=app.export_clean_data)
    menu_bar.add_cascade(label="Files", menu=file_menu)

    preparation_menu = tk.Menu(menu_bar, tearoff=0)
    preparation_menu.add_command(label="Create Prepared Dataset", command=app.create_prepared_dataset)
    preparation_menu.add_command(label="Split Into Subframes", command=app.split_selected_dataset)
    menu_bar.add_cascade(label="Preparation", menu=preparation_menu)

    visualization_menu = tk.Menu(menu_bar, tearoff=0)
    visualization_menu.add_command(label="Plot Data", command=app.plot_selected_data)
    menu_bar.add_cascade(label="Visualization", menu=visualization_menu)

    analysis_menu = tk.Menu(menu_bar, tearoff=0)
    analysis_menu.add_command(label="Open Analysis Workspace", command=app.open_analysis_workspace)
    menu_bar.add_cascade(label="Analysis", menu=analysis_menu)

    help_menu = tk.Menu(menu_bar, tearoff=0)
    for documentation_link in DOCUMENTATION_LINKS:
        help_menu.add_command(
            label=documentation_link.label,
            command=lambda relative_path=documentation_link.relative_path: app.open_documentation(relative_path),
        )
    menu_bar.add_cascade(label="Help", menu=help_menu)

    app.root.config(menu=menu_bar)

    # Status bar must be packed before the workspace so it anchors to the bottom.
    app.status_bar = StatusBar(app.root, app.notifications)
    app.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    workspace = ttk.Frame(app.root, padding=8)
    workspace.pack(fill=tk.BOTH, expand=True)
    workspace.columnconfigure(0, weight=3)
    workspace.columnconfigure(1, weight=5)
    workspace.rowconfigure(1, weight=1)

    build_dataset_selector(app, workspace)
    build_info_tab(app, workspace)
    build_preview_views_notebook(app, workspace, preview_row_limit)


def build_dataset_selector(app, parent: ttk.Frame) -> None:
    """Build a compact dataset table selector spanning both columns."""

    selector_frame = ttk.LabelFrame(parent, text="Datasets")
    selector_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 6))
    selector_frame.columnconfigure(0, weight=1)

    table_frame = ttk.Frame(selector_frame, padding=(5, 4, 5, 4))
    table_frame.pack(fill=tk.X)
    table_frame.columnconfigure(0, weight=1)

    app.dataset_table = ttk.Treeview(
        table_frame,
        columns=("dataset", "rows", "cols", "missing", "source"),
        show="headings",
        selectmode="browse",
        height=3,
    )
    app.dataset_table.grid(row=0, column=0, sticky="ew")
    app.dataset_table.bind("<<TreeviewSelect>>", app._handle_dataset_combo_changed)

    app.dataset_table.heading("dataset", text="Dataset")
    app.dataset_table.heading("rows", text="Rows")
    app.dataset_table.heading("cols", text="Cols")
    app.dataset_table.heading("missing", text="Missing")
    app.dataset_table.heading("source", text="Source")

    app.dataset_table.column("dataset", width=260, stretch=True, anchor=tk.W)
    app.dataset_table.column("rows", width=70, stretch=False, anchor=tk.E)
    app.dataset_table.column("cols", width=60, stretch=False, anchor=tk.E)
    app.dataset_table.column("missing", width=70, stretch=False, anchor=tk.E)
    app.dataset_table.column("source", width=200, stretch=True, anchor=tk.W)

    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=app.dataset_table.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    app.dataset_table.configure(yscrollcommand=scrollbar.set)

    info_frame = ttk.Frame(selector_frame, padding=(5, 0, 5, 4))
    info_frame.pack(fill=tk.X)
    ttk.Label(info_frame, textvariable=app.dataset_shape_var, wraplength=800).pack(anchor="w", padx=5, pady=1)
    ttk.Label(info_frame, textvariable=app.dataset_note_var, wraplength=800).pack(anchor="w", padx=5, pady=(1, 2))


def build_info_tab(app, parent: ttk.Frame) -> None:
    """Build the preparation controls area (left column)."""

    manipulations_frame = ttk.LabelFrame(parent, text="Preparation")
    manipulations_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=0)
    build_manipulations_frame(app, manipulations_frame)

def build_preview_views_notebook(app, parent: ttk.Frame, preview_row_limit: int) -> None:
    """Build the right-side notebook for plot and table previews."""

    preview_frame = ttk.LabelFrame(parent, text="Preview")
    preview_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
    preview_frame.columnconfigure(0, weight=1)
    preview_frame.rowconfigure(0, weight=1)

    preview_notebook = ttk.Notebook(preview_frame)
    preview_notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    plot_tab = ttk.Frame(preview_notebook)
    table_tab = ttk.Frame(preview_notebook)
    preview_notebook.add(plot_tab, text="Plot")
    preview_notebook.add(table_tab, text=f"Table ({preview_row_limit} rows)")

    build_preview_plot_tab(app, plot_tab)
    build_preview_table_tab(app, table_tab, preview_row_limit)


def build_preview_plot_tab(app, parent: ttk.Frame) -> None:
    """Build the overview plot preview tab."""

    preview_plot_frame = ttk.Frame(parent)
    preview_plot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    signal_list_frame = ttk.Frame(preview_plot_frame)
    signal_list_frame.pack(fill=tk.X, padx=5, pady=(5, 2))
    signal_list_frame.columnconfigure(0, weight=1)
    ttk.Label(signal_list_frame, text="Signals").grid(row=0, column=0, sticky="w", pady=(0, 2))
    selector_row = ttk.Frame(signal_list_frame)
    selector_row.grid(row=1, column=0, sticky="ew")
    selector_row.columnconfigure(0, weight=1)

    app._preview_plot_signal_selector_button = ttk.Menubutton(
        selector_row,
        textvariable=app.preview_plot_signal_summary_var,
        direction="below",
    )
    app._preview_plot_signal_selector_button.grid(row=0, column=0, sticky="ew")
    app._preview_plot_signal_selector_menu = tk.Menu(app._preview_plot_signal_selector_button, tearoff=0)
    app._preview_plot_signal_selector_button.configure(menu=app._preview_plot_signal_selector_menu)
    app._preview_plot_signal_selector_button.state(["disabled"])

    preview_action_frame = ttk.Frame(selector_row)
    preview_action_frame.grid(row=0, column=1, sticky="e", padx=(8, 0))
    ttk.Button(preview_action_frame, text="All", width=6, command=app._select_all_preview_plot_signals).pack(side=tk.LEFT)
    ttk.Button(preview_action_frame, text="None", width=6, command=app._clear_selected_preview_plot_signals).pack(
        side=tk.LEFT,
        padx=(6, 0),
    )

    range_controls_frame = ttk.Frame(preview_plot_frame)
    range_controls_frame.pack(fill=tk.X, padx=5, pady=(2, 4))
    ttk.Label(range_controls_frame, text="Signals are updated immediately when selected.").grid(
        row=0,
        column=0,
        sticky="w",
        pady=2,
    )

    app._preview_plot_container = ttk.Frame(preview_plot_frame)
    app._preview_plot_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


def build_preview_table_tab(app, parent: ttk.Frame, preview_row_limit: int) -> None:
    """Build the scrollable preview table tab."""

    container = ttk.Frame(parent, padding=5)
    container.pack(fill=tk.BOTH, expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    ttk.Label(
        container,
        text=f"Showing the first {preview_row_limit} rows of the selected dataset. Scroll vertically and horizontally in this tab to inspect it.",
        justify=tk.LEFT,
        wraplength=640,
    ).grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))

    app._preview_table_container = ttk.Frame(container)
    app._preview_table_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
    app._preview_table_container.columnconfigure(0, weight=1)
    app._preview_table_container.rowconfigure(0, weight=1)


def build_manipulations_frame(app, parent: ttk.LabelFrame) -> None:
    """Build the combined dataset manipulation controls."""

    container = ttk.Frame(parent)
    container.pack(fill=tk.BOTH, expand=True, padx=5, pady=(1, 4))
    build_prepare_tab(app, container)


def build_prepare_tab(app, parent: ttk.Frame) -> None:
    """Build the main dataset preparation workflow tab."""

    container = ttk.Frame(parent, padding=(1, 1, 1, 1))
    container.pack(fill=tk.BOTH, expand=True)
    container.columnconfigure(0, weight=1)

    ttk.Label(
        container,
        text="The preview on the right is only a visual aid. Create a prepared dataset from the full selected dataset, and optionally limit the channels.",
        wraplength=420,
        justify=tk.LEFT,
    ).grid(row=0, column=0, sticky="w", padx=2, pady=(0, 6))

    output_frame = ttk.LabelFrame(container, text="Output")
    output_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 6))
    build_dataset_creation_tab(app, output_frame)

    range_frame = ttk.LabelFrame(container, text="Row Range")
    range_frame.grid(row=2, column=0, sticky="ew", padx=2, pady=(0, 6))
    build_row_range_controls(app, range_frame)

    column_frame = ttk.LabelFrame(container, text="Channels")
    column_frame.grid(row=3, column=0, sticky="ew", padx=2, pady=(0, 5))
    build_column_controls(app, column_frame)

    roles_frame = ttk.LabelFrame(container, text="Roles")
    roles_frame.grid(row=4, column=0, sticky="ew", padx=2, pady=(6, 5))
    build_role_controls_tab(app, roles_frame)


def build_dataset_creation_tab(app, parent: ttk.Frame) -> None:
    """Build the dataset naming and creation controls."""

    frame = ttk.Frame(parent, padding=5)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text="Dataset name").grid(row=0, column=0, sticky="w", padx=5, pady=(0, 2))
    ttk.Entry(frame, textvariable=app.column_output_name_var).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=5,
        pady=(0, 2),
    )
    ttk.Button(frame, text="Create Dataset", command=app.create_prepared_dataset).grid(
        row=1,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=5,
        pady=(6, 5),
    )


def build_row_range_controls(app, parent: ttk.Frame) -> None:
    """Build start/end row-range entries with a Reset button.

    The label dynamically reflects whether a time-role column is present
    (showing units) or falls back to row indices.  Drag-selecting on the
    preview plot fills these entries automatically via SpanSelector.
    """

    frame = ttk.Frame(parent, padding=5)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(3, weight=1)

    ttk.Label(frame, textvariable=app.row_range_label_var).grid(
        row=0, column=0, columnspan=5, sticky="w", padx=5, pady=(0, 4),
    )

    ttk.Label(frame, text="Start").grid(row=1, column=0, sticky="w", padx=(5, 2))
    ttk.Entry(frame, textvariable=app.row_range_start_var, width=14).grid(
        row=1, column=1, sticky="ew", padx=(0, 8),
    )
    ttk.Label(frame, text="End").grid(row=1, column=2, sticky="w", padx=(0, 2))
    ttk.Entry(frame, textvariable=app.row_range_end_var, width=14).grid(
        row=1, column=3, sticky="ew", padx=(0, 8),
    )

    app._row_range_reset_button = ttk.Button(frame, text="Reset", width=6, command=app.reset_row_range)
    app._row_range_reset_button.grid(row=1, column=4, sticky="e", padx=(0, 5))

    ttk.Label(
        frame,
        text="Leave empty for full dataset. Drag on the preview plot to select a range visually.",
        wraplength=420,
        justify=tk.LEFT,
    ).grid(row=2, column=0, columnspan=5, sticky="w", padx=5, pady=(4, 0))


def build_role_controls_tab(app, parent: ttk.Frame) -> None:
    """Build the column role assignment controls."""

    role_frame = ttk.Frame(parent, padding=5)
    role_frame.pack(fill=tk.BOTH, expand=True)
    role_frame.columnconfigure(1, weight=1)
    ttk.Label(
        role_frame,
        text="Use roles after the basic dataset choice is clear so plotting and analysis defaults stay sensible.",
        wraplength=420,
        justify=tk.LEFT,
    ).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 6))
    ttk.Label(role_frame, text="Column").grid(row=1, column=0, sticky="w", padx=5, pady=(0, 2))
    app.role_editor_column_combo = ttk.Combobox(role_frame, textvariable=app.role_editor_column_var, state="readonly")
    app.role_editor_column_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 2))
    ttk.Label(role_frame, text="Role").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    app.role_editor_value_combo = ttk.Combobox(role_frame, textvariable=app.role_editor_value_var, state="readonly")
    app.role_editor_value_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

    role_button_row = ttk.Frame(role_frame)
    role_button_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(6, 5))
    role_button_row.columnconfigure(0, weight=1)
    role_button_row.columnconfigure(1, weight=1)
    ttk.Button(role_button_row, text="Apply Role", command=app.apply_selected_column_role).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 4),
    )
    ttk.Button(role_button_row, text="Reinfer Roles", command=app.reinfer_selected_dataset_roles).grid(
        row=0,
        column=1,
        sticky="ew",
        padx=(4, 0),
    )


def build_column_controls(app, parent: ttk.LabelFrame) -> None:
    """Build the column selection controls for prepared datasets."""

    controls = ttk.Frame(parent, padding=5)
    controls.pack(fill=tk.BOTH, expand=True)
    controls.columnconfigure(1, weight=1)
    controls.columnconfigure(2, weight=0)

    ttk.Label(controls, text="Columns").grid(row=0, column=0, sticky="nw", padx=5, pady=(0, 5))

    selector_frame = ttk.Frame(controls)
    selector_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
    selector_frame.columnconfigure(0, weight=1)

    app._column_selector_button = ttk.Menubutton(
        selector_frame,
        textvariable=app.column_selection_summary_var,
        direction="below",
    )
    app._column_selector_button.grid(row=0, column=0, sticky="ew")
    app._column_selector_menu = tk.Menu(app._column_selector_button, tearoff=0)
    app._column_selector_button.configure(menu=app._column_selector_menu)
    app._column_selector_button.state(["disabled"])

    action_frame = ttk.Frame(selector_frame)
    action_frame.grid(row=0, column=1, sticky="e", padx=(8, 0))
    ttk.Button(action_frame, text="All", width=6, command=app._select_all_columns).pack(side=tk.LEFT)
    ttk.Button(action_frame, text="None", width=6, command=app._clear_selected_columns).pack(side=tk.LEFT, padx=(6, 0))

    ttk.Label(
        controls,
        text="Use the dropdown to choose which channels to keep in the prepared dataset. Leave nothing selected to keep all columns.",
        justify=tk.LEFT,
        wraplength=420,
    ).grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)
