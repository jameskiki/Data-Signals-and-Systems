"""Abstract adapter for table widget backends (Treeview, tksheet, etc).

This module provides a unified interface for different table widget implementations,
enabling feature-flag based backend switching via EVALDATA_TABLE_BACKEND environment variable.

Default: ttk.Treeview (native Tk, always available)
Optional: tksheet.Sheet (per-cell styling, feature-gated)
"""

from __future__ import annotations

import importlib.util
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import ttk

if TYPE_CHECKING:
    import pandas as pd


TABLE_BACKEND_ENV_VAR = "EVALDATA_TABLE_BACKEND"
TREEVIEW_TABLE_BACKEND = "treeview"
TKSHEET_TABLE_BACKEND = "tksheet"
DEFAULT_TABLE_BACKEND = TREEVIEW_TABLE_BACKEND
VALID_TABLE_BACKENDS = frozenset({TREEVIEW_TABLE_BACKEND, TKSHEET_TABLE_BACKEND})


def normalize_table_backend(backend: str | None) -> str:
    """Return a validated table backend name."""
    normalized = (backend or DEFAULT_TABLE_BACKEND).lower().strip()
    if normalized not in VALID_TABLE_BACKENDS:
        raise ValueError(
            f"Unknown {TABLE_BACKEND_ENV_VAR}: {normalized!r}. "
            f"Must be '{TREEVIEW_TABLE_BACKEND}' or '{TKSHEET_TABLE_BACKEND}'."
        )
    return normalized


def get_configured_table_backend() -> str:
    """Return the configured preview table backend."""
    return normalize_table_backend(os.getenv(TABLE_BACKEND_ENV_VAR, DEFAULT_TABLE_BACKEND))


def set_configured_table_backend(backend: str) -> str:
    """Persist the configured preview table backend for the current process."""
    normalized = normalize_table_backend(backend)
    os.environ[TABLE_BACKEND_ENV_VAR] = normalized
    return normalized


def is_tksheet_available() -> bool:
    """Return whether the optional tksheet dependency can be imported."""
    return importlib.util.find_spec("tksheet") is not None


