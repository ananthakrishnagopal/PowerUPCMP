#!/usr/bin/env python3
"""Train a compact dashboard warning classifier for live demo scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from semifab_poc.config import load_runtime_config
from semifab_poc.models.early_warning import (
    EarlyWarningPredictor,
    ModelKind,
    WarningDataset,
    WarningObservationWindow,
    evaluate_predictions,
    load_early_warning_config,
    normalization_for_warning_runtime,
)
from semifab_poc.simulation.chain import (
    ChainEventKind,
    ChainScenario,
    ChainSchedule,
    SyntheticChainRunner,
)
from semifab_poc.simulation.coupling import UtilityCmpTopology
from semifab_poc.simulation.sensors import SensorConfig


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "models" / "early_warning.yaml"
RUNTIME_PATH = ROOT / "configs" / "default.yaml"
ARTIFACT_PATH = ROOT / "reports" / "early_warning" / "models" / "dashboard_warning.pkl"
METRICS_PATH = ROOT / "reports" / "early_warning" / "dashboard_warning_metrics.json"

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


def progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def sensor_configs(config) -> tuple[SensorConfig, ...]:
    sensors = []
    for index, signal_id in enumerate(config.features.allowed_signal_ids):
        minimum, maximum = LIMITS[signal_id]
        sensors.append(
            SensorConfig(
                sensor_id=f"dashboard-warning-{index}",
                signal_id=signal_id,
                unit=UNITS[signal_id],
                sample_period_s=config.sensors.sample_period_s,
                delay_s=config.sensors.delay_s,
                noise_std=config.sensors.noise_by_signal[signal_id],
                packet_loss_probability=config.sensors.packet_loss_probability,
                timestamp_jitter_std_s=config.sensors.timestamp_jitter_std_s,
                minimum_value=minimum,
                maximum_value=maximum,
            )
        )
    return tuple(sensors)


def runner(config):
    runtime = load_runtime_config(RUNTIME_PATH)
    runtime = runtime.model_copy(update={"duration_s": config.simulation.duration_s})
    coupling = replace(
        runtime.coupling,
        topology=UtilityCmpTopology.SYNTHETIC_SLURRY_SUPPORT,
        link_strength=1.0,
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
        sensor_configs(config),
    )


def scenarios(split: str, seed_start: int, count: int) -> list[ChainScenario]:
    families = (
        ChainEventKind.NORMAL,
        ChainEventKind.PUMP_TRIP,
        ChainEventKind.GRID_INTERRUPTION,
        ChainEventKind.VALVE_RESTRICTION,
    )
    result = []
    for family_index, family in enumerate(families):
        for index in range(count):
            seed = seed_start + family_index * 1_000 + index
            rng = np.random.default_rng(seed)
            start_s = float(rng.uniform(6.2, 10.5))
            duration_s = float(rng.uniform(1.5, 4.0))
            if family is ChainEventKind.NORMAL:
                start_s = 7.0
                duration_s = 0.0
            kwargs = {
                "run_id": f"dashboard-{split.lower()}-{family.value.lower()}-{index:03d}",
                "family": family,
                "seed": seed,
                "event_start_s": start_s,
                "event_duration_s": min(duration_s, 15.5 - start_s),
            }
            if family is ChainEventKind.GRID_INTERRUPTION:
                severity = index / max(1, count - 1)
                kwargs["battery_capacity_j"] = float(500.0 + 2_000.0 * (1.0 - severity))
                kwargs["ups_load_power_w"] = float(2_300.0 + 400.0 * severity)
            elif family is ChainEventKind.VALVE_RESTRICTION:
                severity = index / max(1, count - 1)
                kwargs["valve_position"] = float(0.10 + 0.45 * (1.0 - severity))
            result.append(ChainScenario(**kwargs))
    return result


def build_dataset(
    config,
    *,
    train_count: int,
    calibration_count: int,
    conformal_count: int,
    test_count: int,
    decision_period_s: float,
) -> WarningDataset:
    chain = runner(config)
    runtime = chain.runtime
    extractor = EarlyWarningPredictor(
        ModelKind.PREVALENCE,
        config.features,
        config.models,
    ).extractor
    split_specs = {
        "TRAIN": (160_000, train_count),
        "CALIBRATION": (170_000, calibration_count),
        "CONFORMAL_CALIBRATION": (180_000, conformal_count),
        "TEST": (190_000, test_count),
    }
    feature_names = None
    features = []
    labels = []
    run_ids = []
    split_ids = []
    decision_steps = []
    decision_times = []
    first_onsets = []
    stride = round(decision_period_s / config.simulation.dt_s)
    horizon_steps = round(2.0 / config.simulation.dt_s)
    min_decision_time_s = config.simulation.polish_start_s - 1.0

    for split, (seed_start, count) in split_specs.items():
        split_scenarios = scenarios(split, seed_start, count)
        progress(f"[dataset] {split}: {len(split_scenarios)} scenarios")
        for scenario_index, scenario in enumerate(split_scenarios, start=1):
            progress(
                "[trace] "
                f"{split} {scenario_index}/{len(split_scenarios)} "
                f"{scenario.family.value} start={scenario.event_start_s:.2f}s "
                f"duration={scenario.event_duration_s:.2f}s"
            )
            trace = chain.run(scenario)
            rows = trace.truth_rows
            row_by_step = {int(row["step_index"]): row for row in rows}
            event_risk = np.asarray(
                [
                    int(
                        row["timestamp_s"] >= min_decision_time_s
                        and (
                            float(row["effective_availability"]) < 0.90
                            or (
                                row["cmp_mode"] == "POLISH"
                                and float(row["cmp_mrr_m_s"]) < 0.70e-9
                            )
                        )
                    )
                    for row in rows
                ],
                dtype=int,
            )
            for row_index in range(stride - 1, len(rows), stride):
                truth_row = rows[row_index]
                decision_time = float(truth_row["timestamp_s"])
                if decision_time < min_decision_time_s:
                    continue
                future = event_risk[row_index : min(len(rows), row_index + horizon_steps + 1)]
                label = int(np.any(future))
                if label:
                    onset_index = row_index + int(np.argmax(future))
                    first_onset = float(rows[onset_index]["timestamp_s"])
                else:
                    first_onset = np.nan
                available = tuple(
                    obs
                    for obs in trace.observations
                    if obs.arrival_timestamp_s <= decision_time + 1.0e-12
                )
                window = WarningObservationWindow(
                    run_id=scenario.run_id,
                    decision_step_index=int(truth_row["step_index"]),
                    decision_timestamp_s=decision_time,
                    observations=available,
                    process_mode=str(truth_row["cmp_mode"]),
                    polish_start_s=config.simulation.polish_start_s,
                    normalization_by_signal=normalization_for_warning_runtime(
                        scenario_battery_capacity_j=scenario.battery_capacity_j,
                        runtime=runtime,
                    ),
                    sensor_sample_period_s=config.sensors.sample_period_s,
                    battery_capacity_ratio=scenario.battery_capacity_j
                    / runtime.electrical.battery_capacity_j,
                    ups_load_ratio=scenario.ups_load_power_w
                    / runtime.electrical.ups_rated_power_w,
                )
                vector = extractor.transform(window)
                if feature_names is None:
                    feature_names = vector.names
                elif vector.names != feature_names:
                    raise RuntimeError("feature schema changed across generated rows")
                features.append(vector.values)
                labels.append(label)
                run_ids.append(scenario.run_id)
                split_ids.append(split)
                decision_steps.append(int(truth_row["step_index"]))
                decision_times.append(decision_time)
                first_onsets.append(first_onset)
        progress(f"[dataset] {split}: accumulated rows={len(labels)}")

    if feature_names is None:
        raise RuntimeError("no feature rows generated")
    return WarningDataset(
        feature_names=feature_names,
        features=np.vstack(features),
        labels=np.asarray(labels, dtype=int),
        run_ids=tuple(run_ids),
        split_ids=tuple(split_ids),
        decision_step_indices=np.asarray(decision_steps, dtype=int),
        decision_timestamps_s=np.asarray(decision_times, dtype=float),
        first_excursion_timestamps_s=np.asarray(first_onsets, dtype=float),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-count", type=int, default=8)
    parser.add_argument("--calibration-count", type=int, default=4)
    parser.add_argument("--conformal-count", type=int, default=4)
    parser.add_argument("--test-count", type=int, default=4)
    parser.add_argument("--decision-period-s", type=float, default=0.20)
    args = parser.parse_args()

    progress("[config] loading dashboard warning configuration")
    config = load_early_warning_config(CONFIG_PATH)
    progress("[dataset] generating synthetic traces and feature rows")
    dataset = build_dataset(
        config,
        train_count=args.train_count,
        calibration_count=args.calibration_count,
        conformal_count=args.conformal_count,
        test_count=args.test_count,
        decision_period_s=args.decision_period_s,
    )
    progress(
        "[dataset] complete "
        f"rows={len(dataset.labels)} "
        f"positive_fraction={float(np.mean(dataset.labels)):.3f}"
    )
    progress("[fit] fitting gradient-boosted dashboard warning classifier")
    predictor = EarlyWarningPredictor(
        ModelKind.GRADIENT_BOOSTED,
        config.features,
        config.models,
    ).fit(dataset)
    progress(f"[artifact] writing {ARTIFACT_PATH.relative_to(ROOT)}")
    predictor.save(ARTIFACT_PATH)

    progress("[eval] evaluating TEST split")
    test = dataset.subset("TEST")
    probabilities, sets, latency = predictor.predict_features(test.features)
    metrics = evaluate_predictions(
        test.labels,
        probabilities,
        sets,
        test.decision_timestamps_s,
        test.first_excursion_timestamps_s,
        bins=config.evaluation.calibration_bins,
    )
    summary = {
        "artifact": str(ARTIFACT_PATH.relative_to(ROOT)),
        "rows": int(len(dataset.labels)),
        "positive_fraction": float(np.mean(dataset.labels)),
        "test_metrics": metrics,
        "latency_mean_s": float(np.mean(latency)),
    }
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    progress(f"[metrics] wrote {METRICS_PATH.relative_to(ROOT)}")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
