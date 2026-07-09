"""Tests for shared.presentation_shell helpers."""

import matplotlib.backends.backend_tkagg as backend_tkagg

from Source.shared import presentation_shell
from Source.shared.presentation_shell import PresentationShellMixin


class DummyVar:
    def __init__(self, value=False):
        self.value = value
        self.traces = []

    def trace_add(self, mode, handler):
        self.traces.append((mode, handler))

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyMenu:
    def __init__(self):
        self.commands = []
        self.checkbuttons = []
        self.separators = 0
        self.delete_calls = []

    def delete(self, start, end):
        self.delete_calls.append((start, end))

    def add_command(self, **kwargs):
        self.commands.append(kwargs)

    def add_checkbutton(self, **kwargs):
        self.checkbuttons.append(kwargs)

    def add_separator(self):
        self.separators += 1


class DummyButton:
    def __init__(self):
        self.state_calls = []

    def state(self, values):
        self.state_calls.append(tuple(values))


class DummyTree:
    def __init__(self, selected=None, children=None):
        self._selected = list(selected or [])
        self._children = list(children or [])
        self.selection_set_calls = []
        self.selection_remove_calls = []

    def selection(self):
        return tuple(self._selected)

    def get_children(self):
        return tuple(self._children)

    def selection_set(self, items):
        self.selection_set_calls.append(tuple(items))
        self._selected = list(items)

    def selection_remove(self, items):
        self.selection_remove_calls.append(tuple(items))
        removed = set(items)
        self._selected = [item for item in self._selected if item not in removed]


class DummyListbox:
    def __init__(self, selected=None):
        self._selected = list(selected or [])
        self.deleted = []
        self.inserted = []

    def delete(self, start, end):
        self.deleted.append((start, end))

    def insert(self, index, value):
        self.inserted.append((index, value))

    def curselection(self):
        return tuple(self._selected)


class DummyWindow:
    def __init__(self):
        self.title_calls = []
        self.geometry_calls = []
        self.protocol_calls = []
        self.after_idle_calls = []
        self.bind_calls = []
        self.after_cancel_calls = []
        self.transient_calls = []
        self.grab_set_calls = 0
        self.resizable_calls = []

    def title(self, value):
        self.title_calls.append(value)

    def geometry(self, value):
        self.geometry_calls.append(value)

    def protocol(self, name, callback):
        self.protocol_calls.append((name, callback))

    def transient(self, parent):
        self.transient_calls.append(parent)

    def grab_set(self):
        self.grab_set_calls += 1

    def resizable(self, width, height):
        self.resizable_calls.append((width, height))

    def after_idle(self, callback):
        self.after_idle_calls.append(callback)
        callback()

    def bind(self, event, callback):
        self.bind_calls.append((event, callback))

    def after_cancel(self, job):
        self.after_cancel_calls.append(job)

    def destroy(self):
        self.destroyed = True


class DummyFrame:
    def __init__(self, master=None):
        self.master = master
        self.pack_calls = []
        self.bind_calls = []

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def bind(self, event, callback):
        self.bind_calls.append((event, callback))


class DummyFigure:
    def __init__(self):
        self.size_calls = []

    def get_dpi(self):
        return 100.0

    def set_size_inches(self, width, height, forward=True):
        self.size_calls.append((width, height, forward))


class DummyCanvasWidget:
    def __init__(self, master=None):
        self.master = master

    def pack(self, **kwargs):
        self.pack_calls = kwargs

    def update_idletasks(self):
        return None

    def winfo_width(self):
        return 400

    def winfo_height(self):
        return 250


class DummyCanvas:
    def __init__(self, figure, master=None):
        self.figure = figure
        self.master = master
        self.draw_calls = 0
        self.draw_idle_calls = 0
        self.widget = DummyCanvasWidget(master=master)

    def draw(self):
        self.draw_calls += 1

    def draw_idle(self):
        self.draw_idle_calls += 1

    def get_tk_widget(self):
        return self.widget


