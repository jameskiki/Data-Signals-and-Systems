"""Shared presentation-shell helpers for Tk application facades."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import tkinter as tk
from tkinter import ttk

from Source.shared.base_app_shell import BaseAppShell


class PresentationShellMixin(BaseAppShell):
    """Mixin that centralizes reusable presentation-layer shell helpers."""

    @staticmethod
    def configure_modal_dialog(
        dialog: tk.Toplevel,
        *,
        parent: tk.Misc,
        title: str,
        geometry: str | None = None,
        resizable: tuple[bool, bool] = (False, False),
    ) -> None:
        """Apply standard modal-dialog behavior to a Tk toplevel."""

        dialog.title(title)
        dialog.transient(parent)
        dialog.grab_set()
        dialog.resizable(*resizable)
        if geometry is not None:
            dialog.geometry(geometry)

    @staticmethod
    def show_figure_in_window(root: tk.Misc, figure, window_title: str, window_geometry: str) -> None:
        """Show a matplotlib figure in a dedicated Tk window."""

        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import matplotlib.pyplot as plt

        window = tk.Toplevel(root)
        window.title(window_title)
        window.geometry(window_geometry)
        container = ttk.Frame(window)
        container.pack(fill=tk.BOTH, expand=True)
        canvas = FigureCanvasTkAgg(figure, master=container)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, container)
        toolbar.update()
        toolbar.pack(side=tk.TOP, fill=tk.X)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)

        resize_job: str | None = None

        def _sync_canvas_size() -> None:
            widget = canvas.get_tk_widget()
            widget.update_idletasks()
            width = max(widget.winfo_width(), 1)
            height = max(widget.winfo_height(), 1)
            dpi = float(figure.get_dpi() or 100.0)
            figure.set_size_inches(width / dpi, height / dpi, forward=True)
            canvas.draw_idle()

        def _on_configure(event: tk.Event) -> None:
            nonlocal resize_job
            if event.widget is not container:
                return
            if resize_job is not None:
                window.after_cancel(resize_job)
            resize_job = window.after(150, _sync_canvas_size)

        container.bind("<Configure>", _on_configure)
        window.after_idle(_sync_canvas_size)

        def _on_close() -> None:
            plt.close(figure)
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", _on_close)

    @staticmethod
    def populate_listbox(listbox: tk.Listbox, items: Sequence[str]) -> None:
        """Replace the contents of a listbox with the given items."""

        listbox.delete(0, tk.END)
        for item in items:
            listbox.insert(tk.END, item)

    @staticmethod
    def get_selected_listbox_items(listbox: tk.Listbox, items: Sequence[str]) -> list[str]:
        """Return the selected items from a listbox using the provided item order."""

        return [items[index] for index in listbox.curselection()]

    @staticmethod
    def get_selected_treeview_indices(tree: ttk.Treeview | None, item_to_index: dict[str, int]) -> list[int]:
        """Return sorted unique indices mapped from the current treeview selection."""

        if tree is None:
            return []
        selected_items = tree.selection()
        if not selected_items:
            return []
        selected_indices = [item_to_index[item_id] for item_id in selected_items if item_id in item_to_index]
        return sorted(set(selected_indices))

    @staticmethod
    def select_all_treeview_items(tree: ttk.Treeview | None) -> None:
        """Select every item currently present in a treeview."""

        if tree is None:
            return
        tree.selection_set(tree.get_children())

    @staticmethod
    def clear_treeview_selection(tree: ttk.Treeview | None) -> None:
        """Clear the current treeview selection."""

        if tree is None:
            return
        tree.selection_remove(tree.selection())

    @staticmethod
    def get_selected_selector_items(selector_vars: dict[str, tk.BooleanVar]) -> list[str]:
        """Return the names of checked selector items in display order."""

        return [item_name for item_name, variable in selector_vars.items() if variable.get()]

    @staticmethod
    def set_selector_items_state(selector_vars: dict[str, tk.BooleanVar], value: bool) -> None:
        """Set every selector variable to the same boolean value."""

        for variable in selector_vars.values():
            variable.set(value)

    @staticmethod
    def format_selector_summary(
        selected_items: Sequence[str],
        *,
        visible_count: int,
        hidden_count: int,
        empty_text: str,
        choose_text: str,
    ) -> str:
        """Format a compact summary for a multi-select UI selector."""

        limit_suffix = ""
        if hidden_count:
            total_count = visible_count + hidden_count
            limit_suffix = f" (showing {visible_count} of {total_count})"

        if visible_count == 0:
            return empty_text
        if not selected_items:
            return f"{choose_text}{limit_suffix}"
        if len(selected_items) <= 2:
            return f"{', '.join(selected_items)}{limit_suffix}"

        shown_items = ", ".join(selected_items[:2])
        return f"{len(selected_items)} selected: {shown_items}, +{len(selected_items) - 2}{limit_suffix}"

    def _build_checkbutton_selector_menu(
        self,
        *,
        menu: tk.Menu | None,
        button: ttk.Menubutton | None,
        items: Sequence[str],
        selected_items: Sequence[str] | set[str],
        max_items: int,
        get_colors: Callable[[str], tuple[str, str]],
        on_changed: Callable[..., None],
        on_select_all: Callable[[], None],
        on_clear_selection: Callable[[], None],
        select_all_label: str = "Select all",
        clear_label: str = "Clear selection",
        hidden_label: str = "channels",
    ) -> tuple[dict[str, tk.BooleanVar], int]:
        """Populate a checkbutton-backed selector menu and return its variables."""

        if menu is None or button is None:
            return {}, 0

        visible_items = list(items[:max_items])
        hidden_count = max(0, len(items) - len(visible_items))
        selector_vars: dict[str, tk.BooleanVar] = {}

        menu.delete(0, tk.END)
        if not visible_items:
            button.state(["disabled"])
            return selector_vars, hidden_count

        menu.add_command(label=select_all_label, command=on_select_all)
        menu.add_command(label=clear_label, command=on_clear_selection)
        if hidden_count:
            menu.add_separator()
            menu.add_command(
                label=f"Showing first {len(visible_items)} of {len(items)} {hidden_label}",
                state=tk.DISABLED,
            )
        menu.add_separator()

        selected_set = set(selected_items)
        for item_name in visible_items:
            variable = tk.BooleanVar(value=item_name in selected_set)
            variable.trace_add("write", on_changed)
            selector_vars[item_name] = variable
            background, foreground = get_colors(item_name)
            menu.add_checkbutton(
                label=item_name,
                variable=variable,
                onvalue=True,
                offvalue=False,
                background=background,
                foreground=foreground,
                activebackground=background,
                activeforeground=foreground,
                selectcolor=background,
            )

        button.state(["!disabled"])
        return selector_vars, hidden_count