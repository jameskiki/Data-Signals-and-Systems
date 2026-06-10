import numpy as np

from Source.shared.demo_catalog import (
    CYCLE_EXCLUSION_STRESS_DEMO,
    CYCLE_VALIDATION_DEMO,
    DEMO_DATASET_SPEC_BY_KEY,
    build_demo_menu_description_lines,
    create_demo_dataset,
)


def test_cycle_validation_demo_is_registered() -> None:
    assert DEMO_DATASET_SPEC_BY_KEY[CYCLE_VALIDATION_DEMO.key] is CYCLE_VALIDATION_DEMO
    description_lines = build_demo_menu_description_lines(CYCLE_VALIDATION_DEMO)
    assert any("drifting-cycle" in line for line in description_lines)


def test_cycle_validation_demo_exposes_metric_drift() -> None:
    spec, dataframe = create_demo_dataset(CYCLE_VALIDATION_DEMO.key)

    assert spec is CYCLE_VALIDATION_DEMO
    assert {
        "time_s",
        "cycle_process",
        "cycle_reference_zero",
        "trigger_pulse",
        "true_cycle_index",
        "true_cycle_duration_s",
        "baseline_drift",
        "amplitude_scale",
    }.issubset(dataframe.columns)

    assert dataframe["true_cycle_index"].nunique() == 28
    assert dataframe["cycle_reference_zero"].min() < 0.0
    assert dataframe["cycle_reference_zero"].max() > 0.0
    assert set(np.unique(dataframe["trigger_pulse"])) <= {0.0, 1.0}

    cycle_metrics = dataframe.groupby("true_cycle_index", sort=True).agg(
        duration_s=("true_cycle_duration_s", "first"),
        mean_value=("cycle_process", "mean"),
        p2p=("cycle_process", lambda values: float(values.max() - values.min())),
    )

    assert cycle_metrics["duration_s"].iloc[-1] > cycle_metrics["duration_s"].iloc[0]
    assert cycle_metrics["mean_value"].iloc[-1] > cycle_metrics["mean_value"].iloc[0]
    assert cycle_metrics["p2p"].max() - cycle_metrics["p2p"].min() > 0.2


def test_cycle_exclusion_stress_demo_is_registered() -> None:
    assert DEMO_DATASET_SPEC_BY_KEY[CYCLE_EXCLUSION_STRESS_DEMO.key] is CYCLE_EXCLUSION_STRESS_DEMO
    description_lines = build_demo_menu_description_lines(CYCLE_EXCLUSION_STRESS_DEMO)
    assert any("deliberate faults" in line for line in description_lines)


def test_cycle_exclusion_stress_demo_exposes_clear_outliers() -> None:
    spec, dataframe = create_demo_dataset(CYCLE_EXCLUSION_STRESS_DEMO.key)

    assert spec is CYCLE_EXCLUSION_STRESS_DEMO
    assert {"is_outlier_cycle", "outlier_label", "true_cycle_duration_s", "cycle_process"}.issubset(dataframe.columns)

    cycle_metrics = dataframe.groupby("true_cycle_index", sort=True).agg(
        duration_s=("true_cycle_duration_s", "first"),
        mean_value=("cycle_process", "mean"),
        p2p=("cycle_process", lambda values: float(values.max() - values.min())),
        outlier_label=("outlier_label", "first"),
        is_outlier=("is_outlier_cycle", "first"),
    )

    assert int(cycle_metrics["is_outlier"].sum()) == 4
    assert set(cycle_metrics.loc[cycle_metrics["is_outlier"] == 1, "outlier_label"]) == {
        "low_amplitude",
        "short_cycle",
        "high_mean",
        "spike_outlier",
    }

    low_amp_cycle = cycle_metrics[cycle_metrics["outlier_label"] == "low_amplitude"].iloc[0]
    short_cycle = cycle_metrics[cycle_metrics["outlier_label"] == "short_cycle"].iloc[0]
    high_mean_cycle = cycle_metrics[cycle_metrics["outlier_label"] == "high_mean"].iloc[0]
    spike_cycle = cycle_metrics[cycle_metrics["outlier_label"] == "spike_outlier"].iloc[0]
    normal_cycles = cycle_metrics[cycle_metrics["outlier_label"] == "normal"]

    assert low_amp_cycle["p2p"] < normal_cycles["p2p"].median() * 0.55
    assert short_cycle["duration_s"] < normal_cycles["duration_s"].median() * 0.75
    assert high_mean_cycle["mean_value"] > normal_cycles["mean_value"].median() + 0.6
    assert spike_cycle["p2p"] > normal_cycles["p2p"].median() + 1.0