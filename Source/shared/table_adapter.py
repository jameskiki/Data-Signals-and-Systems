"""Abstract adapter for table widget backends (Treeview, tksheet, etc).

This module provides a unified interface for different table widget implementations,
enabling feature-flag based backend switching via EVALDATA_TABLE_BACKEND environment variable.

Default: ttk.Treeview (native Tk, always available)
Optional: tksheet.Sheet (per-cell styling, feature-gated)
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import ttk

if TYPE_CHECKING:
    import pandas as pd


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
        self._tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

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
            self._tree.heading(col, text=spec.get("label", col))
            self._tree.column(
                col,
                width=spec.get("width", 100),
                minwidth=spec.get("minwidth", 50),
                anchor=spec.get("anchor", "e"),
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
            theme="dark blue",
            row_height=25,
            column_width=100,
            headers=[""] if show_headings else [],
        )
        self._sheet.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self._columns: list[str] = []

    def get_widget(self) -> tk.Widget:
        """Return the tksheet Sheet widget."""
        return self._sheet

    def configure_columns(
        self, columns: list[str], column_specs: list[dict] | None = None
    ) -> None:
        """Configure tksheet columns."""
        self._columns = columns
        self._sheet.data = [[col for col in columns]]  # Header row

        specs = column_specs or []
        for idx, (col, spec) in enumerate(zip(columns, specs)):
            width = spec.get("width", 100)
            self._sheet.column_width(column=idx, width=width)

    def insert_row(
        self,
        values: tuple,
        iid: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> str:
        """Insert a row into the tksheet."""
        row_idx = len(self._sheet.data)
        self._sheet.data.append(list(values))

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
        self._sheet.data = [[col for col in self._columns]]

    def set_selectmode(self, selectmode: str) -> None:
        """Set selection mode (stub for API compatibility)."""
        self._selectmode = selectmode
        # TODO: tksheet selection binding configuration


def create_table_adapter(
    container: ttk.Frame,
    *,
    selectmode: str = "none",
    show_headings: bool = True,
) -> TableWidgetAdapter:
    """Factory function to create the appropriate table adapter.

    Reads EVALDATA_TABLE_BACKEND environment variable:
    - 'tksheet': Use tksheet.Sheet (requires tksheet package)
    - 'treeview' or unset: Use ttk.Treeview (default, always available)

    Args:
        container: Parent ttk.Frame to host the widget.
        selectmode: Selection mode for the table.
        show_headings: Whether to show column headings.

    Returns:
        TableWidgetAdapter instance (TTreeviewAdapter or TksheetAdapter).

    Raises:
        ValueError: If EVALDATA_TABLE_BACKEND is set to an unknown backend.
    """
    backend = os.getenv("EVALDATA_TABLE_BACKEND", "treeview").lower().strip()

    if backend == "treeview":
        return TTreeviewAdapter(container, selectmode=selectmode, show_headings=show_headings)
    elif backend == "tksheet":
        try:
            return TksheetAdapter(container, selectmode=selectmode, show_headings=show_headings)
        except ImportError:
            # Fallback to Treeview if tksheet not installed
            print(
                f"Warning: EVALDATA_TABLE_BACKEND=tksheet but tksheet not installed. "
                f"Falling back to Treeview."
            )
            return TTreeviewAdapter(container, selectmode=selectmode, show_headings=show_headings)
    else:
        raise ValueError(
            f"Unknown EVALDATA_TABLE_BACKEND: {backend!r}. "
            f"Must be 'treeview' or 'tksheet'."
        )
