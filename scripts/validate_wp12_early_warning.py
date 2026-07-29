#!/usr/bin/env python3
"""Generate frozen WP12 synthetic early-warning evidence and model artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from semifab_poc.config import load_runtime_config, runtime_config_sha256
from semifab_poc.models.early_warning import (
    CensorReason,
    EarlyWarningConfig,
    EarlyWarningPredictor,
    ExcursionLabel,
    ModelKind,
    TargetConfig,
    WarningDataset,
    WarningObservationWindow,
    evaluate_predictions,
    generate_excursion_labels,
    load_early_warning_config,
    normalization_for_warning_runtime,
)
from semifab_poc.simulation.chain import (
    ChainEventKind,
    ChainScenario,
    ChainSchedule,
    ChainTrace,
    SyntheticChainRunner,
)
from semifab_poc.simulation.coupling import UtilityCmpTopology
from semifab_poc.simulation.sensors import SensorConfig


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "models" / "early_warning.yaml"
RUNTIME_PATH = ROOT / "configs" / "default.yaml"
OUTPUT_DIR = ROOT / "reports" / "early_warning"
MODEL_DIR = OUTPUT_DIR / "models"
FIGURE_DIR = OUTPUT_DIR / "figures"
EXPECTED_REVISION_1_1_PROBABILITY_SHA256 = (
    "5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede"
)


UNITS = {
    "electrical.grid_voltage": "pu",
    "electrical.ups_output_voltage": "pu",
    "electrical.ups_battery_energy": "J",
    "drive.motor_angular_speed": "rad/s",
    "pump.volumetric_flow": "m^3/s",
    "upw.supply_pressure": "Pa",
    "upw.tool_flow": "m^3/s",
    "upw.temperature": "K",
}


LIMITS = {
    "electrical.grid_voltage": (0.0, 1.5),
    "electrical.ups_output_voltage": (0.0, 1.5),
    "electrical.ups_battery_energy": (0.0, None),
    "drive.motor_angular_speed": (0.0, None),
    "pump.volumetric_flow": (0.0, 5.0e-4),
    "upw.supply_pressure": (0.0, 600_000.0),
    "upw.tool_flow": (0.0, 5.0e-4),
    "upw.temperature": (273.15, 373.15),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_csv_atomic(path: Path, rows: Sequence[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    fieldnames = list(rows[0])
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def sensor_configs(config: EarlyWarningConfig, *, robustness: str = "PRIMARY") -> tuple[SensorConfig, ...]:
    if robustness == "PRIMARY":
        noise_scale, delay_s, loss = 1.0, config.sensors.delay_s, config.sensors.packet_loss_probability
    elif robustness == "HIGH_NOISE":
        noise_scale, delay_s, loss = 2.0, config.sensors.delay_s, config.sensors.packet_loss_probability
    elif robustness == "HIGH_DELAY":
        noise_scale, delay_s, loss = 1.0, 0.20, config.sensors.packet_loss_probability
    elif robustness == "HIGH_DROPOUT":
        noise_scale, delay_s, loss = 1.0, config.sensors.delay_s, 0.10
    else:
        raise ValueError(f"unknown observation robustness case: {robustness}")
    sensors: list[SensorConfig] = []
    for index, signal_id in enumerate(config.features.allowed_signal_ids):
        minimum, maximum = LIMITS[signal_id]
        sensors.append(
            SensorConfig(
                sensor_id=f"warning-{index:02d}-{signal_id}",
                signal_id=signal_id,
                unit=UNITS[signal_id],
                sample_period_s=config.sensors.sample_period_s,
                provenance_id=f"synthetic-warning-sensor-v1:{robustness}",
                noise_std=config.sensors.noise_by_signal[signal_id] * noise_scale,
                delay_s=delay_s,
                packet_loss_probability=loss,
                timestamp_jitter_std_s=config.sensors.timestamp_jitter_std_s,
                minimum_value=minimum,
                maximum_value=maximum,
            )
        )
    return tuple(sensors)


def chain_runner(
    config: EarlyWarningConfig,
    topology: UtilityCmpTopology,
    *,
    robustness: str = "PRIMARY",
) -> SyntheticChainRunner:
    runtime = load_runtime_config(RUNTIME_PATH)
    coupling = replace(
        runtime.coupling,
        topology=topology,
        link_strength=(0.0 if topology is UtilityCmpTopology.NO_CONNECTION else 1.0),
    )
    return SyntheticChainRunner(
        runtime,
        ChainSchedule(
            dt_s=config.simulation.dt_s,
            duration_s=config.simulation.duration_s,
            plant_warmup_s=config.simulation.plant_warmup_s,
            dress_end_s=config.simulation.dress_end_s,
            polish_start_s=config.simulation.polish_start_s,
        ),
        coupling,
        sensor_configs(config, robustness=robustness),
    )


def _severity(index: int, count: int) -> float:
    return 0.5 if count == 1 else index / (count - 1)


def scenario_for_family(
    family: ChainEventKind,
    *,
    config: EarlyWarningConfig,
    split: str,
    index: int,
    count: int,
    seed: int,
) -> ChainScenario:
    rng = np.random.default_rng(seed)
    severity = _severity(index, count)
    anchored_families = {
        ChainEventKind.GRID_INTERRUPTION,
        ChainEventKind.PUMP_TRIP,
        ChainEventKind.VALVE_RESTRICTION,
        ChainEventKind.TOOL_DEMAND_SPIKE,
    }
    full_dress_anchor = index == count - 1 and family in anchored_families
    start_s = (
        config.simulation.full_dress_anchor_start_s
        if full_dress_anchor
        else float(0.5 + rng.uniform(0.0, 2.2))
    )
    default = {
        "run_id": f"{split.lower()}-{family.value.lower()}-{index:02d}",
        "family": family,
        "seed": seed,
        "event_start_s": start_s,
    }
    if family is ChainEventKind.NORMAL:
        return ChainScenario(**default, event_duration_s=0.0)
    if family is ChainEventKind.HEALTHY_SAG:
        return ChainScenario(
            **default,
            event_duration_s=float(0.10 + 0.90 * severity),
            grid_voltage_pu=float(0.90 - 0.30 * severity),
        )
    duration_s = (
        config.simulation.full_dress_anchor_end_s
        - config.simulation.full_dress_anchor_start_s
        if full_dress_anchor
        else min(float(0.50 + 4.80 * severity), 5.90 - start_s)
    )
    if family is ChainEventKind.GRID_INTERRUPTION:
        return ChainScenario(
            **default,
            event_duration_s=duration_s,
            battery_capacity_j=float(4_500.0 - 4_250.0 * severity),
            ups_load_power_w=float(1_800.0 + 1_100.0 * severity),
        )
    if family is ChainEventKind.PUMP_TRIP:
        return ChainScenario(**default, event_duration_s=duration_s)
    if family is ChainEventKind.VALVE_RESTRICTION:
        return ChainScenario(
            **default,
            event_duration_s=duration_s,
            valve_position=float(0.85 - 0.80 * severity),
        )
    if family is ChainEventKind.TOOL_DEMAND_SPIKE:
        return ChainScenario(
            **default,
            event_duration_s=duration_s,
            tool_demand_m3_s=float(1.2e-4 + 3.3e-4 * severity),
        )
    raise ValueError(f"unsupported primary family: {family}")


def scenarios_for_split(
    config: EarlyWarningConfig,
    split: str,
) -> list[ChainScenario]:
    if split == "TRAIN":
        count = config.splits.runs_per_family.training
        seed_start = config.splits.train_seed_start
    elif split == "CALIBRATION":
        count = config.splits.runs_per_family.calibration
        seed_start = config.splits.calibration_seed_start
    elif split == "CONFORMAL_CALIBRATION":
        count = config.splits.runs_per_family.conformal_calibration
        seed_start = config.splits.conformal_calibration_seed_start
    elif split == "TEST":
        count = config.splits.runs_per_family.test
        seed_start = config.splits.test_seed_start
    else:
        raise ValueError(f"unknown primary split: {split}")
    scenarios: list[ChainScenario] = []
    for family_index, family_name in enumerate(config.splits.primary_families):
        family = ChainEventKind(family_name)
        for index in range(count):
            seed = seed_start + family_index * 100 + index
            scenarios.append(
                scenario_for_family(
                    family,
                    config=config,
                    split=split,
                    index=index,
                    count=count,
                    seed=seed,
                )
            )
    return scenarios


def observation_robustness_scenarios(
    config: EarlyWarningConfig,
    test_scenarios: Sequence[ChainScenario],
) -> list[ChainScenario]:
    """Select the frozen upper-median and maximum TEST endpoint per family."""

    selected: list[ChainScenario] = []
    for family_name in config.splits.primary_families:
        family_scenarios = [
            scenario
            for scenario in test_scenarios
            if scenario.family.value == family_name
        ]
        if not family_scenarios:
            raise ValueError(f"TEST contains no scenarios for family {family_name}")
        indices_by_position = {
            "UPPER_MEDIAN": len(family_scenarios) // 2,
            "MAXIMUM": len(family_scenarios) - 1,
        }
        indices = [
            indices_by_position[position]
            for position in config.evaluation.observation_robustness_family_positions
        ]
        if len(set(indices)) != len(indices):
            raise ValueError(
                f"observation robustness positions collapse for family {family_name}"
            )
        selected.extend(family_scenarios[index] for index in indices)
    return selected


def unseen_compound_scenarios(config: EarlyWarningConfig) -> list[ChainScenario]:
    count = config.splits.runs_per_family.unseen_compound
    scenarios: list[ChainScenario] = []
    for index in range(count):
        severity = _severity(index, count)
        seed = config.splits.unseen_compound_seed_start + index
        rng = np.random.default_rng(seed)
        start_s = float(0.5 + rng.uniform(0.0, 1.5))
        scenarios.append(
            ChainScenario(
                run_id=f"unseen-compound-{index:02d}",
                family=ChainEventKind.COMPOUND_INTERRUPTION_DEMAND,
                seed=seed,
                event_start_s=start_s,
                event_duration_s=min(2.0 + 3.0 * severity, 5.90 - start_s),
                battery_capacity_j=1_500.0 - 1_250.0 * severity,
                ups_load_power_w=2_000.0 + 800.0 * severity,
                tool_demand_m3_s=2.0e-4 + 2.0e-4 * severity,
            )
        )
    return scenarios


def structural_null_scenarios(config: EarlyWarningConfig) -> list[ChainScenario]:
    count = config.splits.runs_per_family.structural_null
    scenarios: list[ChainScenario] = []
    for index in range(count):
        seed = config.splits.structural_null_seed_start + index
        scenarios.append(
            ChainScenario(
                run_id=f"structural-null-{index:02d}",
                family=ChainEventKind.GRID_INTERRUPTION,
                seed=seed,
                event_start_s=0.5 + 0.1 * index,
                event_duration_s=5.0 - 0.1 * index,
                battery_capacity_j=250.0,
                ups_load_power_w=2_900.0,
            )
        )
    return scenarios


def normalization_for_scenario(
    scenario: ChainScenario,
    runtime: Any,
) -> dict[str, tuple[float, float]]:
    return normalization_for_warning_runtime(
        scenario_battery_capacity_j=scenario.battery_capacity_j,
        runtime=runtime,
    )


def build_dataset(
    config: EarlyWarningConfig,
    traces_by_split: dict[str, list[tuple[ChainScenario, ChainTrace]]],
    reference_trace: ChainTrace,
    *,
    target_config: TargetConfig | None = None,
) -> tuple[WarningDataset, dict[str, object]]:
    target = target_config or config.target
    reference_rows = reference_trace.truth_rows
    reference_mrr = [float(row["cmp_mrr_m_s"]) for row in reference_rows]
    runtime = load_runtime_config(RUNTIME_PATH)
    feature_names: tuple[str, ...] | None = None
    feature_rows: list[np.ndarray] = []
    labels: list[int] = []
    run_ids: list[str] = []
    split_ids: list[str] = []
    decision_steps: list[int] = []
    decision_times: list[float] = []
    first_onsets: list[float] = []
    censor_totals = {reason.value: 0 for reason in CensorReason}
    split_censor_totals: dict[str, dict[str, int]] = {}
    run_summaries: list[dict[str, object]] = []
    feature_extractor = EarlyWarningPredictor(
        ModelKind.PREVALENCE,
        config.features,
        config.models,
    ).extractor
    decision_stride = round(target.decision_period_s / config.simulation.dt_s)
    if not math.isclose(
        decision_stride * config.simulation.dt_s,
        target.decision_period_s,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError("decision period must be an integer simulation-step multiple")

    for split, entries in traces_by_split.items():
        split_censors = split_censor_totals.setdefault(
            split,
            {reason.value: 0 for reason in CensorReason},
        )
        for scenario, trace in entries:
            rows = trace.truth_rows
            if len(rows) != len(reference_rows):
                raise ValueError("disturbed and reference traces must have equal length")
            trace_steps = [int(row["step_index"]) for row in rows]
            decision_step_ids = trace_steps[decision_stride - 1 :: decision_stride]
            labeling = generate_excursion_labels(
                run_id=scenario.run_id,
                timestamps_s=[float(row["timestamp_s"]) for row in rows],
                true_mrr_m_s=[float(row["cmp_mrr_m_s"]) for row in rows],
                reference_mrr_m_s=reference_mrr,
                process_modes=[str(row["cmp_mode"]) for row in rows],
                decision_step_indices=decision_step_ids,
                trace_step_indices=trace_steps,
                config=target,
            )
            for reason, count in labeling.censor_counts.items():
                censor_totals[reason.value] += int(count)
                split_censors[reason.value] += int(count)
            row_by_step = {int(row["step_index"]): row for row in rows}
            observations = tuple(trace.observations)
            normalization = normalization_for_scenario(scenario, runtime)
            positive_rows = 0
            for label in labeling.labels:
                truth_row = row_by_step[label.decision_step_index]
                available = tuple(
                    observation
                    for observation in observations
                    if observation.arrival_timestamp_s
                    <= label.decision_timestamp_s + 1.0e-12
                )
                window = WarningObservationWindow(
                    run_id=scenario.run_id,
                    decision_step_index=label.decision_step_index,
                    decision_timestamp_s=label.decision_timestamp_s,
                    observations=available,
                    process_mode=str(truth_row["cmp_mode"]),
                    polish_start_s=config.simulation.polish_start_s,
                    normalization_by_signal=normalization,
                    sensor_sample_period_s=config.sensors.sample_period_s,
                    battery_capacity_ratio=(
                        scenario.battery_capacity_j / runtime.electrical.battery_capacity_j
                    ),
                    ups_load_ratio=(
                        scenario.ups_load_power_w / runtime.electrical.ups_rated_power_w
                    ),
                )
                vector = feature_extractor.transform(window)
                if feature_names is None:
                    feature_names = vector.names
                elif vector.names != feature_names:
                    raise ValueError("feature schema changed across runs")
                feature_rows.append(vector.values)
                label_value = int(label.excursion_within_horizon)
                labels.append(label_value)
                positive_rows += label_value
                run_ids.append(scenario.run_id)
                split_ids.append(split)
                decision_steps.append(label.decision_step_index)
                decision_times.append(label.decision_timestamp_s)
                first_onsets.append(
                    np.nan
                    if label.first_excursion_timestamp_s is None
                    else label.first_excursion_timestamp_s
                )
            run_summaries.append(
                {
                    "run_id": scenario.run_id,
                    "split": split,
                    "family": scenario.family.value,
                    "seed": scenario.seed,
                    "event_start_s": scenario.event_start_s,
                    "event_duration_s": scenario.event_duration_s,
                    "battery_capacity_j": scenario.battery_capacity_j,
                    "ups_load_power_w": scenario.ups_load_power_w,
                    "valve_position": scenario.valve_position,
                    "tool_demand_m3_s": scenario.tool_demand_m3_s,
                    "eligible_rows": len(labeling.labels),
                    "positive_rows": positive_rows,
                    "episode_count": len(labeling.episode_onset_step_indices),
                    "episode_onsets": list(labeling.episode_onset_step_indices),
                    "censor_counts": {
                        reason.value: int(count)
                        for reason, count in labeling.censor_counts.items()
                    },
                    "minimum_effective_availability": min(
                        float(row["effective_availability"]) for row in rows
                    ),
                    "end_dress_pad_activity": float(
                        min(
                            rows,
                            key=lambda row: abs(
                                float(row["timestamp_s"]) - config.simulation.dress_end_s
                            ),
                        )["cmp_pad_surface_activity"]
                    ),
                }
            )
    if feature_names is None:
        raise ValueError("dataset generation produced no eligible rows")
    dataset = WarningDataset(
        feature_names=feature_names,
        features=np.vstack(feature_rows),
        labels=np.asarray(labels, dtype=int),
        run_ids=tuple(run_ids),
        split_ids=tuple(split_ids),
        decision_step_indices=np.asarray(decision_steps, dtype=int),
        decision_timestamps_s=np.asarray(decision_times, dtype=float),
        first_excursion_timestamps_s=np.asarray(first_onsets, dtype=float),
    )
    dataset.validate()
    split_groups = {
        split: sorted({run_id for run_id, row_split in zip(run_ids, split_ids, strict=True) if row_split == split})
        for split in sorted(set(split_ids))
    }
    group_sets = [set(values) for values in split_groups.values()]
    if any(left & right for index, left in enumerate(group_sets) for right in group_sets[index + 1 :]):
        raise ValueError("warning dataset run groups overlap")
    manifest = {
        "target": target.model_dump(mode="json"),
        "feature_count": len(feature_names),
        "row_count": len(labels),
        "positive_count": int(np.sum(dataset.labels)),
        "split_rows": {
            split: int(sum(value == split for value in split_ids)) for split in split_groups
        },
        "split_positive_rows": {
            split: int(
                sum(label for label, value in zip(labels, split_ids, strict=True) if value == split)
            )
            for split in split_groups
        },
        "split_groups": split_groups,
        "split_group_sha256": canonical_sha256(split_groups),
        "censor_counts": censor_totals,
        "split_censor_counts": split_censor_totals,
        "run_summaries": run_summaries,
        "forbidden_online_signals": list(config.features.forbidden_signal_ids),
        "future_or_latent_feature_count": 0,
    }
    return dataset, manifest


def dataset_csv_rows(dataset: WarningDataset) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(len(dataset.labels)):
        row: dict[str, object] = {
            "run_id": dataset.run_ids[index],
            "split_id": dataset.split_ids[index],
            "decision_step_index": int(dataset.decision_step_indices[index]),
            "decision_timestamp_s": float(dataset.decision_timestamps_s[index]),
            "label": int(dataset.labels[index]),
            "first_excursion_timestamp_s": (
                ""
                if not np.isfinite(dataset.first_excursion_timestamps_s[index])
                else float(dataset.first_excursion_timestamps_s[index])
            ),
        }
        row.update(
            {
                feature_name: float(dataset.features[index, feature_index])
                for feature_index, feature_name in enumerate(dataset.feature_names)
            }
        )
        rows.append(row)
    return rows


def prediction_csv_rows(
    dataset: WarningDataset,
    model_kind: ModelKind,
    probabilities: np.ndarray,
    prediction_sets: Sequence[Sequence[int]],
    latencies: np.ndarray,
    threshold: float,
) -> list[dict[str, object]]:
    return [
        {
            "model_kind": model_kind.value,
            "run_id": dataset.run_ids[index],
            "split_id": dataset.split_ids[index],
            "decision_step_index": int(dataset.decision_step_indices[index]),
            "decision_timestamp_s": float(dataset.decision_timestamps_s[index]),
            "label": int(dataset.labels[index]),
            "probability": float(probabilities[index]),
            "predicted_excursion": bool(probabilities[index] >= threshold),
            "conformal_prediction_set": "|".join(
                str(value) for value in prediction_sets[index]
            ),
            "first_excursion_timestamp_s": (
                ""
                if not np.isfinite(dataset.first_excursion_timestamps_s[index])
                else float(dataset.first_excursion_timestamps_s[index])
            ),
            "latency_s": float(latencies[index]),
        }
        for index in range(len(dataset.labels))
    ]


def grouped_bootstrap_intervals(
    dataset: WarningDataset,
    probabilities: np.ndarray,
    prediction_sets: Sequence[Sequence[int]],
    latencies: np.ndarray,
    config: EarlyWarningConfig,
) -> dict[str, dict[str, float] | None]:
    groups = sorted(set(dataset.run_ids))
    indices_by_group = {
        group: np.asarray(
            [index for index, run_id in enumerate(dataset.run_ids) if run_id == group],
            dtype=int,
        )
        for group in groups
    }
    rng = np.random.default_rng(config.evaluation.grouped_bootstrap_seed)
    metric_names = (
        "pr_auc",
        "precision",
        "recall",
        "brier_score",
        "conformal_coverage",
        "false_alarms_per_simulated_hour",
        "event_recall",
        "median_warning_lead_time_s",
    )
    draws: dict[str, list[float]] = {name: [] for name in metric_names}
    for _ in range(config.evaluation.grouped_bootstrap_repetitions):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        selected_indices: list[int] = []
        bootstrap_run_ids: list[str] = []
        for copy_index, group in enumerate(sampled):
            group_indices = indices_by_group[str(group)]
            selected_indices.extend(int(index) for index in group_indices)
            bootstrap_run_ids.extend(
                f"bootstrap-{copy_index}:{group}" for _ in range(len(group_indices))
            )
        selection = np.asarray(selected_indices, dtype=int)
        bootstrap = WarningDataset(
            feature_names=dataset.feature_names,
            features=dataset.features[selection],
            labels=dataset.labels[selection],
            run_ids=tuple(bootstrap_run_ids),
            split_ids=tuple("BOOTSTRAP" for _ in selection),
            decision_step_indices=dataset.decision_step_indices[selection],
            decision_timestamps_s=dataset.decision_timestamps_s[selection],
            first_excursion_timestamps_s=dataset.first_excursion_timestamps_s[selection],
        )
        metrics = evaluate_predictions(
            bootstrap,
            probabilities[selection],
            tuple(prediction_sets[index] for index in selection),
            probability_threshold=config.models.probability_threshold,
            horizon_s=config.target.horizon_s,
            decision_period_s=config.target.decision_period_s,
            calibration_bins=config.evaluation.calibration_bins,
            latency_s=latencies[selection],
        )
        for name in metric_names:
            value = metrics[name]
            if value is not None and math.isfinite(float(value)):
                draws[name].append(float(value))
    intervals: dict[str, dict[str, float] | None] = {}
    for name, values in draws.items():
        if values:
            intervals[name] = {
                "median": float(np.median(values)),
                "lower_95": float(np.quantile(values, 0.025)),
                "upper_95": float(np.quantile(values, 0.975)),
                "valid_repetitions": len(values),
            }
        else:
            intervals[name] = None
    return intervals


def useful_gate(
    metrics: dict[str, float | int | None],
    config: EarlyWarningConfig,
) -> dict[str, bool]:
    prevalence = float(metrics["prevalence"])
    event_recall = metrics["event_recall"]
    lead_time = metrics["median_warning_lead_time_s"]
    checks = {
        "pr_auc_margin": (
            float(metrics["pr_auc"])
            >= prevalence + config.evaluation.useful_pr_auc_margin_over_prevalence
        ),
        "event_recall": (
            event_recall is not None
            and float(event_recall) >= config.evaluation.useful_minimum_event_recall
        ),
        "warning_lead_time": (
            lead_time is not None
            and float(lead_time)
            >= config.evaluation.useful_minimum_median_lead_time_s
        ),
        "conformal_coverage": (
            float(metrics["conformal_coverage"])
            >= config.evaluation.useful_minimum_conformal_coverage
        ),
    }
    checks["all_pass"] = all(checks.values())
    return checks


def target_sensitivity_configs(config: EarlyWarningConfig) -> list[tuple[str, TargetConfig]]:
    variants: list[tuple[str, TargetConfig]] = []
    for deviation in config.evaluation.target_sensitivities.relative_deviation_fractions:
        variants.append(
            (
                f"deviation_{deviation:.4f}",
                config.target.model_copy(
                    update={
                        "lower_relative_fraction": 1.0 - deviation,
                        "upper_relative_fraction": 1.0 + deviation,
                    }
                ),
            )
        )
    for horizon in config.evaluation.target_sensitivities.horizon_s:
        variants.append(
            (f"horizon_{horizon:.2f}s", config.target.model_copy(update={"horizon_s": horizon}))
        )
    for persistence in config.evaluation.target_sensitivities.persistence_s:
        variants.append(
            (
                f"persistence_{persistence:.2f}s",
                config.target.model_copy(update={"persistence_s": persistence}),
            )
        )
    return variants


def plot_model_comparison(model_results: dict[str, dict[str, object]]) -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    names = list(model_results)
    metrics = ("pr_auc", "event_recall", "conformal_coverage")
    x = np.arange(len(names))
    width = 0.24
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    for offset, metric in enumerate(metrics):
        values = [
            0.0
            if model_results[name]["primary_test_metrics"][metric] is None
            else float(model_results[name]["primary_test_metrics"][metric])
            for name in names
        ]
        ax.bar(x + (offset - 1) * width, values, width=width, label=metric.replace("_", " "))
    ax.set_xticks(x, names)
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Held-out synthetic metric")
    ax.set_title("WP12 primary held-out early-warning comparison")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    output = FIGURE_DIR / "wp12_model_comparison.png"
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


def plot_warning_timeline(
    dataset: WarningDataset,
    probabilities_by_model: dict[str, np.ndarray],
) -> Path:
    positive_groups = sorted(
        {
            run_id
            for run_id, onset in zip(
                dataset.run_ids,
                dataset.first_excursion_timestamps_s,
                strict=True,
            )
            if np.isfinite(onset)
        }
    )
    if not positive_groups:
        raise ValueError("cannot plot warning timeline without a positive test run")
    run_id = positive_groups[len(positive_groups) // 2]
    indices = np.asarray(
        [index for index, value in enumerate(dataset.run_ids) if value == run_id], dtype=int
    )
    order = indices[np.argsort(dataset.decision_timestamps_s[indices])]
    onset = float(
        np.min(
            dataset.first_excursion_timestamps_s[order][
                np.isfinite(dataset.first_excursion_timestamps_s[order])
            ]
        )
    )
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    for model_name, probabilities in probabilities_by_model.items():
        if len(probabilities) != len(dataset.labels):
            raise ValueError(f"timeline probabilities misalign for {model_name}")
        ax.plot(
            dataset.decision_timestamps_s[order],
            probabilities[order],
            lw=1.8,
            label=f"{model_name} probability",
        )
    ax.axhline(0.5, color="#666666", ls="--", label="alarm threshold")
    ax.axvline(onset, color="#c9362b", ls="--", label="true synthetic excursion onset")
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Decision time (s)")
    ax.set_ylabel("Excursion probability")
    ax.set_title(f"Held-out warning timeline: {run_id}")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    output = FIGURE_DIR / "wp12_warning_timeline.png"
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


def main() -> int:
    started = time.perf_counter()
    config = load_early_warning_config(CONFIG_PATH)
    runtime = load_runtime_config(RUNTIME_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    primary_runner = chain_runner(config, UtilityCmpTopology.DRESSING_WATER_SUPPORT)
    null_runner = chain_runner(config, UtilityCmpTopology.NO_CONNECTION)
    reference_scenario = ChainScenario(
        run_id="wp12-reference",
        family=ChainEventKind.NORMAL,
        seed=11000,
        event_start_s=0.0,
        event_duration_s=0.0,
    )
    print("simulating paired event-disabled reference", flush=True)
    reference_trace = primary_runner.run(reference_scenario)

    traces_by_split: dict[str, list[tuple[ChainScenario, ChainTrace]]] = {}
    for split in ("TRAIN", "CALIBRATION", "CONFORMAL_CALIBRATION", "TEST"):
        entries: list[tuple[ChainScenario, ChainTrace]] = []
        scenarios = scenarios_for_split(config, split)
        for index, scenario in enumerate(scenarios, 1):
            if index == 1 or index % 6 == 0 or index == len(scenarios):
                print(f"simulating {split} {index}/{len(scenarios)}", flush=True)
            entries.append((scenario, primary_runner.run(scenario)))
        traces_by_split[split] = entries

    unseen_entries: list[tuple[ChainScenario, ChainTrace]] = []
    for scenario in unseen_compound_scenarios(config):
        unseen_entries.append((scenario, primary_runner.run(scenario)))
    traces_by_split["UNSEEN_COMPOUND"] = unseen_entries
    null_entries: list[tuple[ChainScenario, ChainTrace]] = []
    for scenario in structural_null_scenarios(config):
        null_entries.append((scenario, null_runner.run(scenario)))
    traces_by_split["STRUCTURAL_NULL"] = null_entries

    replay_scenario = traces_by_split["TEST"][0][0]
    replay_trace = primary_runner.run(replay_scenario)
    replay_matches = replay_trace == traces_by_split["TEST"][0][1]
    if not replay_matches:
        raise ValueError("fixed-seed WP12 chain replay is not deterministic")

    print("building causal feature/label dataset", flush=True)
    dataset, dataset_manifest = build_dataset(config, traces_by_split, reference_trace)
    for split in ("TRAIN", "CALIBRATION", "CONFORMAL_CALIBRATION", "TEST"):
        split_dataset = dataset.subset(split)
        if len(np.unique(split_dataset.labels)) != 2:
            raise ValueError(f"{split} lacks both primary target classes")
    dataset_path = OUTPUT_DIR / "wp12_dataset.csv"
    write_csv_atomic(dataset_path, dataset_csv_rows(dataset))
    dataset_manifest.update(
        {
            "manifest_id": "WP12_SYNTHETIC_EARLY_WARNING_DATASET_V1_4",
            "evidence_plane": "SYNTHETIC_SIMULATOR",
            "dataset_csv": str(dataset_path.relative_to(ROOT)),
            "dataset_csv_sha256": sha256_file(dataset_path),
            "config_path": str(CONFIG_PATH.relative_to(ROOT)),
            "config_sha256": sha256_file(CONFIG_PATH),
            "runtime_config_sha256": runtime_config_sha256(runtime),
            "reference_trace_sha256": canonical_sha256(reference_trace.truth_rows),
            "deterministic_replay": replay_matches,
        }
    )
    write_json_atomic(OUTPUT_DIR / "wp12_dataset_manifest.json", dataset_manifest)

    model_results: dict[str, dict[str, object]] = {}
    prediction_rows: list[dict[str, object]] = []
    fitted_predictors: dict[str, EarlyWarningPredictor] = {}
    prediction_cache: dict[tuple[str, str], tuple[np.ndarray, tuple[tuple[int, ...], ...], np.ndarray]] = {}
    for model_kind in ModelKind:
        print(f"fitting {model_kind.value}", flush=True)
        predictor = EarlyWarningPredictor(model_kind, config.features, config.models).fit(dataset)
        artifact_path = MODEL_DIR / f"{model_kind.value.lower()}.pkl"
        predictor.save(artifact_path)
        restored = EarlyWarningPredictor.load(artifact_path)
        fitted_predictors[model_kind.value] = predictor
        split_metrics: dict[str, object] = {}
        for split in ("TEST", "UNSEEN_COMPOUND", "STRUCTURAL_NULL"):
            split_dataset = dataset.subset(split)
            probabilities, sets, latencies = predictor.predict_features(split_dataset.features)
            restored_probabilities = restored.predict_features(split_dataset.features)[0]
            if not np.array_equal(probabilities, restored_probabilities):
                raise ValueError("saved/restored warning predictions differ")
            metrics = evaluate_predictions(
                split_dataset,
                probabilities,
                sets,
                probability_threshold=config.models.probability_threshold,
                horizon_s=config.target.horizon_s,
                decision_period_s=config.target.decision_period_s,
                calibration_bins=config.evaluation.calibration_bins,
                latency_s=latencies,
            )
            split_metrics[split] = metrics
            prediction_cache[(model_kind.value, split)] = (probabilities, sets, latencies)
            prediction_rows.extend(
                prediction_csv_rows(
                    split_dataset,
                    model_kind,
                    probabilities,
                    sets,
                    latencies,
                    config.models.probability_threshold,
                )
            )
        primary_test = dataset.subset("TEST")
        primary_probabilities, primary_sets, primary_latencies = prediction_cache[
            (model_kind.value, "TEST")
        ]
        bootstrap = grouped_bootstrap_intervals(
            primary_test,
            primary_probabilities,
            primary_sets,
            primary_latencies,
            config,
        )
        model_results[model_kind.value] = {
            "artifact_path": str(artifact_path.relative_to(ROOT)),
            "artifact_sha256": sha256_file(artifact_path),
            "metadata_sha256": sha256_file(
                artifact_path.with_suffix(artifact_path.suffix + ".json")
            ),
            "fit_group_sha256": predictor.fit_group_sha256,
            "training_prevalence": predictor.training_prevalence,
            "conformal_quantile": predictor.conformal_quantile,
            "primary_test_metrics": split_metrics["TEST"],
            "unseen_compound_metrics": split_metrics["UNSEEN_COMPOUND"],
            "structural_null_metrics": split_metrics["STRUCTURAL_NULL"],
            "grouped_bootstrap_95_intervals": bootstrap,
            "useful_warning_gate": useful_gate(split_metrics["TEST"], config),
        }

    predictions_path = OUTPUT_DIR / "wp12_predictions.csv"
    write_csv_atomic(predictions_path, prediction_rows)
    probability_payload = [
        {
            key: row[key]
            for key in (
                "model_kind",
                "run_id",
                "split_id",
                "decision_step_index",
                "label",
                "probability",
                "predicted_excursion",
            )
        }
        for row in prediction_rows
    ]
    probability_payload_sha256 = canonical_sha256(probability_payload)
    if probability_payload_sha256 != EXPECTED_REVISION_1_1_PROBABILITY_SHA256:
        raise ValueError(
            "frozen pre-amendment probability payload changed: "
            f"{probability_payload_sha256}"
        )

    learned_names = (ModelKind.LOGISTIC.value, ModelKind.GRADIENT_BOOSTED.value)
    best_model_name = max(
        learned_names,
        key=lambda name: float(model_results[name]["primary_test_metrics"]["pr_auc"]),
    )
    sensitivity_results: dict[str, object] = {}
    for name, target in target_sensitivity_configs(config):
        sensitivity_dataset, sensitivity_manifest = build_dataset(
            config,
            traces_by_split,
            reference_trace,
            target_config=target,
        )
        sensitivity_test = sensitivity_dataset.subset("TEST")
        sensitivity_model_metrics: dict[str, object] = {}
        for model_name, predictor in fitted_predictors.items():
            probabilities, sets, latencies = predictor.predict_features(
                sensitivity_test.features
            )
            sensitivity_model_metrics[model_name] = evaluate_predictions(
                sensitivity_test,
                probabilities,
                sets,
                probability_threshold=config.models.probability_threshold,
                horizon_s=target.horizon_s,
                decision_period_s=target.decision_period_s,
                calibration_bins=config.evaluation.calibration_bins,
                latency_s=latencies,
            )
        sensitivity_results[name] = {
            "target": target.model_dump(mode="json"),
            "test_rows": len(sensitivity_test.labels),
            "test_positive_rows": int(np.sum(sensitivity_test.labels)),
            "censor_counts": sensitivity_manifest["split_censor_counts"]["TEST"],
            "metric_domain_note": (
                "PR-AUC is undefined because the held-out sensitivity target "
                "contains one class; negative-only diagnostics remain valid."
                if len(np.unique(sensitivity_test.labels)) < 2
                else None
            ),
            "model_metrics": sensitivity_model_metrics,
        }

    observation_robustness: dict[str, object] = {}
    representative_test = observation_robustness_scenarios(
        config,
        [scenario for scenario, _ in traces_by_split["TEST"]],
    )
    for case_index, case in enumerate(("HIGH_NOISE", "HIGH_DELAY", "HIGH_DROPOUT"), 1):
        robust_runner = chain_runner(
            config,
            UtilityCmpTopology.DRESSING_WATER_SUPPORT,
            robustness=case,
        )
        robust_entries: list[tuple[ChainScenario, ChainTrace]] = []
        for scenario in representative_test:
            robust_scenario = replace(
                scenario,
                run_id=f"{scenario.run_id}-{case.lower()}",
                seed=scenario.seed + case_index * 100_000,
            )
            robust_entries.append((robust_scenario, robust_runner.run(robust_scenario)))
        robust_split = f"ROBUSTNESS_{case}"
        robust_dataset, robust_manifest = build_dataset(
            config,
            {robust_split: robust_entries},
            reference_trace,
        )
        robust_subset = robust_dataset.subset(robust_split)
        if len(np.unique(robust_subset.labels)) != 2:
            raise ValueError(
                f"{case} robustness completion lacks both primary target classes"
            )
        robust_model_metrics: dict[str, object] = {}
        for model_name, predictor in fitted_predictors.items():
            probabilities, sets, latencies = predictor.predict_features(
                robust_subset.features
            )
            robust_model_metrics[model_name] = evaluate_predictions(
                robust_subset,
                probabilities,
                sets,
                probability_threshold=config.models.probability_threshold,
                horizon_s=config.target.horizon_s,
                decision_period_s=config.target.decision_period_s,
                calibration_bins=config.evaluation.calibration_bins,
                latency_s=latencies,
            )
        observation_robustness[case] = {
            "scenario_count": len(robust_entries),
            "family_positions": list(
                config.evaluation.observation_robustness_family_positions
            ),
            "row_count": len(robust_subset.labels),
            "positive_count": int(np.sum(robust_subset.labels)),
            "censor_counts": robust_manifest["split_censor_counts"][robust_split],
            "class_support": "BOTH_CLASSES_REQUIRED",
            "model_metrics": robust_model_metrics,
        }

    comparison_figure = plot_model_comparison(model_results)
    test_dataset = dataset.subset("TEST")
    timeline_probabilities = {
        model_kind.value: prediction_cache[(model_kind.value, "TEST")][0]
        for model_kind in ModelKind
    }
    timeline_figure = plot_warning_timeline(
        test_dataset,
        timeline_probabilities,
    )
    complete_seconds = time.perf_counter() - started
    report = {
        "report_id": "WP12_SYNTHETIC_EARLY_WARNING_VALIDATION_V1_4",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "claim_boundary": (
            "Held-out synthetic configured-envelope prediction only; no public-data, "
            "real-fab, defect, yield, controller, equipment, or production claim."
        ),
        "configuration": {
            "path": str(CONFIG_PATH.relative_to(ROOT)),
            "sha256": sha256_file(CONFIG_PATH),
            "runtime_sha256": runtime_config_sha256(runtime),
            "experiment_revision": config.experiment_revision,
            "target": config.target.model_dump(mode="json"),
            "features": config.features.model_dump(mode="json"),
            "splits": config.splits.model_dump(mode="json"),
        },
        "dataset_manifest_path": "reports/early_warning/wp12_dataset_manifest.json",
        "dataset_manifest_sha256": sha256_file(
            OUTPUT_DIR / "wp12_dataset_manifest.json"
        ),
        "predictions_path": str(predictions_path.relative_to(ROOT)),
        "predictions_sha256": sha256_file(predictions_path),
        "probability_payload_sha256": probability_payload_sha256,
        "latency_measurement_mode": (
            "AMORTIZED_VECTORIZED_OFFLINE_INFERENCE; not streaming controller latency"
        ),
        "deterministic_replay": replay_matches,
        "model_results": model_results,
        "descriptive_model_comparison": {
            "best_learned_model_by_test_pr_auc": best_model_name,
            "used_for_downstream_selection": False,
        },
        "target_sensitivity": sensitivity_results,
        "observation_robustness": observation_robustness,
        "figures": {
            str(comparison_figure.relative_to(ROOT)): sha256_file(comparison_figure),
            str(timeline_figure.relative_to(ROOT)): sha256_file(timeline_figure),
        },
        "elapsed_s": complete_seconds,
        "checks": {
            "train_sigmoid_conformal_test_groups_disjoint": True,
            "future_or_latent_feature_count_zero": True,
            "all_fit_role_splits_have_both_classes": True,
            "primary_test_has_both_classes": True,
            "pre_amendment_probability_payload_reproduced": (
                probability_payload_sha256
                == EXPECTED_REVISION_1_1_PROBABILITY_SHA256
            ),
            "model_save_load_exact": True,
            "fixed_seed_replay_exact": replay_matches,
            "historical_runtime_hash_preserved": (
                runtime_config_sha256(runtime)
                == "b2b07edbaad458f6f66cf26ce88ffc5deef656a33701a7cccd8da94104d7383f"
            ),
            "at_least_one_learned_model_passes_useful_gate": any(
                bool(model_results[name]["useful_warning_gate"]["all_pass"])
                for name in learned_names
            ),
        },
    }
    write_json_atomic(OUTPUT_DIR / "wp12_validation.json", report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
