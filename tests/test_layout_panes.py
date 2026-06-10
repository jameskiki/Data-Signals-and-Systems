"""Regression tests for top-level resizable pane layout wiring."""

from types import SimpleNamespace

from Source.analysis_app import layout as analysis_layout
from Source.datapreparation_app import layout as dataprep_layout


class FakeWidget:
    def __init__(self, master=None, *args, **kwargs):
        self.master = master
        self.args = args
        self.kwargs = kwargs
        self.pack_calls = []
        self.grid_calls = []
        self.bind_calls = []
        self.config_calls = []
        self.columnconfigure_calls = []
        self.rowconfigure_calls = []
        self.state_calls = []

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def grid(self, **kwargs):
        self.grid_calls.append(kwargs)

    def bind(self, *args, **kwargs):
        self.bind_calls.append((args, kwargs))

    def config(self, **kwargs):
        self.config_calls.append(kwargs)

    def configure(self, **kwargs):
        self.config_calls.append(kwargs)

    def columnconfigure(self, index, weight):
        self.columnconfigure_calls.append((index, weight))

    def rowconfigure(self, index, weight):
        self.rowconfigure_calls.append((index, weight))

    def state(self, values):
        self.state_calls.append(tuple(values))


class FakePanedwindow(FakeWidget):
    instances = []

    def __init__(self, master=None, *args, **kwargs):
        super().__init__(master=master, *args, **kwargs)
        self.add_calls = []
        FakePanedwindow.instances.append(self)

    def add(self, child, **kwargs):
        self.add_calls.append((child, kwargs))


class FakeNotebook(FakeWidget):
    def __init__(self, master=None, *args, **kwargs):
        super().__init__(master=master, *args, **kwargs)
        self.tabs = []

    def add(self, child, **kwargs):
        self.tabs.append((child, kwargs))


class FakeMenu:
    def __init__(self, master=None, tearoff=0):
        self.master = master
        self.tearoff = tearoff
        self.commands = []
        self.cascades = []
        self.separators = 0

    def add_command(self, **kwargs):
        self.commands.append(kwargs)

    def add_cascade(self, **kwargs):
        self.cascades.append(kwargs)

    def add_separator(self):
        self.separators += 1


class FakeTreeview(FakeWidget):
    def __init__(self, master=None, *args, **kwargs):
        super().__init__(master=master, *args, **kwargs)
        self.heading_calls = []
        self.column_calls = []

    def heading(self, column, **kwargs):
        self.heading_calls.append((column, kwargs))

    def column(self, column, **kwargs):
        self.column_calls.append((column, kwargs))

    def yview(self, *_args, **_kwargs):
        return None


class FakeText(FakeWidget):
    def yview(self, *_args, **_kwargs):
        return None


class FakeStatusBar(FakeWidget):
    pass


def _patch_common_widgets(monkeypatch, module):
    FakePanedwindow.instances = []
    monkeypatch.setattr(module.tk, "Menu", FakeMenu)
    monkeypatch.setattr(module, "StatusBar", FakeStatusBar)
    monkeypatch.setattr(module.ttk, "Frame", FakeWidget)
    monkeypatch.setattr(module.ttk, "LabelFrame", FakeWidget)
    monkeypatch.setattr(module.ttk, "Panedwindow", FakePanedwindow)
    monkeypatch.setattr(module.ttk, "Notebook", FakeNotebook)
    monkeypatch.setattr(module.ttk, "Label", FakeWidget)
    monkeypatch.setattr(module.ttk, "Button", FakeWidget)
    monkeypatch.setattr(module.ttk, "Combobox", FakeWidget)
    monkeypatch.setattr(module.ttk, "Scrollbar", FakeWidget)
    monkeypatch.setattr(module.ttk, "Menubutton", FakeWidget)
    monkeypatch.setattr(module.ttk, "Checkbutton", FakeWidget)
    monkeypatch.setattr(module.ttk, "Entry", FakeWidget)
    monkeypatch.setattr(module.ttk, "Treeview", FakeTreeview)
    monkeypatch.setattr(module.tk, "Label", FakeWidget)
    monkeypatch.setattr(module.tk, "Text", FakeText)


def test_analysis_workspace_uses_nested_panes(monkeypatch):
    _patch_common_widgets(monkeypatch, analysis_layout)
    monkeypatch.setattr(analysis_layout, "build_context_panel", lambda *_args: None)
    monkeypatch.setattr(analysis_layout, "build_notebook", lambda *_args: None)
    monkeypatch.setattr(analysis_layout, "build_plot_panel", lambda *_args: None)

    workspace = SimpleNamespace(window=FakeWidget(), notifications=object(), open_documentation=lambda _path: None)

    analysis_layout.build_analysis_workspace_ui(workspace)

    assert len(FakePanedwindow.instances) == 2
    horizontal_pane, vertical_pane = FakePanedwindow.instances
    assert horizontal_pane.kwargs["orient"] == analysis_layout.tk.HORIZONTAL
    assert vertical_pane.kwargs["orient"] == analysis_layout.tk.VERTICAL
    assert len(horizontal_pane.add_calls) == 2
    assert horizontal_pane.add_calls[0][0] is vertical_pane
    assert horizontal_pane.add_calls[0][1] == {"weight": 2}
    assert horizontal_pane.add_calls[1][1] == {"weight": 3}
    assert len(vertical_pane.add_calls) == 2
    assert [call[1] for call in vertical_pane.add_calls] == [{"weight": 1}, {"weight": 3}]


def test_dataprep_main_ui_uses_horizontal_pane(monkeypatch):
    _patch_common_widgets(monkeypatch, dataprep_layout)
    monkeypatch.setattr(dataprep_layout, "build_dataset_selector", lambda *_args: None)
    monkeypatch.setattr(dataprep_layout, "build_manipulations_frame", lambda *_args: None)
    monkeypatch.setattr(dataprep_layout, "build_preview_plot_tab", lambda *_args: None)
    monkeypatch.setattr(dataprep_layout, "build_preview_table_tab", lambda *_args: None)

    app = SimpleNamespace(
        root=FakeWidget(),
        notifications=object(),
        load_files=lambda: None,
        _load_demo_dataset=lambda _key: None,
        load_all_demo_test_signals=lambda: None,
        unload_selected_files=lambda: None,
        merge_selected_files=lambda: None,
        export_clean_data=lambda: None,
        create_prepared_dataset=lambda: None,
        split_selected_dataset=lambda: None,
        plot_selected_data=lambda: None,
        open_analysis_workspace=lambda: None,
        open_documentation=lambda _path: None,
    )

    dataprep_layout.build_main_ui(app, preview_row_limit=100)

    assert len(FakePanedwindow.instances) == 1
    pane = FakePanedwindow.instances[0]
    assert pane.kwargs["orient"] == dataprep_layout.tk.HORIZONTAL
    assert len(pane.add_calls) == 2
    assert [call[1] for call in pane.add_calls] == [{"weight": 3}, {"weight": 5}]