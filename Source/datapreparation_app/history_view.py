"""Read-only list and graph of the prototype operation history."""

import json
import os
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from .history_deletion import plan_history_deletion, delete_history_nodes
from .report import build_publish_report
from .datasets import dataset_display_name, refresh_dataset_table

from Source.shared.operation_history import REPORT_VIEW_OPERATION, OperationHistory
from Source.data_ops.models import SIGNAL_FILTER_OPERATIONS


HISTORY_COLORS = {
    "input": ("Inputs / combined data", "#d9ecf5", "#0072b2"),
    "processing": ("Processing", "#fff0cf", "#8a5700"),
    "snapshot": ("Snapshot results", "#f2dfeb", "#804567"),
    "published": ("Published dataset", "#dff3ec", "#00745a"),
    "metadata": ("Metadata", "#eeeeee", "#4b5563"),
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
        self.window = tk.Toplevel(parent)
        self.window.title("History / Workflow (Prototype)")
        self.window.geometry("1400x850")
        ttk.Label(
            self.window,
            text="Prototype history. Save/reopen with Files -> Save Embedded Project / Open Project. "
                 "No replay or undo. Comparison/display settings are not recorded. Refresh after operations.",
            wraplength=950,
        ).pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(self.window, text="Refresh", command=self.refresh).pack(anchor="w", padx=10)
        if app is not None:
            ttk.Button(self.window, text="Preview Node Deletion...", command=self._preview_deletion).pack(anchor="w", padx=10)
        self.delete_button = ttk.Button(
            self.window, text="Confirm Highlighted Deletion...", command=self._confirm_deletion, state="disabled",
        )
        if app is not None:
            self.delete_button.pack(anchor="w", padx=10)
        legend = ttk.Frame(self.window)
        legend.pack(fill=tk.X, padx=10, pady=(6, 0))
        for label, fill, outline in HISTORY_COLORS.values():
            tk.Label(legend, text=label, background=fill, foreground=outline, padx=8, pady=3).pack(
                side=tk.LEFT, padx=(0, 6),
            )
        tk.Label(
            legend, text="solid arrow = data flow   - - - = included in publish",
            foreground=HISTORY_COLORS["published"][2], padx=8,
        ).pack(side=tk.LEFT)
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
        self.result_button = ttk.Button(left, text="Inspect Saved Result Tables", command=self._show_result_tables, state="disabled")
        self.result_button.pack(fill=tk.X)
        self.report_button = ttk.Button(
            left, text="Generate Report from Publish Node...", command=self._generate_report, state="disabled",
        )
        if app is not None:
            self.report_button.pack(fill=tk.X)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(right, background="white")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.refresh()

    def refresh(self) -> None:
        self._deletion_preview = None
        self.delete_button.configure(state="disabled")
        selection = self.steps.selection()
        self.steps.delete(*self.steps.get_children())
        self.canvas.delete("all")
        self._node_rectangles: dict[str, tuple[int, str]] = {}
        positions: dict[str, tuple[int, int]] = {}
        depths: dict[str, int] = {}
        step_positions: dict[str, tuple[int, int]] = {}
        step_depths: dict[str, int] = {}
        for index, step in enumerate(self.history.steps):
            text = f"{index + 1}. {step.operation}" + ("" if step.tracked else " [UNTRACKED]")
            category = history_category(step, self.history)
            _, fill, outline = HISTORY_COLORS[category]
            self.steps.insert("", tk.END, iid=step.id, text=text, tags=(category,))
            linked = [step_id for step_id in publish_linked_steps(step) if step_id in step_positions]
            depth = max(
                [depths[parent] + 1 for parent in step.input_revisions]
                + [step_depths[step_id] + 1 for step_id in linked],
                default=0,
            )
            x, y = 30 + depth * 300, 25 + index * 100
            for parent in step.input_revisions:
                px, py = positions[parent]
                self.canvas.create_line(px + 125, py + 60, x + 125, y, arrow=tk.LAST, fill="#64748b", width=1.5)
            data_parent_positions = {positions[parent] for parent in step.input_revisions}
            for step_id in linked:
                if step_positions[step_id] in data_parent_positions:
                    continue
                px, py = step_positions[step_id]
                self.canvas.create_line(
                    px + 250, py + 30, x, y + 30, arrow=tk.LAST,
                    fill=HISTORY_COLORS["published"][2], width=1.2, dash=(5, 3),
                )
            tag = f"step-{step.id}"
            rectangle = self.canvas.create_rectangle(
                x, y, x + 250, y + 60, fill=fill, outline=outline, width=1.5,
                dash=(4, 2) if category == "untracked" else (), tags=tag,
            )
            self._node_rectangles[step.id] = rectangle, outline
            self.canvas.create_text(
                x + 125, y + 30,
                text=f"{text}\n{HISTORY_COLORS[category][0]}: {self._node_name(step)}",
                width=235, fill="#111827", tags=tag,
            )
            self.canvas.tag_bind(tag, "<Button-1>", lambda event, step_id=step.id: self._select(step_id))
            positions.setdefault(step.output_revision, (x, y))
            depths.setdefault(step.output_revision, depth)
            step_positions[step.id] = (x, y)
            step_depths[step.id] = depth
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if selection and self.steps.exists(selection[0]):
            self._select(selection[0])
        elif self.history.steps:
            self._select(self.history.steps[-1].id)
        else:
            self.result_button.configure(state="disabled")
            self.report_button.configure(state="disabled")
            self._set_details("No operations recorded. Load a demo or file to begin.")

    def _node_name(self, step) -> str:
        context = getattr(self.app, "dataset_contexts", {}).get(step.label) if self.app is not None else None
        return dataset_display_name(step.label, context)

    def _generate_report(self) -> None:
        selection = self.steps.selection()
        if not selection or self.app is None:
            return
        step = next(step for step in self.history.steps if step.id == selection[0])
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
                width=3 if step_id == step.id else 1.5,
            )
        self.result_button.configure(state="normal" if self.history.artifact_tables.get(step.id) else "disabled")
        self.report_button.configure(state="normal" if step.operation == "publish" else "disabled")
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
            included = "Included workspace operations:\n" + "\n".join(lines) + "\n\n"
        self._set_details(
            f"{step.operation}\n{step.label}\n"
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
