"""Shared persisted UI state used across all apps."""

from __future__ import annotations

import json
import pathlib
import tkinter as tk

from Source.shared.plot_options import PlotStyle


DEFAULT_TABLE_BACKEND = "treeview"


def _ui_state_config_path() -> pathlib.Path:
    """Return the path to the global persisted UI state JSON file."""

    path = pathlib.Path.home() / ".evaldata" / "ui_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_plot_style_config_path() -> pathlib.Path:
    """Return the legacy plot-style config path for backward compatibility."""

    return pathlib.Path.home() / ".evaldata" / "plot_style.json"


def _resolve_ui_state_path(path: pathlib.Path | None = None) -> pathlib.Path:
    """Resolve the file to read persisted UI state from."""

    if path is not None:
        return path

    current_path = _ui_state_config_path()
    if current_path.exists():
        return current_path

    legacy_path = _legacy_plot_style_config_path()
    if legacy_path.exists():
        return legacy_path

    return current_path


class UiStateVars:
    """Tkinter variables mirroring persisted plot-style and preview settings."""

    def __init__(self) -> None:
        defaults = PlotStyle()
        self.show_grid = tk.BooleanVar(value=defaults.show_grid)
        self.show_subgrid = tk.BooleanVar(value=defaults.show_subgrid)
        self.show_legend = tk.BooleanVar(value=defaults.show_legend)
        self.grid_alpha = tk.DoubleVar(value=defaults.grid_alpha)
        self.subgrid_alpha = tk.DoubleVar(value=defaults.subgrid_alpha)
        self.line_width = tk.DoubleVar(value=defaults.line_width)
        self.marker_size = tk.DoubleVar(value=defaults.marker_size)
        self.title_fontsize = tk.IntVar(value=defaults.title_fontsize)
        self.label_fontsize = tk.IntVar(value=defaults.label_fontsize)
        self.tick_fontsize = tk.IntVar(value=defaults.tick_fontsize)
        self.legend_fontsize = tk.IntVar(value=defaults.legend_fontsize)
        self.font_family = tk.StringVar(value=defaults.font_family)
        self.marker = tk.StringVar(value=defaults.marker)
        self.legend_location = tk.StringVar(value=defaults.legend_location)
        self.table_backend = tk.StringVar(value=DEFAULT_TABLE_BACKEND)

    def reset_to_defaults(self) -> None:
        """Reset all variables back to PlotStyle defaults."""

        defaults = PlotStyle()
        self.show_grid.set(defaults.show_grid)
        self.show_subgrid.set(defaults.show_subgrid)
        self.show_legend.set(defaults.show_legend)
        self.grid_alpha.set(defaults.grid_alpha)
        self.subgrid_alpha.set(defaults.subgrid_alpha)
        self.line_width.set(defaults.line_width)
        self.marker_size.set(defaults.marker_size)
        self.title_fontsize.set(defaults.title_fontsize)
        self.label_fontsize.set(defaults.label_fontsize)
        self.tick_fontsize.set(defaults.tick_fontsize)
        self.legend_fontsize.set(defaults.legend_fontsize)
        self.font_family.set(defaults.font_family)
        self.marker.set(defaults.marker)
        self.legend_location.set(defaults.legend_location)
        self.table_backend.set(DEFAULT_TABLE_BACKEND)

    def save_to_file(self, path: pathlib.Path | None = None) -> None:
        """Persist current UI settings to *path* (default: user config)."""

        target = path or _ui_state_config_path()
        data = {
            "show_grid": self.show_grid.get(),
            "show_subgrid": self.show_subgrid.get(),
            "show_legend": self.show_legend.get(),
            "grid_alpha": round(self.grid_alpha.get(), 4),
            "subgrid_alpha": round(self.subgrid_alpha.get(), 4),
            "line_width": round(self.line_width.get(), 4),
            "marker_size": round(self.marker_size.get(), 4),
            "title_fontsize": self.title_fontsize.get(),
            "label_fontsize": self.label_fontsize.get(),
            "tick_fontsize": self.tick_fontsize.get(),
            "legend_fontsize": self.legend_fontsize.get(),
            "font_family": self.font_family.get(),
            "marker": self.marker.get(),
            "legend_location": self.legend_location.get(),
            "table_backend": self.table_backend.get(),
        }
        try:
            target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def load_from_file(self, path: pathlib.Path | None = None) -> None:
        """Load persisted UI settings from *path* (default: user config)."""

        target = _resolve_ui_state_path(path)
        try:
            data: dict = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        bool_keys = {"show_grid", "show_subgrid", "show_legend"}
        float_keys = {"grid_alpha", "subgrid_alpha", "line_width", "marker_size"}
        int_keys = {"title_fontsize", "label_fontsize", "tick_fontsize", "legend_fontsize"}
        str_keys = {"font_family", "marker", "legend_location"}

        for key in bool_keys:
            if key in data:
                getattr(self, key).set(bool(data[key]))
        for key in float_keys:
            if key in data:
                try:
                    getattr(self, key).set(float(data[key]))
                except (ValueError, TypeError):
                    pass
        for key in int_keys:
            if key in data:
                try:
                    getattr(self, key).set(int(data[key]))
                except (ValueError, TypeError):
                    pass
        for key in str_keys:
            if key in data:
                getattr(self, key).set(str(data[key]))
        if "table_backend" in data:
            backend = str(data["table_backend"]).strip().lower() or DEFAULT_TABLE_BACKEND
            self.table_backend.set(backend)

    def to_plot_style(self) -> PlotStyle:
        """Build a sanitized PlotStyle from current Tk variables."""

        defaults = PlotStyle()

        def _safe_float(var, default: float) -> float:
            try:
                return float(var.get())
            except (ValueError, tk.TclError):
                return default

        def _safe_int(var, default: int) -> int:
            try:
                return int(var.get())
            except (ValueError, tk.TclError):
                return default

        return PlotStyle(
            show_grid=self.show_grid.get(),
            show_subgrid=self.show_subgrid.get(),
            show_legend=self.show_legend.get(),
            grid_alpha=round(_safe_float(self.grid_alpha, defaults.grid_alpha), 2),
            subgrid_alpha=round(_safe_float(self.subgrid_alpha, defaults.subgrid_alpha), 2),
            line_width=max(0.1, _safe_float(self.line_width, defaults.line_width)),
            marker_size=max(0.5, _safe_float(self.marker_size, defaults.marker_size)),
            title_fontsize=max(4, _safe_int(self.title_fontsize, defaults.title_fontsize)),
            label_fontsize=max(4, _safe_int(self.label_fontsize, defaults.label_fontsize)),
            tick_fontsize=max(4, _safe_int(self.tick_fontsize, defaults.tick_fontsize)),
            legend_fontsize=max(4, _safe_int(self.legend_fontsize, defaults.legend_fontsize)),
            font_family=self.font_family.get() or defaults.font_family,
            marker=self.marker.get() or defaults.marker,
            legend_location=self.legend_location.get() or defaults.legend_location,
        )


PlotStyleVars = UiStateVars