class TableWidgetAdapter(ABC):
    """Abstract interface for table widget implementations."""

    @abstractmethod
    def get_widget(self) -> tk.Widget:
        """Return the underlying Tk widget (Treeview, Sheet, etc)."""
        ...

    @abstractmethod
    def configure_columns(
        self, columns: list[str], column_specs: list[dict] | None = None
    ) -> None:
        """Configure table columns.

        Args:
            columns: List of column identifiers/keys.
            column_specs: Optional list of dicts with keys like 'width', 'minwidth', 'anchor', 'stretch'.
        """
        ...

    @abstractmethod
    def insert_row(
        self,
        values: tuple,
        iid: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> str:
        """Insert a row with the given values.

        Args:
            values: Tuple of cell values.
            iid: Optional internal ID for the row. If None, auto-generated.
            tags: Optional tuple of tag names to apply to the row.

        Returns:
            The internal ID of the inserted row.
        """
        ...

    @abstractmethod
    def tag_configure(self, tag_name: str, bg: str | None = None, fg: str | None = None) -> None:
        """Configure a tag's background and foreground colors.

        Args:
            tag_name: Name of the tag.
            bg: Background color (e.g., '#ffffff').
            fg: Foreground color (e.g., '#000000').
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Remove all rows from the table."""
        ...

    @abstractmethod
    def set_selectmode(self, selectmode: str) -> None:
        """Set the selection mode ('none', 'browse', 'extended', etc)."""
        ...


class TTreeviewAdapter(TableWidgetAdapter):
    """Adapter wrapping ttk.Treeview."""

    def __init__(
        self,
        container: ttk.Frame,
        *,
        selectmode: str = "none",
        show_headings: bool = True,
    ):
        """Initialize Treeview adapter.

        Args:
            container: Parent ttk.Frame.
            selectmode: Selection mode for the Treeview.
            show_headings: Whether to show column headings.
        """
        self.container = container
        self._selectmode = selectmode
        self._tree = ttk.Treeview(
            container,
            selectmode=selectmode,
            show="headings" if show_headings else "tree",
        )

    def get_widget(self) -> ttk.Treeview:
        """Return the Treeview widget."""
        return self._tree

    def configure_columns(
        self, columns: list[str], column_specs: list[dict] | None = None
    ) -> None:
        """Configure Treeview columns."""
        self._tree.configure(columns=columns)
        specs = column_specs or []
        for col, spec in zip(columns, specs):
            self._tree.heading(
                col,
                text=spec.get("label", col),
                anchor=spec.get("heading_anchor", spec.get("anchor", "center")),
            )
            self._tree.column(
                col,
                width=spec.get("width", 100),
                minwidth=spec.get("minwidth", 50),
                anchor=spec.get("anchor", "center"),
                stretch=spec.get("stretch", False),
            )
        # Handle remaining columns without specs
        for col in columns[len(specs) :]:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=100, minwidth=50)

    def insert_row(
        self,
        values: tuple,
        iid: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> str:
        """Insert a row into the Treeview."""
        tags_arg = tags or ()
        return self._tree.insert("", tk.END, iid=iid, values=values, tags=tags_arg)

    def tag_configure(self, tag_name: str, bg: str | None = None, fg: str | None = None) -> None:
        """Configure a Treeview tag's colors."""
        kwargs = {}
        if bg is not None:
            kwargs["background"] = bg
        if fg is not None:
            kwargs["foreground"] = fg
        if kwargs:
            self._tree.tag_configure(tag_name, **kwargs)

    def clear(self) -> None:
        """Remove all rows from the Treeview."""
        for item in self._tree.get_children():
            self._tree.delete(item)

    def set_selectmode(self, selectmode: str) -> None:
        """Set Treeview selection mode."""
        self._selectmode = selectmode
        self._tree.configure(selectmode=selectmode)


class TksheetAdapter(TableWidgetAdapter):
    """Adapter wrapping tksheet.Sheet.

    Falls back gracefully if tksheet is not installed.
    """

    def __init__(
        self,
        container: ttk.Frame,
        *,
        selectmode: str = "none",
        show_headings: bool = True,
    ):
        """Initialize tksheet adapter.

        Args:
            container: Parent ttk.Frame.
            selectmode: Selection mode (converted to tksheet equivalents).
            show_headings: Whether to show column headings.

        Raises:
            ImportError: If tksheet is not installed.
        """
        try:
            import tksheet
        except ImportError as e:
            raise ImportError(
                "tksheet not installed. Install with: pip install tksheet"
            ) from e

        self.container = container
        self._selectmode = selectmode
        self._show_headings = show_headings

        # tksheet.Sheet doesn't have a direct 'selectmode', but we can control
        # selection via disable_bindings if needed. For now, we'll allow selection.
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

    def insert_row(
        self,
        values: tuple,
        iid: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> str:
        """Insert a row into the tksheet."""
        self._sheet.insert_row(list(values), redraw=False)
        row_idx = self._sheet.get_total_rows() - 1
        self._sheet.redraw()

        # TODO: tksheet per-cell styling support (tag_name -> cell color mapping)
        # For now, we insert the row without style.
        # tksheet allows per-cell styling via sheet.options_dict.update(...)
        # which we can map from tags in a future enhancement.

        return str(row_idx)

    def tag_configure(self, tag_name: str, bg: str | None = None, fg: str | None = None) -> None:
        """Configure a tag's colors.

        Note: tksheet styling is per-cell, not per-row like Treeview tags.
        This stub is for API compatibility; full implementation would require
        tracking tag-to-row mappings and applying cell-level styles.
        """
        # TODO: Implement per-cell coloring for tksheet
        pass

    def clear(self) -> None:
        """Remove all rows from the tksheet (keeping headers)."""
        self._sheet.set_sheet_data([], reset_row_positions=True, redraw=True)

    def set_selectmode(self, selectmode: str) -> None:
        """Set selection mode (stub for API compatibility)."""
        self._selectmode = selectmode
        # TODO: tksheet selection binding configuration


def create_table_adapter(
    container: ttk.Frame,
    *,
    selectmode: str = "none",
    show_headings: bool = True,
    backend: str | None = None,
) -> TableWidgetAdapter:
    """Factory function to create the appropriate table adapter.

    Reads EVALDATA_TABLE_BACKEND environment variable unless *backend* is passed:
    - 'tksheet': Use tksheet.Sheet (requires tksheet package)
    - 'treeview' or unset: Use ttk.Treeview (default, always available)

    Args:
        container: Parent ttk.Frame to host the widget.
        selectmode: Selection mode for the table.
        show_headings: Whether to show column headings.
        backend: Optional explicit backend override.

    Returns:
        TableWidgetAdapter instance (TTreeviewAdapter or TksheetAdapter).

    Raises:
        ValueError: If EVALDATA_TABLE_BACKEND is set to an unknown backend.
    """
    backend_name = normalize_table_backend(backend) if backend is not None else get_configured_table_backend()

    if backend_name == TREEVIEW_TABLE_BACKEND:
        return TTreeviewAdapter(container, selectmode=selectmode, show_headings=show_headings)
    if backend_name == TKSHEET_TABLE_BACKEND:
        try:
            return TksheetAdapter(container, selectmode=selectmode, show_headings=show_headings)
        except ImportError:
            # Fallback to Treeview if tksheet not installed
            print(
                f"Warning: {TABLE_BACKEND_ENV_VAR}={TKSHEET_TABLE_BACKEND} but tksheet not installed. "
                f"Falling back to Treeview."
            )
            return TTreeviewAdapter(container, selectmode=selectmode, show_headings=show_headings)

    raise ValueError(
        f"Unknown {TABLE_BACKEND_ENV_VAR}: {backend_name!r}. "
        f"Must be '{TREEVIEW_TABLE_BACKEND}' or '{TKSHEET_TABLE_BACKEND}'."
    )
