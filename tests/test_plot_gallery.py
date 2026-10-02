"""Tests for Plot Gallery reuse of production demo data and calculations."""

import numpy as np
import pandas as pd

from Source.datapreparation_app.plot_gallery import build_plot_gallery_examples
from Source.datapreparation_app.plot_gallery import PlotGallery
from Source.shared.demo_catalog import (
    COMPARISON_DEMO_SPECS,
    CYCLE_VALIDATION_DEMO,
    INPUT_OUTPUT_DEMO,
    SPECTRAL_REFERENCE_DEMO,
    create_demo_dataset,
)


def test_plot_gallery_examples_reuse_existing_demo_datasets() -> None:
    examples = build_plot_gallery_examples()
    spectral_spec, spectral_frame = create_demo_dataset(SPECTRAL_REFERENCE_DEMO.key)
    input_output_spec, input_output_frame = create_demo_dataset(INPUT_OUTPUT_DEMO.key)
    cycle_spec, cycle_frame = create_demo_dataset(CYCLE_VALIDATION_DEMO.key)

    assert examples.spectral_spec is spectral_spec
    assert examples.input_output_spec is input_output_spec
    assert examples.cycle_spec is cycle_spec
    assert examples.comparison_specs == COMPARISON_DEMO_SPECS
    pd.testing.assert_frame_equal(examples.spectral_frame, spectral_frame)
    pd.testing.assert_frame_equal(examples.input_output_frame, input_output_frame)
    pd.testing.assert_frame_equal(examples.cycle_frame, cycle_frame)
    for comparison_spec in COMPARISON_DEMO_SPECS:
        _, comparison_frame = create_demo_dataset(comparison_spec.key)
        pd.testing.assert_frame_equal(
            examples.comparison_frames[comparison_spec.basename],
            comparison_frame,
        )

    assert examples.transfer_result.source_column == "system_output"
    assert examples.transfer_result.comparison_column == "actuator_input"
    assert examples.spectrogram_result.source_column == "measured_signal"
    np.testing.assert_array_equal(
        examples.filtered_frame["measured_signal"],
        spectral_frame["measured_signal"],
    )
    assert "filtered_signal" in examples.filtered_frame
    assert not np.array_equal(
        examples.filtered_frame["filtered_signal"],
        examples.filtered_frame["measured_signal"],
    )


def test_plot_control_changes_schedule_debounced_refresh() -> None:
    gallery = PlotGallery.__new__(PlotGallery)
    gallery.window = object()
    scheduled: list[tuple[object, str, object]] = []
    gallery._schedule_debounced = lambda window, job_attr, callback: scheduled.append(
        (window, job_attr, callback)
    )

    class Variable:
        def trace_add(self, mode, callback):
            self.mode = mode
            self.callback = callback

    variable = Variable()
    render = lambda: None
    gallery._bind_plot_refresh([variable], "_time_plot_refresh_job_id", render)
    variable.callback("write", "", "")

    assert scheduled == [(gallery.window, "_time_plot_refresh_job_id", render)]
