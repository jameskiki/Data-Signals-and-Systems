"""tksheet adapter for dataframe preview tables."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import tksheet


class TableWidgetAdapter:
    """Adapter wrapping the tksheet preview widget."""

    def __init__(
        self,
        container: ttk.Frame,
        *,
        show_headings: bool = True,
    ):
        """Initialize tksheet adapter.

        Args:
            container: Parent ttk.Frame.
            show_headings: Whether to show column headings.
        """
        self.container = container
        self._show_headings = show_headings

        self._sheet = tksheet.Sheet(
            container,
            theme="light blue",
            row_height=25,
            column_width=100,
            default_header_height=2,
            align="center",
            header_align="center",
            show_header=show_headings,
        )
        self._sheet.set_options(
            redraw=False,
            table_bg="#ffffff",
            table_fg="#111111",
            header_bg="#ffffff",
            header_fg="#111111",
            index_bg="#ffffff",
            index_fg="#111111",
            table_grid_fg="#e1e1e1",
            header_grid_fg="#d3d3d3",
            index_grid_fg="#d3d3d3",
            align="center",
            header_align="center",
        )
        self._columns: list[str] = []

    def get_widget(self) -> tk.Widget:
        """Return the tksheet Sheet widget."""
        return self._sheet

    def configure_columns(
        self, columns: list[str], column_specs: list[dict] | None = None
    ) -> None:
        """Configure tksheet columns."""
        self._columns = columns
        specs = column_specs or []
        header_labels = [spec.get("label", col) for col, spec in zip(columns, specs)]
        if len(header_labels) < len(columns):
            header_labels.extend(columns[len(header_labels) :])

        # Keep headers separate from sheet data (tksheet renders these independently).
        self._sheet.headers(header_labels if self._show_headings else [], redraw=False)
        if self._show_headings and any("\n" in str(label) for label in header_labels):
            self._sheet.set_header_height_lines(2, redraw=False)
        self._sheet.total_columns(len(columns))
        self._sheet.set_sheet_data([], reset_col_positions=True, reset_row_positions=True, redraw=False)
        self._sheet.dehighlight_columns("all", redraw=False)

        for idx, (_, spec) in enumerate(zip(columns, specs)):
            width = spec.get("width", 100)
            self._sheet.column_width(column=idx, width=width)
            column_bg = spec.get("bg")
            column_fg = spec.get("fg")
            if column_bg is not None or column_fg is not None:
                self._sheet.highlight_columns(
                    idx,
                    bg=column_bg if column_bg is not None else False,
                    fg=column_fg if column_fg is not None else False,
                    highlight_header=True,
                    redraw=False,
                    overwrite=True,
                )
        self._sheet.redraw()

    def set_rows(self, rows: list[list[str]]) -> None:
        """Replace the preview data and redraw once."""
        self._sheet.set_sheet_data(
            rows,
            reset_col_positions=False,
            reset_row_positions=True,
            redraw=True,
            reset_highlights=False,
            keep_formatting=True,
        )


def create_table_adapter(
    container: ttk.Frame,
    *,
    show_headings: bool = True,
) -> TableWidgetAdapter:
    """Create the tksheet preview-table adapter.

    Args:
        container: Parent ttk.Frame to host the widget.
        show_headings: Whether to show column headings.

    Returns:
        TableWidgetAdapter instance.
    """
    return TableWidgetAdapter(container, show_headings=show_headings)
