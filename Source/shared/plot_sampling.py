"""Peak-preserving display reduction; analysis arrays remain untouched."""

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.lines import Line2D


ADAPTIVE_PLOT_THRESHOLD = 20_000
MAX_DISPLAY_POINTS = 20_000


def envelope_indices(values: np.ndarray, max_points: int) -> np.ndarray:
    """Keep ordered bucket endpoints/extrema, inserting breaks across omitted gaps."""

    count = len(values)
    if max_points < 8:
        raise ValueError("max_points must be at least 8.")
    if count <= max_points:
        return np.arange(count, dtype=np.int64)

    bucket_count = max_points // 8
    step = (count + bucket_count - 1) // bucket_count
    full_count = count // step
    starts = np.arange(full_count, dtype=np.int64) * step
    blocks = values[:full_count * step].reshape(full_count, step)
    finite = np.isfinite(blocks)
    minima = starts + np.argmin(np.where(finite, blocks, np.inf), axis=1)
    maxima = starts + np.argmax(np.where(finite, blocks, -np.inf), axis=1)
    indices = [starts, starts + step - 1, minima, maxima]
    tail_start = full_count * step
    if tail_start < count:
        tail = values[tail_start:]
        valid_tail = np.flatnonzero(np.isfinite(tail))
        tail_indices = [tail_start, count - 1]
        if len(valid_tail):
            tail_indices.extend([
                tail_start + valid_tail[np.argmin(tail[valid_tail])],
                tail_start + valid_tail[np.argmax(tail[valid_tail])],
            ])
        indices.append(np.asarray(tail_indices, dtype=np.int64))
    selected = np.unique(np.concatenate(indices))

    gaps = np.flatnonzero(~np.isfinite(values))
    if len(gaps):
        positions = np.searchsorted(gaps, selected[:-1] + 1)
        candidates = gaps[np.minimum(positions, len(gaps) - 1)]
        breaks = candidates[(positions < len(gaps)) & (candidates < selected[1:])]
        selected = np.unique(np.concatenate([selected, breaks]))
    return selected


class AdaptiveLine:
    """Retain source arrays while sending only visible envelope points to Matplotlib."""

    def __init__(self, axis: Axes, x: np.ndarray, y: np.ndarray, **line_options) -> None:
        self.axis = axis
        self.x = x
        self.y = y
        self.increasing = bool(x[-1] >= x[0])
        self.last_view: tuple[float, float, int] | None = None
        indices = envelope_indices(y, self._point_budget())
        self.line, = axis.plot(x[indices], y[indices], **line_options)
        self.axis_callback = axis.callbacks.connect("xlim_changed", self._on_limits)
        self.canvas = axis.figure.canvas
        self.draw_callback = self.canvas.mpl_connect("draw_event", self._on_draw)
        self.close_callback = self.canvas.mpl_connect("close_event", self._on_close)

    def _point_budget(self) -> int:
        return min(MAX_DISPLAY_POINTS, max(64, int(self.axis.bbox.width) * 8))

    def refresh(self) -> bool:
        low, high = sorted(self.axis.get_xlim())
        budget = self._point_budget()
        view = (low, high, budget)
        if view == self.last_view:
            return False
        self.last_view = view
        if self.increasing:
            start = max(0, int(np.searchsorted(self.x, low, side="left")) - 1)
            end = min(len(self.x), int(np.searchsorted(self.x, high, side="right")) + 1)
        else:
            reversed_x = self.x[::-1]
            start = max(0, len(self.x) - int(np.searchsorted(reversed_x, high, side="right")) - 1)
            end = min(len(self.x), len(self.x) - int(np.searchsorted(reversed_x, low, side="left")) + 1)
        indices = envelope_indices(self.y[start:end], budget) + start
        self.line.set_data(self.x[indices], self.y[indices])
        return True

    def _on_limits(self, _axis) -> None:
        self.refresh()

    def _on_draw(self, _event) -> None:
        if self.refresh():
            self.axis.figure.canvas.draw_idle()

    def _on_close(self, _event) -> None:
        self.axis.callbacks.disconnect(self.axis_callback)
        self.canvas.mpl_disconnect(self.draw_callback)
        self.canvas.mpl_disconnect(self.close_callback)


def plot_adaptive_line(axis: Axes, x_values, y_values, **line_options) -> Line2D:
    """Reduce large numeric signals on monotonic axes; retain other plot behavior."""

    x_dtype = x_values.dtype if hasattr(x_values, "dtype") else np.asarray(x_values).dtype
    y_dtype = y_values.dtype if hasattr(y_values, "dtype") else np.asarray(y_values).dtype
    if (
        len(y_values) <= ADAPTIVE_PLOT_THRESHOLD
        or not pd.api.types.is_numeric_dtype(y_dtype)
        or pd.api.types.is_complex_dtype(y_dtype)
        or pd.api.types.is_complex_dtype(x_dtype)
        or not (
            pd.api.types.is_numeric_dtype(x_dtype)
            or pd.api.types.is_datetime64_any_dtype(x_dtype)
        )
    ):
        line, = axis.plot(x_values, y_values, **line_options)
        return line

    axis.xaxis.update_units(x_values)
    converted_x = np.asarray(axis.convert_xunits(x_values))
    if not np.issubdtype(converted_x.dtype, np.number):
        line, = axis.plot(x_values, y_values, **line_options)
        return line
    x = converted_x
    monotonic = np.all(x[1:] >= x[:-1]) or np.all(x[1:] <= x[:-1])
    if not np.isfinite(x).all() or not monotonic:
        line, = axis.plot(x_values, y_values, **line_options)
        return line
    if isinstance(y_values, pd.Series):
        y = y_values.to_numpy(dtype=float, na_value=np.nan, copy=False)
    else:
        y = np.asarray(y_values, dtype=float)
    controller = AdaptiveLine(axis, x, y, **line_options)
    controller.sources = (x_values, y_values)
    # Matplotlib stores weak references to bound callbacks, so the line owns its controller.
    controller.line._evaldata_adaptive_line = controller
    if not any(text.get_gid() == "evaldata-adaptive-display" for text in axis.texts):
        note = axis.text(
            0.01, 0.01, "Adaptive display; calculations use full data",
            transform=axis.transAxes, fontsize=7, color="#666666",
        )
        note.set_gid("evaldata-adaptive-display")
    return controller.line
