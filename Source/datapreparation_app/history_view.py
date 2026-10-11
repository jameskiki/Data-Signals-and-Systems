"""Pipeline graph, decision notes and per-publish report content selection."""

import json
import os
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from .history_deletion import plan_history_deletion, delete_history_nodes
from .report import build_publish_report
from .datasets import dataset_display_name, refresh_dataset_table

from Source.shared.operation_history import REPORT_VIEW_OPERATION, OperationHistory, based_on_text, before_append_step
from Source.data_ops.models import SIGNAL_FILTER_OPERATIONS


NODE_HEIGHT = 132
COMPACT_NODE_HEIGHT = 66
NODE_WIDTH = 280

HISTORY_COLORS = {
    "input": ("Inputs / combined data", "#eaf3fa", "#537f9b"),
    "processing": ("Processing", "#faf2e2", "#947743"),
    "snapshot": ("Snapshot results", "#f5edf4", "#956e8b"),
    "published": ("Published dataset", "#eaf5f1", "#568575"),
    "metadata": ("Metadata", "#f0f2f5", "#768293"),
    "untracked": ("Untracked", "#ffffff", "#111827"),
}


def history_category(step, history: OperationHistory) -> str:
    if not step.tracked:
        return "untracked"
    if step.id in history.artifact_tables or step.operation == REPORT_VIEW_OPERATION:
        return "snapshot"
    if step.operation in {"load_file", "load_demo", "append_raw", "merge"}:
        return "input"
    if step.operation == "publish":
        return "published"
    if (
        step.operation in SIGNAL_FILTER_OPERATIONS
        or step.operation.startswith("derived_")
        or step.operation in {"prepare", "split", "simple_filter", "resample", "reset", "apply_kept_cycles"}
    ):
        return "processing"
    return "metadata"


def publish_linked_steps(step) -> tuple[str, ...]:
    if step.operation != "publish":
        return ()
    linked = json.loads(step.parameters_json).get("workspace_steps", [])
    return tuple(item for item in linked if isinstance(item, str)) if isinstance(linked, list) else ()


