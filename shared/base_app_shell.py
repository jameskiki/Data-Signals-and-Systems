"""Shared mixin for EvalData application shells.

Provides lightweight infrastructure that is common to both
``DataAnalysisApp`` and ``AnalysisWorkspace`` without imposing any
Tkinter inheritance (both windows use different root types).

Usage::

    from shared.base_app_shell import BaseAppShell

    class MyApp(BaseAppShell):
        def __init__(self):
            ...
            self.notifications = NotificationManager()
"""

from contextlib import contextmanager
from tkinter import messagebox


class BaseAppShell:
    """Mixin providing error-dialog handling and var-binding utilities."""

    @contextmanager
    def _error_dialog(self, title: str):
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
            messagebox.showerror(title, str(error))
            _failed.append(error)

    def _sync_canvas_size(self, canvas, figure) -> None:
        """Resize *figure* to fill the Tkinter widget that hosts *canvas*.

        Call this after a figure is first embedded (via ``after_idle``) and
        whenever the hosting container changes size, so the matplotlib figure
        always fills the available space instead of keeping its initial
        ``figsize`` in inches.
        """
        widget = canvas.get_tk_widget()
        widget.update_idletasks()
        width = max(widget.winfo_width(), 1)
        height = max(widget.winfo_height(), 1)
        dpi = float(figure.get_dpi() or 100.0)
        figure.set_size_inches(width / dpi, height / dpi, forward=True)

    def _bind_canvas_resize(self, container, canvas, root_window, debounce_ms: int = 150) -> None:
        """Bind a debounced ``<Configure>`` handler so the matplotlib figure
        always fills *container* when the user resizes the window.

        Uses *debounce_ms* to avoid redrawing on every pixel during a drag.
        The handler ignores events from child widgets so it only fires when
        the container itself changes size.
        """
        job_attr = f"_resize_job_{id(canvas)}"

        def _on_configure(event):
            if event.widget is not container:
                return
            job = getattr(self, job_attr, None)
            if job is not None:
                root_window.after_cancel(job)

            def _do_resize():
                self._sync_canvas_size(canvas, canvas.figure)
                canvas.draw_idle()

            setattr(self, job_attr, root_window.after(debounce_ms, _do_resize))

        container.bind("<Configure>", _on_configure, add="+")

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
