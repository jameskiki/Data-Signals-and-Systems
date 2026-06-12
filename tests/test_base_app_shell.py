"""Tests for shared.base_app_shell.BaseAppShell."""

import matplotlib.backends.backend_tkagg as backend_tkagg
import matplotlib.pyplot as plt

from Source.shared.base_app_shell import BaseAppShell
from Source.shared import base_app_shell
from Source.shared.notifications import NotificationSeverity


class DummyVar:
    """Simple variable mock that records trace_add registrations."""

    def __init__(self):
        self.calls = []

    def trace_add(self, mode, handler):
        self.calls.append((mode, handler))


class DummyWidget:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class DummyContainer:
    def __init__(self, children=None):
        self._children = list(children or [])

    def winfo_children(self):
        return self._children


class DummyRootWindow:
    def __init__(self):
        self.after_idle_calls = []

    def after_idle(self, callback):
        self.after_idle_calls.append(callback)


class DummyFigure:
    def __init__(self):
        self.canvas = None


class FakeCanvasWidget:
    def __init__(self, master=None, exists=True):
        self.master = master
        self._exists = exists
        self.pack_calls = []
        self.destroyed = False

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def winfo_exists(self):
        return 1 if self._exists else 0

    def destroy(self):
        self.destroyed = True
        self._exists = False


class FakeFigureCanvas:
    def __init__(self, figure, master):
        self.figure = figure
        self.master = master
        self.draw_calls = 0
        self.draw_idle_calls = 0
        self.widget = FakeCanvasWidget(master=master)

    def draw(self):
        self.draw_calls += 1

    def draw_idle(self):
        self.draw_idle_calls += 1

    def get_tk_widget(self):
        return self.widget


class FakeToolbar:
    def __init__(self, canvas, container):
        self.canvas = canvas
        self.container = container
        self.master = container
        self._exists = True
        self.destroyed = False
        self.update_calls = 0
        self.pack_calls = []

    def update(self):
        self.update_calls += 1

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def winfo_exists(self):
        return 1 if self._exists else 0

    def destroy(self):
        self.destroyed = True
        self._exists = False


def test_error_dialog_marks_failed_on_exception(monkeypatch):
    shell = BaseAppShell()
    shown = []
    monkeypatch.setattr(base_app_shell.messagebox, "showerror", lambda title, msg: shown.append((title, msg)))

    with shell._error_dialog("Operation Error") as failed:
        raise ValueError("invalid value")

    assert len(shown) == 1
    assert shown[0][0] == "Operation Error"
    assert "invalid value" in shown[0][1]
    assert len(failed) == 1
    assert isinstance(failed[0], ValueError)


def test_error_dialog_no_exception_keeps_failed_empty(monkeypatch):
    shell = BaseAppShell()
    shown = []
    monkeypatch.setattr(base_app_shell.messagebox, "showerror", lambda title, msg: shown.append((title, msg)))

    with shell._error_dialog("Operation Error") as failed:
        _ = 1 + 1

    assert failed == []
    assert shown == []


def test_notify_success_posts_notification():
    shell = BaseAppShell()
    posted = []
    shell._ensure_notifications().subscribe(lambda notification: posted.append(notification))

    shell.notify_success("Done")

    assert len(posted) == 1
    assert posted[0].message == "Done"
    assert posted[0].severity == NotificationSeverity.SUCCESS


def test_notify_warning_posts_notification_with_details():
    shell = BaseAppShell()
    posted = []
    shell._ensure_notifications().subscribe(lambda notification: posted.append(notification))

    shell.notify_warning("Invalid", details="x must be > 0")

    assert len(posted) == 1
    assert posted[0].message == "Invalid"
    assert posted[0].details == "x must be > 0"
    assert posted[0].severity == NotificationSeverity.WARNING


def test_bind_write_registers_handler_for_all_vars():
    shell = BaseAppShell()
    var_a = DummyVar()
    var_b = DummyVar()

    def _handler(*_args):
        return None

    shell._bind_write(_handler, var_a, var_b)

    assert var_a.calls == [("write", _handler)]
    assert var_b.calls == [("write", _handler)]