class DummyToolbar:
    def __init__(self, canvas, container):
        self.canvas = canvas
        self.container = container
        self.update_calls = 0
        self.pack_calls = []

    def update(self):
        self.update_calls += 1

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)


def test_format_selector_summary_handles_truncation_and_selection():
    summary = PresentationShellMixin.format_selector_summary(
        ["a", "b", "c"],
        visible_count=2,
        hidden_count=1,
        empty_text="No items available",
        choose_text="Choose items",
    )

    assert summary == "3 selected: a, b, +1 (showing 2 of 3)"


def test_build_checkbutton_selector_menu_populates_visible_items(monkeypatch):
    monkeypatch.setattr(presentation_shell.tk, "BooleanVar", DummyVar)

    shell = PresentationShellMixin()
    menu = DummyMenu()
    button = DummyButton()

    selector_vars, hidden_count = shell._build_checkbutton_selector_menu(
        menu=menu,
        button=button,
        items=["alpha", "beta", "gamma"],
        selected_items=["beta"],
        max_items=2,
        get_colors=lambda name: (f"bg-{name}", f"fg-{name}"),
        on_changed=lambda *_args: None,
        on_select_all=lambda: None,
        on_clear_selection=lambda: None,
        hidden_label="channels",
    )

    assert hidden_count == 1
    assert list(selector_vars) == ["alpha", "beta"]
    assert selector_vars["beta"].get() is True
    assert menu.commands[0]["label"] == "Select all"
    assert menu.commands[1]["label"] == "Clear selection"
    assert menu.checkbuttons[0]["label"] == "alpha"
    assert menu.checkbuttons[1]["label"] == "beta"
    assert button.state_calls == [("!disabled",)]


def test_treeview_selection_helpers_map_and_toggle_selection():
    shell = PresentationShellMixin()
    tree = DummyTree(selected=["row-2", "row-1", "row-2"], children=["row-1", "row-2"])

    assert shell.get_selected_treeview_indices(tree, {"row-1": 0, "row-2": 1}) == [0, 1]

    shell.select_all_treeview_items(tree)
    assert tree.selection_set_calls[-1] == ("row-1", "row-2")

    shell.clear_treeview_selection(tree)
    assert tree.selection_remove_calls[-1] == ("row-1", "row-2")


def test_listbox_helpers_populate_and_map_selection():
    shell = PresentationShellMixin()
    listbox = DummyListbox(selected=[0, 2])

    shell.populate_listbox(listbox, ["alpha", "beta", "gamma"])
    assert listbox.deleted == [(0, presentation_shell.tk.END)]
    assert listbox.inserted == [
        (presentation_shell.tk.END, "alpha"),
        (presentation_shell.tk.END, "beta"),
        (presentation_shell.tk.END, "gamma"),
    ]
    assert shell.get_selected_listbox_items(listbox, ["alpha", "beta", "gamma"]) == ["alpha", "gamma"]


def test_show_figure_in_window_wires_canvas_and_close(monkeypatch):
    monkeypatch.setattr(presentation_shell.tk, "Toplevel", lambda _root: DummyWindow())
    monkeypatch.setattr(presentation_shell.ttk, "Frame", DummyFrame)
    monkeypatch.setattr(backend_tkagg, "FigureCanvasTkAgg", DummyCanvas)
    monkeypatch.setattr(backend_tkagg, "NavigationToolbar2Tk", DummyToolbar)

    shell = PresentationShellMixin()
    figure = DummyFigure()
    root = object()

    shell.show_figure_in_window(root, figure, "Demo", "600x400")

    # The helper should create and size the window, then draw the figure and hook close handling.
    assert figure.size_calls == [(4.0, 2.5, True)]


def test_configure_modal_dialog_sets_standard_window_state():
    shell = PresentationShellMixin()
    dialog = DummyWindow()
    parent = object()

    shell.configure_modal_dialog(dialog, parent=parent, title="Modal", geometry="320x240", resizable=(True, False))

    assert dialog.title_calls == ["Modal"]
    assert dialog.geometry_calls == ["320x240"]