class HistoryWindow:
    def __init__(self, parent: tk.Misc, history: OperationHistory, app=None) -> None:
        self.history = history
        self.app = app
        self._deletion_preview = None
        self._report_publish_id = None
        self._expanded_nodes: set[str] = set()
        self.window = tk.Toplevel(parent)
        self.window.title("Workflow / Pipeline & Reports (Prototype)")
        self.window.geometry("1400x850")
        ttk.Label(
            self.window,
            text="Pipeline of how each dataset is produced, with snapshot results and decision notes as evidence. "
                 "Appends are inserted upstream of existing operations. Save/reopen with Files -> Save Embedded "
                 "Project / Open Project. No undo. Comparison/display settings are not recorded. Refresh after operations.",
            wraplength=950,
        ).pack(fill=tk.X, padx=10, pady=10)
        toolbar = ttk.Frame(self.window)
        toolbar.pack(fill=tk.X, padx=10)
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Compact All", command=lambda: self._set_all_expanded(False)).pack(side=tk.LEFT, padx=6)
        ttk.Button(toolbar, text="Expand All", command=lambda: self._set_all_expanded(True)).pack(side=tk.LEFT)
        if app is not None:
            ttk.Button(toolbar, text="Preview Node Deletion...", command=self._preview_deletion).pack(side=tk.LEFT, padx=6)
        self.delete_button = ttk.Button(
            toolbar, text="Confirm Highlighted Deletion...", command=self._confirm_deletion, state="disabled",
        )
        if app is not None:
            self.delete_button.pack(side=tk.LEFT)
        report_controls = ttk.Frame(self.window)
        report_controls.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(report_controls, text="Report for publish:").pack(side=tk.LEFT)
        self.report_target_var = tk.StringVar()
        self.report_target = ttk.Combobox(
            report_controls, textvariable=self.report_target_var, state="readonly", width=55,
        )
        self.report_target.pack(side=tk.LEFT, padx=6)
        self.report_target.bind("<<ComboboxSelected>>", self._change_report_target)
        self.report_status = ttk.Label(report_controls)
        self.report_status.pack(side=tk.LEFT, padx=6)
        legend = ttk.Frame(self.window)
        legend.pack(fill=tk.X, padx=10, pady=(6, 0))
        for label, fill, outline in HISTORY_COLORS.values():
            tk.Label(legend, text=label, background=fill, foreground=outline, padx=8, pady=3).pack(
                side=tk.LEFT, padx=(0, 6),
            )
        tk.Label(
            self.window, text="Solid arrows: data flow   Dotted arrows: content in selected report   "
            "In report / Excluded / Pipeline only: report status   Dashed card: earlier data   ✎: note   "
            "Double-click a card to expand/compact",
            foreground=HISTORY_COLORS["published"][2], padx=8,
        ).pack(anchor="w", padx=10, pady=4)
        panes = ttk.Panedwindow(self.window, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=4)
        self.steps = ttk.Treeview(left, show="tree", height=12)
        self.steps.pack(fill=tk.BOTH, expand=True)
        for category, (_, fill, _) in HISTORY_COLORS.items():
            self.steps.tag_configure(category, background=fill, foreground="#111827")
        self.steps.bind("<<TreeviewSelect>>", self._show_details)
        self.details = tk.Text(left, height=14, wrap="word", state="disabled")
        self.details.pack(fill=tk.BOTH, expand=True)
        self.include_var = tk.BooleanVar()
        self.include_button = ttk.Checkbutton(
            left, text="Include selected node in this report",
            variable=self.include_var, command=self._toggle_report_node, state="disabled",
        )
        self.include_button.pack(fill=tk.X, pady=5)
        ttk.Label(
            left, text="Only report content changes. Calculations and published data stay unchanged.",
            wraplength=330,
        ).pack(fill=tk.X)
        self.result_button = ttk.Button(left, text="Inspect Saved Result Tables", command=self._show_result_tables, state="disabled")
        self.result_button.pack(fill=tk.X)
        self.note_button = ttk.Button(left, text="Edit Decision Note...", command=self._edit_note, state="disabled")
        self.note_button.pack(fill=tk.X)
        self.report_button = ttk.Button(
            left, text="Generate Selected Report...", command=self._generate_report, state="disabled",
        )
        if app is not None:
            self.report_button.pack(fill=tk.X)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(right, background="#f7f9fc", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.refresh()
        self.window.after_idle(lambda: panes.sashpos(0, 360) if panes.winfo_exists() else None)

    def refresh(self) -> None:
        self._deletion_preview = None
        self.delete_button.configure(state="disabled")
        selection = self.steps.selection()
        self.steps.delete(*self.steps.get_children())
        self.canvas.delete("all")
        publishes = [step for step in self.history.steps if step.operation == "publish"]
        self._report_targets = {
            f"#{self.history.steps.index(step) + 1}: {self._node_name(step)}": step.id for step in publishes
        }
        if self._report_publish_id not in self._report_targets.values():
            self._report_publish_id = publishes[-1].id if publishes else None
        self.report_target.configure(values=list(self._report_targets))
        self.report_target_var.set(next(
            (name for name, step_id in self._report_targets.items() if step_id == self._report_publish_id), "",
        ))
        self._report_candidates = {
            step.id for step in self.history.report_candidates(self._report_publish_id)
        } if self._report_publish_id else set()
        self._report_enabled = {
            step_id for step_id in self._report_candidates
            if self.history.report_node_enabled(self._report_publish_id, step_id)
        }
        self.report_status.configure(text=f"{len(self._report_enabled)} content nodes included")
        self._node_rectangles: dict[str, tuple[int, str]] = {}
        positions: dict[str, tuple[int, int, int]] = {}
        depths: dict[str, int] = {}
        step_positions: dict[str, tuple[int, int, int]] = {}
        step_depths: dict[str, int] = {}
        y = 25
        for index, step in enumerate(self.history.steps):
            text = f"{index + 1}. {step.operation}" + ("" if step.tracked else " [UNTRACKED]")
            stale = self._before_append_text(step)
            note = self.history.notes.get(step.id, "")
            category = history_category(step, self.history)
            _, fill, outline = HISTORY_COLORS[category]
            self.steps.insert(
                "", tk.END, iid=step.id, tags=(category,),
                text=text + (" [earlier data]" if stale else "") + (" ✎" if note else "")
                + f" [{self._report_node_status(step.id)}]",
            )
            linked = [step_id for step_id in publish_linked_steps(step) if step_id in step_positions]
            depth = max(
                [depths[parent] + 1 for parent in step.input_revisions]
                + [step_depths[step_id] + 1 for step_id in linked],
                default=0,
            )
            x = 30 + depth * 330
            expanded = step.id in self._expanded_nodes
            height = NODE_HEIGHT if expanded else COMPACT_NODE_HEIGHT
            for parent in step.input_revisions:
                px, py, parent_height = positions[parent]
                self.canvas.create_line(
                    px + NODE_WIDTH // 2, py + parent_height,
                    px + NODE_WIDTH // 2, py + parent_height + 16,
                    x + NODE_WIDTH // 2, y - 16, x + NODE_WIDTH // 2, y,
                    arrow=tk.LAST, fill="#a9b6c5", width=1.2, smooth=True,
                )
            tag = f"step-{step.id}"
            r = 12
            rectangle = self.canvas.create_polygon(
                x + r, y, x + NODE_WIDTH - r, y, x + NODE_WIDTH, y,
                x + NODE_WIDTH, y + r, x + NODE_WIDTH, y + height - r,
                x + NODE_WIDTH, y + height, x + NODE_WIDTH - r, y + height,
                x + r, y + height, x, y + height, x, y + height - r,
                x, y + r, x, y,
                fill=fill, outline=outline, width=1, smooth=True,
                dash=(4, 2) if category == "untracked" or stale else (), tags=tag,
            )
            self._node_rectangles[step.id] = rectangle, outline
            self.canvas.create_text(
                x + 14, y + 10, anchor="nw",
                text=f"{text}{' ✎' if note else ''}", font=("TkDefaultFont", 9, "bold"),
                width=NODE_WIDTH - 28, fill="#334155", tags=tag,
            )
            if expanded:
                name = self._node_name(step)
                self.canvas.create_text(
                    x + 14, y + 44, anchor="nw", text=name if len(name) <= 42 else name[:39] + "...",
                    width=NODE_WIDTH - 28, font=("TkDefaultFont", 9), fill="#475569", tags=tag,
                )
                self.canvas.create_text(
                    x + 14, y + 80, anchor="nw",
                    text=HISTORY_COLORS[category][0] + (" | Earlier data" if stale else ""),
                    width=NODE_WIDTH - 28, font=("TkDefaultFont", 8), fill="#64748b", tags=tag,
                )
            self.canvas.create_text(
                x + 14, y + (103 if expanded else 44), anchor="nw",
                text=self._report_node_status(step.id), width=NODE_WIDTH - 28,
                font=("TkDefaultFont", 9, "bold"),
                fill="#376b89" if step.id in self._report_enabled else "#64748b", tags=tag,
            )
            self.canvas.tag_bind(tag, "<Button-1>", lambda event, step_id=step.id: self._select(step_id))
            self.canvas.tag_bind(
                tag, "<Double-Button-1>", lambda event, step_id=step.id: self._toggle_expanded(step_id),
            )
            if note:
                self.canvas.tag_bind(tag, "<Enter>", lambda event, step_id=step.id: self._show_tooltip(step_id))
                self.canvas.tag_bind(tag, "<Leave>", lambda event: self.canvas.delete("tooltip"))
            positions.setdefault(step.output_revision, (x, y, height))
            depths.setdefault(step.output_revision, depth)
            step_positions[step.id] = (x, y, height)
            step_depths[step.id] = depth
            y += height + 33
        if self._report_publish_id:
            x, y, target_height = step_positions[self._report_publish_id]
            for step_id in self._report_enabled:
                px, py, height = step_positions[step_id]
                edge = self.canvas.create_line(
                    px + NODE_WIDTH, py + height // 2,
                    px + NODE_WIDTH + 25, py + height // 2,
                    x - 25, y + target_height // 2, x, y + target_height // 2,
                    arrow=tk.LAST, fill="#91b1c5", width=1, dash=(2, 5), smooth=True,
                )
                self.canvas.tag_lower(edge)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if selection and self.steps.exists(selection[0]):
            self._select(selection[0])
        elif self.history.steps:
            self._select(self.history.steps[-1].id)
        else:
            self.result_button.configure(state="disabled")
            self.report_button.configure(state="disabled")
            self.note_button.configure(state="disabled")
            self.include_button.configure(state="disabled")
            self._set_details("No operations recorded. Load a demo or file to begin.")

    def _toggle_expanded(self, step_id: str) -> None:
        if step_id in self._expanded_nodes:
            self._expanded_nodes.remove(step_id)
        else:
            self._expanded_nodes.add(step_id)
        self.steps.selection_set(step_id)
        self.refresh()

    def _set_all_expanded(self, expanded: bool) -> None:
        self._expanded_nodes = {step.id for step in self.history.steps} if expanded else set()
        self.refresh()

    def _report_node_status(self, step_id: str) -> str:
        if step_id == self._report_publish_id:
            return "Report target | Data included"
        if step_id in self._report_enabled:
            return "In report"
        overrides = self.history.report_selection.get(self._report_publish_id, {})
        if overrides.get(step_id) is False:
            return "Excluded"
        return "Pipeline only"

    def _change_report_target(self, _event=None) -> None:
        self._report_publish_id = self._report_targets[self.report_target_var.get()]
        self.refresh()

    def _toggle_report_node(self) -> None:
        selection = self.steps.selection()
        if not selection or self._report_publish_id is None:
            return
        try:
            self.history.set_report_node_enabled(self._report_publish_id, selection[0], self.include_var.get())
        except ValueError as error:
            messagebox.showerror("Report Selection", str(error), parent=self.window)
            return
        self.refresh()

    def _node_name(self, step) -> str:
        context = getattr(self.app, "dataset_contexts", {}).get(step.label) if self.app is not None else None
        return dataset_display_name(step.label, context)

    def _before_append_text(self, step) -> str:
        append_id = before_append_step(step)
        if append_id is None:
            return ""
        number = next((index + 1 for index, item in enumerate(self.history.steps) if item.id == append_id), None)
        return f"{based_on_text(step)}, before append #{number}" if number else f"{based_on_text(step)}, before an append"

    def _show_tooltip(self, step_id: str) -> None:
        self.canvas.delete("tooltip")
        x1, y1, x2, _ = self.canvas.bbox(f"step-{step_id}")
        text = self.canvas.create_text(
            x2 + 12, y1 + 4, text="Decision note:\n" + self.history.notes.get(step_id, ""),
            anchor="nw", width=320, fill="#111827", tags="tooltip",
        )
        left, top, right, bottom = self.canvas.bbox(text)
        box = self.canvas.create_rectangle(
            left - 6, top - 4, right + 6, bottom + 4, fill="#fffbe6", outline="#8a5700", tags="tooltip",
        )
        self.canvas.tag_lower(box, text)
        self.canvas.tag_raise("tooltip")

    def _edit_note(self) -> None:
        selection = self.steps.selection()
        if not selection:
            return
        step_id = selection[0]
        dialog = tk.Toplevel(self.window)
        dialog.title("Decision Note")
        dialog.transient(self.window)
        ttk.Label(
            dialog, wraplength=480,
            text="Why this step or result matters (e.g. 'FFT shows a 12 h sine -> added moving average'). "
                 "Shown in the graph, details and reports. Leave empty to remove.",
        ).pack(fill=tk.X, padx=10, pady=(10, 4))
        editor = tk.Text(dialog, width=64, height=8, wrap="word")
        editor.pack(fill=tk.BOTH, expand=True, padx=10)
        editor.insert("1.0", self.history.notes.get(step_id, ""))
        editor.focus_set()

        def save() -> None:
            try:
                self.history.set_note(step_id, editor.get("1.0", tk.END))
            except ValueError as error:
                messagebox.showerror("Decision Note", str(error), parent=dialog)
                return
            dialog.destroy()
            self.refresh()
            self._select(step_id)

        buttons = ttk.Frame(dialog)
        buttons.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(buttons, text="Save", command=save).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=6)

    def _generate_report(self) -> None:
        if self._report_publish_id is None or self.app is None:
            return
        step = next(step for step in self.history.steps if step.id == self._report_publish_id)
        try:
            content = build_publish_report(self.app, step.id)
        except ValueError as error:
            messagebox.showerror("Report", str(error), parent=self.window)
            return
        name = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in os.path.splitext(self._node_name(step))[0]
        )
        path = filedialog.asksaveasfilename(
            parent=self.window, title="Save HTML report", defaultextension=".html",
            initialfile=f"{name}_report.html", filetypes=[("HTML report", "*.html")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except OSError as error:
            messagebox.showerror("Report", f"Could not write report:\n{error}", parent=self.window)
            return
        webbrowser.open(Path(path).resolve().as_uri())

    def _select(self, step_id: str) -> None:
        self.steps.selection_set(step_id)
        self.steps.see(step_id)
        self._show_details()

    def _set_details(self, text: str) -> None:
        self.details.configure(state="normal")
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def _show_details(self, _event=None) -> None:
        selection = self.steps.selection()
        if not selection:
            return
        self._deletion_preview = None
        self.delete_button.configure(state="disabled")
        step = next(step for step in self.history.steps if step.id == selection[0])
        for step_id, (rectangle, outline) in self._node_rectangles.items():
            self.canvas.itemconfigure(
                rectangle, outline="#111827" if step_id == step.id else outline,
                width=2 if step_id == step.id else 1,
            )
        self.result_button.configure(state="normal" if self.history.artifact_tables.get(step.id) else "disabled")
        self.report_button.configure(state="normal" if self._report_publish_id else "disabled")
        self.include_button.configure(state="normal" if step.id in self._report_candidates else "disabled")
        self.include_var.set(step.id in self._report_enabled)
        numbers = {item.id: index + 1 for index, item in enumerate(self.history.steps)}
        linked = publish_linked_steps(step)
        included = ""
        if linked:
            lines = [
                f"  {numbers[item.id]}. {item.operation}" for item in self.history.steps if item.id in linked
            ]
            missing = sum(step_id not in numbers for step_id in linked)
            if missing:
                lines.append(f"  ({missing} linked step(s) were deleted)")
            included = "Original publish links (report choices are separate):\n" + "\n".join(lines) + "\n\n"
        if step.id == self._report_publish_id:
            included += "Content enabled for this report:\n" + "\n".join(
                f"  {numbers[item.id]}. {item.operation}"
                for item in self.history.steps if item.id in self._report_enabled
            ) + "\n\nPublished data summary: always included.\n\n"
        stale = self._before_append_text(step)
        stale_text = (
            f"Evidence {stale}: it does not include rows appended later.\n\n" if stale else ""
        )
        note = self.history.notes.get(step.id)
        note_text = f"Decision note:\n{note}\n\n" if note else ""
        self.note_button.configure(state="normal")
        self._set_details(
            f"Selected report: {self.report_target_var.get() or '(none)'}\n"
            f"Content status: {self._report_node_status(step.id)}\n\n"
            f"{note_text}{stale_text}{step.operation}\n{step.label}\n"
            f"Category: {HISTORY_COLORS[history_category(step, self.history)][0]}\n\nUTC: {step.timestamp}\n"
            f"Tracked: {step.tracked}\nInputs: {', '.join(step.input_revisions) or '-'}\n"
            f"Output: {step.output_revision}\n\n{included}Parameters:\n{step.parameters_json}"
        )

    def _preview_deletion(self) -> None:
        selection = self.steps.selection()
        if not selection:
            return
        try:
            plan = plan_history_deletion(self.app, selection[0])
        except ValueError as error:
            messagebox.showerror("Deletion Preview", str(error), parent=self.window)
            return
        self._deletion_preview = selection[0], plan
        for step_id in plan.step_ids:
            rectangle, _ = self._node_rectangles[step_id]
            self.canvas.itemconfigure(rectangle, outline="#111827", width=4, dash=(6, 3))
        names = "\n".join(
            f"- {step.operation}: {os.path.basename(step.label)}"
            for step in self.history.steps if step.id in plan.step_ids
        )
        self._set_details(
            f"DELETION PREVIEW: {len(plan.step_ids)} nodes, {len(plan.dataset_paths)} datasets, "
            f"{plan.result_count} result snapshots.\n\n{names}\n\nDatasets:\n"
            + ("\n".join(plan.dataset_paths) or "(none)")
            + "\n\nHighlighted nodes will be removed. Source files and existing saved project files "
            "are unchanged. All analysis/comparison windows will close. No undo."
        )
        self.delete_button.configure(state="normal")

    def _confirm_deletion(self) -> None:
        if self._deletion_preview is None:
            return
        step_id, plan = self._deletion_preview
        if not messagebox.askyesno(
            "Delete Highlighted Nodes",
            f"Remove {len(plan.step_ids)} nodes, {len(plan.dataset_paths)} datasets and "
            f"{plan.result_count} result snapshots?\n\nAll analysis/comparison windows will close, "
            "discarding unpublished edits. Source files and saved projects are not deleted. No undo.",
            parent=self.window,
        ):
            self._show_details()
            return
        try:
            delete_history_nodes(self.app, step_id, plan)
        except Exception as error:
            messagebox.showerror("Deletion Error", str(error), parent=self.window)
            return
        refresh_dataset_table(self.app)
        self.app._refresh_dataset_preparation_views()
        self.refresh()
        self.app.notifications.success("Selected history nodes and dependents deleted from the current session")

    def _show_result_tables(self) -> None:
        selection = self.steps.selection()
        if not selection or not self.history.artifact_tables.get(selection[0]):
            return
        window = tk.Toplevel(self.window)
        window.title("Saved Result Tables (Preview)")
        window.geometry("850x500")
        notebook = ttk.Notebook(window)
        notebook.pack(fill=tk.BOTH, expand=True)
        for name, frame in self.history.artifact_tables[selection[0]].items():
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=name)
            ttk.Label(tab, text=f"{len(frame)} rows x {len(frame.columns)} columns; preview limited to 200 rows / 20 columns.").pack()
            text = tk.Text(tab, wrap="none")
            text.pack(fill=tk.BOTH, expand=True)
            text.insert("1.0", frame.iloc[:200, :20].to_string())
            text.configure(state="disabled")