class FigureForSyncSize:
    def __init__(self, dpi=100.0):
        self._dpi = dpi
        self.last_size = None

    def get_dpi(self):
        return self._dpi

    def set_size_inches(self, width, height, forward=True):
        self.last_size = (width, height, forward)


class WidgetForSyncSize:
    def __init__(self, *, exists=True, width=500, height=300):
        self._exists = exists
        self._width = width
        self._height = height

    def winfo_exists(self):
        return 1 if self._exists else 0

    def update_idletasks(self):
        return None

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height


class CanvasForSyncSize:
    def __init__(self, widget):
        self._widget = widget

    def get_tk_widget(self):
        return self._widget


def test_sync_canvas_size_returns_true_and_resizes_figure_for_live_widget():
    shell = BaseAppShell()
    figure = FigureForSyncSize(dpi=100.0)
    canvas = CanvasForSyncSize(WidgetForSyncSize(width=400, height=250))

    resized = shell._sync_canvas_size(canvas, figure)

    assert resized is True
    assert figure.last_size == (4.0, 2.5, True)


def test_sync_canvas_size_returns_false_for_destroyed_widget():
    shell = BaseAppShell()
    figure = FigureForSyncSize(dpi=100.0)
    canvas = CanvasForSyncSize(WidgetForSyncSize(exists=False))

    resized = shell._sync_canvas_size(canvas, figure)

    assert resized is False
    assert figure.last_size is None


def test_render_embedded_figure_create_path_clears_and_initializes(monkeypatch):
    shell = BaseAppShell()
    shell._plot_figure = None
    shell._plot_canvas = None
    shell._plot_toolbar = None

    child_a = DummyWidget()
    child_b = DummyWidget()
    container = DummyContainer(children=[child_a, child_b])
    root_window = DummyRootWindow()
    figure = DummyFigure()

    bind_calls = []
    monkeypatch.setattr(shell, "_bind_canvas_resize", lambda c, canvas, root: bind_calls.append((c, canvas, root)))
    monkeypatch.setattr(shell, "_sync_canvas_size", lambda canvas, fig: None)
    monkeypatch.setattr(backend_tkagg, "FigureCanvasTkAgg", FakeFigureCanvas)
    monkeypatch.setattr(backend_tkagg, "NavigationToolbar2Tk", FakeToolbar)

    shell._render_embedded_figure(
        figure=figure,
        figure_attr="_plot_figure",
        canvas_attr="_plot_canvas",
        toolbar_attr="_plot_toolbar",
        container=container,
        root_window=root_window,
        draw_idle_on_reuse=True,
        clear_container_before_create=True,
    )

    assert child_a.destroyed is True
    assert child_b.destroyed is True
    assert shell._plot_figure is figure
    assert isinstance(shell._plot_canvas, FakeFigureCanvas)
    assert isinstance(shell._plot_toolbar, FakeToolbar)
    assert shell._plot_canvas.draw_calls >= 1
    assert len(root_window.after_idle_calls) == 2
    assert len(bind_calls) == 1


def test_render_embedded_figure_reuse_path_updates_canvas_for_same_figure(monkeypatch):
    shell = BaseAppShell()
    figure = DummyFigure()
    shared_container = DummyContainer()
    existing_canvas = FakeFigureCanvas(figure, master=shared_container)
    existing_toolbar = FakeToolbar(existing_canvas, container=shared_container)

    shell._plot_figure = figure
    shell._plot_canvas = existing_canvas
    shell._plot_toolbar = existing_toolbar

    closed = []
    monkeypatch.setattr(plt, "close", lambda fig: closed.append(fig))
    monkeypatch.setattr(shell, "_sync_canvas_size", lambda canvas, fig: None)

    shell._render_embedded_figure(
        figure=figure,
        figure_attr="_plot_figure",
        canvas_attr="_plot_canvas",
        toolbar_attr="_plot_toolbar",
        container=shared_container,
        root_window=DummyRootWindow(),
        draw_idle_on_reuse=True,
        clear_container_before_create=False,
    )

    assert closed == []
    assert shell._plot_figure is figure
    assert shell._plot_canvas is existing_canvas
    assert existing_canvas.figure is figure
    assert figure.canvas is existing_canvas
    assert existing_canvas.draw_idle_calls == 1
    assert existing_toolbar.update_calls == 1


