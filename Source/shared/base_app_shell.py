"""Shared mixin for EvalData application shells.

Provides lightweight infrastructure that is common to both
``DataPreparationApp`` and ``AnalysisWorkspace`` without imposing any
Tkinter inheritance (both windows use different root types).

Usage::

    from Source.shared.base_app_shell import BaseAppShell

    class MyApp(BaseAppShell):
        def __init__(self):
            ...
            self.notifications = NotificationManager()
"""

from contextlib import contextmanager
from tkinter import TclError, messagebox

from Source.shared.plot_options import PlotDescriptor


class BaseAppShell:
    """Mixin providing error-dialog handling and var-binding utilities."""

    def _ensure_notifications(self):
        """Ensure a NotificationManager instance exists on the shell."""
        if hasattr(self, "notifications") and self.notifications is not None:
            return self.notifications
        from Source.shared.notifications import NotificationManager

        self.notifications = NotificationManager()
        return self.notifications

    def notify_info(self, message: str, details: str | None = None) -> None:
        """Post an informational notification."""
        self._ensure_notifications().info(message, details)

    def notify_success(self, message: str, details: str | None = None) -> None:
        """Post a success notification."""
        self._ensure_notifications().success(message, details)

    def notify_warning(self, message: str, details: str | None = None) -> None:
        """Post a warning notification."""
        self._ensure_notifications().warning(message, details)

    def notify_error(self, message: str, details: str | None = None) -> None:
        """Post an error notification."""
        self._ensure_notifications().error(message, details)

    @contextmanager
    def _error_dialog(self, title: str, *, modal_fallback: bool = True):
        """Context manager that shows a modal error dialog if an exception is raised.

        Usage::

            with self._error_dialog("Operation Error") as _failed:
                result = do_something()
            if _failed:
                return
        """
        _failed: list[Exception] = []
        try:
            yield _failed
        except Exception as error:
            self.notify_error(title, str(error))
            if modal_fallback:
                messagebox.showerror(title, str(error))
            _failed.append(error)

    def _sync_canvas_size(self, canvas, figure) -> bool:
        """Resize *figure* to fill the Tkinter widget that hosts *canvas*.

        Call this after a figure is first embedded (via ``after_idle``) and
        whenever the hosting container changes size, so the matplotlib figure
        always fills the available space instead of keeping its initial
        ``figsize`` in inches.
        """
        try:
            widget = canvas.get_tk_widget()
            if not bool(widget.winfo_exists()):
                return False
            widget.update_idletasks()
            width = max(widget.winfo_width(), 1)
            height = max(widget.winfo_height(), 1)
        except (AttributeError, TclError):
            return False

        dpi = float(figure.get_dpi() or 100.0)
        figure.set_size_inches(width / dpi, height / dpi, forward=True)
        return True

    def _bind_canvas_resize(self, container, canvas, root_window, debounce_ms: int = 150) -> None:
        """Bind a debounced ``<Configure>`` handler so the matplotlib figure
        always fills *container* when the user resizes the window.

        Uses *debounce_ms* to avoid redrawing on every pixel during a drag.
        The handler ignores events from child widgets so it only fires when
        the container itself changes size.
        """
        binding_attr = f"_resize_bindings_{id(container)}"
        previous_bindings = getattr(self, binding_attr, None)
        if previous_bindings is not None:
            configure_binding, destroy_binding, previous_job_attr = previous_bindings
            previous_job = getattr(self, previous_job_attr, None)
            if previous_job is not None:
                try:
                    root_window.after_cancel(previous_job)
                except TclError:
                    pass
            for event_name, binding_id in (("<Configure>", configure_binding), ("<Destroy>", destroy_binding)):
                if binding_id is not None:
                    try:
                        container.unbind(event_name, binding_id)
                    except TclError:
                        pass

        job_attr = f"_resize_job_{id(canvas)}"

        def _on_configure(event):
            if event.widget is not container:
                return
            job = getattr(self, job_attr, None)
            if job is not None:
                try:
                    root_window.after_cancel(job)
                except TclError:
                    pass

            def _do_resize():
                setattr(self, job_attr, None)
                if not self._sync_canvas_size(canvas, canvas.figure):
                    return
                try:
                    canvas.draw_idle()
                except TclError:
                    return

            try:
                setattr(self, job_attr, root_window.after(debounce_ms, _do_resize))
            except TclError:
                setattr(self, job_attr, None)

        def _on_destroy(event):
            if event.widget is not container:
                return
            job = getattr(self, job_attr, None)
            if job is not None:
                try:
                    root_window.after_cancel(job)
                except TclError:
                    pass
            setattr(self, job_attr, None)
            setattr(self, binding_attr, None)

        configure_binding = container.bind("<Configure>", _on_configure, add="+")
        destroy_binding = container.bind("<Destroy>", _on_destroy, add="+")
        setattr(self, binding_attr, (configure_binding, destroy_binding, job_attr))

    def _bind_write(self, handler, *vars) -> None:
        """Register *handler* as the ``trace_add("write", ...)`` callback for each var.

        Replaces repetitive blocks such as::

            self.var_a.trace_add("write", self._on_changed)
            self.var_b.trace_add("write", self._on_changed)
            self.var_c.trace_add("write", self._on_changed)

        with::

            self._bind_write(self._on_changed, self.var_a, self.var_b, self.var_c)
        """
        for var in vars:
            var.trace_add("write", handler)

    def _schedule_debounced(self, root_window, job_attr: str, callback, delay_ms: int = 300) -> None:
        """Run *callback* after a quiet period, replacing any pending job."""

        pending_job = getattr(self, job_attr, None)
        if pending_job is not None:
            try:
                root_window.after_cancel(pending_job)
            except TclError:
                pass

        def _run() -> None:
            setattr(self, job_attr, None)
            callback()

        try:
            setattr(self, job_attr, root_window.after(delay_ms, _run))
        except TclError:
            setattr(self, job_attr, None)

    def _cancel_scheduled(self, root_window, *job_attrs: str) -> None:
        """Cancel pending jobs stored on this shell."""

        for job_attr in job_attrs:
            pending_job = getattr(self, job_attr, None)
            if pending_job is None:
                continue
            try:
                root_window.after_cancel(pending_job)
            except TclError:
                pass
            setattr(self, job_attr, None)

    def _render_embedded_figure(
        self,
        *,
        figure,
        figure_attr: str,
        canvas_attr: str,
        toolbar_attr: str,
        container,
        root_window,
        draw_idle_on_reuse: bool,
        clear_container_before_create: bool = False,
        plot_type: PlotDescriptor | None = None,
    ) -> None:
        """Render a matplotlib figure in a Tk container with shared lifecycle behavior.

        Reuses an existing canvas/toolbar when present, otherwise creates and binds
        resize handling once during first initialization.
        """

        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import matplotlib.pyplot as plt
        from tkinter import ttk

        def _update_plot_type_indicator() -> None:
            if plot_type is None:
                return
            indicator_text = f"Plot type: {plot_type}"
            for child in container.winfo_children():
                if getattr(child, "_evaldata_plot_type_indicator", False):
                    child.configure(text=indicator_text)
                    return
            indicator = ttk.Label(container, text=indicator_text, anchor="w", padding=(8, 4))
            indicator._evaldata_plot_type_indicator = True
            indicator.pack(side="top", fill="x")

        existing_figure = getattr(self, figure_attr)
        existing_canvas = getattr(self, canvas_attr)
        existing_toolbar = getattr(self, toolbar_attr)

        def _is_widget_alive(widget, expected_master) -> bool:
            if widget is None:
                return False
            if not hasattr(widget, "winfo_exists"):
                return False
            try:
                if not bool(widget.winfo_exists()):
                    return False
            except Exception:
                return False
            return getattr(widget, "master", None) is expected_master

        if existing_canvas is not None:
            canvas_widget = existing_canvas.get_tk_widget()
            canvas_is_alive = _is_widget_alive(canvas_widget, container)
            toolbar_is_alive = existing_toolbar is None or _is_widget_alive(existing_toolbar, container)
            can_reuse_canvas = canvas_is_alive and toolbar_is_alive and existing_figure is figure

            if can_reuse_canvas:
                _update_plot_type_indicator()
                setattr(self, figure_attr, figure)
                existing_canvas.figure = figure
                figure.canvas = existing_canvas
                self._sync_canvas_size(existing_canvas, figure)
                if draw_idle_on_reuse:
                    existing_canvas.draw_idle()
                else:
                    existing_canvas.draw()
                if existing_toolbar is not None:
                    existing_toolbar.canvas = existing_canvas
                    existing_toolbar.update()
                return

            # Recreate stale widgets, or recreate on figure swap to avoid Tk/matplotlib
            # callback drift after replacing a figure object under an existing toolbar.
            if existing_toolbar is not None and hasattr(existing_toolbar, "destroy"):
                try:
                    existing_toolbar.destroy()
                except Exception:
                    pass
            try:
                if _is_widget_alive(canvas_widget, container):
                    canvas_widget.destroy()
            except Exception:
                pass
            existing_canvas = None
            existing_toolbar = None
            setattr(self, canvas_attr, None)
            setattr(self, toolbar_attr, None)

        if existing_figure is not None and existing_figure is not figure:
            plt.close(existing_figure)

        setattr(self, figure_attr, figure)

        if clear_container_before_create:
            for widget in container.winfo_children():
                widget.destroy()

        _update_plot_type_indicator()

        canvas = FigureCanvasTkAgg(figure, master=container)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, container)
        toolbar.update()
        toolbar.pack(side="top", fill="x")
        canvas.get_tk_widget().pack(fill="both", expand=True, side="bottom")

        setattr(self, canvas_attr, canvas)
        setattr(self, toolbar_attr, toolbar)

        _canvas, _figure = canvas, figure
        root_window.after_idle(lambda: self._sync_canvas_size(_canvas, _figure))
        root_window.after_idle(_canvas.draw)
        self._bind_canvas_resize(container, canvas, root_window)