def test_render_embedded_figure_recreates_canvas_and_toolbar_on_figure_swap(monkeypatch):
    shell = BaseAppShell()
    old_figure = DummyFigure()
    new_figure = DummyFigure()
    shared_container = DummyContainer()
    existing_canvas = FakeFigureCanvas(old_figure, master=shared_container)
    existing_toolbar = FakeToolbar(existing_canvas, container=shared_container)

    shell._plot_figure = old_figure
    shell._plot_canvas = existing_canvas
    shell._plot_toolbar = existing_toolbar

    closed = []
    bind_calls = []
    monkeypatch.setattr(plt, "close", lambda fig: closed.append(fig))
    monkeypatch.setattr(shell, "_bind_canvas_resize", lambda c, canvas, root: bind_calls.append((c, canvas, root)))
    monkeypatch.setattr(shell, "_sync_canvas_size", lambda canvas, fig: None)
    monkeypatch.setattr(backend_tkagg, "FigureCanvasTkAgg", FakeFigureCanvas)
    monkeypatch.setattr(backend_tkagg, "NavigationToolbar2Tk", FakeToolbar)

    shell._render_embedded_figure(
        figure=new_figure,
        figure_attr="_plot_figure",
        canvas_attr="_plot_canvas",
        toolbar_attr="_plot_toolbar",
        container=shared_container,
        root_window=DummyRootWindow(),
        draw_idle_on_reuse=True,
        clear_container_before_create=False,
    )

    assert closed == [old_figure]
    assert shell._plot_figure is new_figure
    assert shell._plot_canvas is not existing_canvas
    assert shell._plot_toolbar is not existing_toolbar
    assert isinstance(shell._plot_canvas, FakeFigureCanvas)
    assert isinstance(shell._plot_toolbar, FakeToolbar)
    assert len(bind_calls) == 1


def test_render_embedded_figure_recreates_stale_canvas_and_toolbar(monkeypatch):
    shell = BaseAppShell()
    old_figure = DummyFigure()
    new_figure = DummyFigure()
    stale_container = DummyContainer()
    target_container = DummyContainer()
    existing_canvas = FakeFigureCanvas(old_figure, master=stale_container)
    existing_canvas.widget._exists = False
    existing_toolbar = FakeToolbar(existing_canvas, container=stale_container)
    existing_toolbar._exists = False

    shell._plot_figure = old_figure
    shell._plot_canvas = existing_canvas
    shell._plot_toolbar = existing_toolbar

    closed = []
    bind_calls = []
    monkeypatch.setattr(plt, "close", lambda fig: closed.append(fig))
    monkeypatch.setattr(shell, "_bind_canvas_resize", lambda c, canvas, root: bind_calls.append((c, canvas, root)))
    monkeypatch.setattr(shell, "_sync_canvas_size", lambda canvas, fig: None)
    monkeypatch.setattr(backend_tkagg, "FigureCanvasTkAgg", FakeFigureCanvas)
    monkeypatch.setattr(backend_tkagg, "NavigationToolbar2Tk", FakeToolbar)

    shell._render_embedded_figure(
        figure=new_figure,
        figure_attr="_plot_figure",
        canvas_attr="_plot_canvas",
        toolbar_attr="_plot_toolbar",
        container=target_container,
        root_window=DummyRootWindow(),
        draw_idle_on_reuse=True,
        clear_container_before_create=False,
    )

    assert closed == [old_figure]
    assert shell._plot_figure is new_figure
    assert shell._plot_canvas is not existing_canvas
    assert shell._plot_toolbar is not existing_toolbar
    assert isinstance(shell._plot_canvas, FakeFigureCanvas)
    assert isinstance(shell._plot_toolbar, FakeToolbar)
    assert len(bind_calls) == 1
