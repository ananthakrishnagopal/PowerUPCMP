#!/usr/bin/env python3
"""Prepare and one-shot evaluate the frozen WP13 synthetic attribution study."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from semifab_poc.config import load_runtime_config
from semifab_poc.data.schema import RootCause
from semifab_poc.models.attribution import (
    ALL_CAUSES,
    MODEL_CAUSES,
    PRIMARY_INITIATING_CAUSES,
    AttributionConfig,
    AttributionDataset,
    AttributionFeatureExtractor,
    AttributionMethod,
    AttributionObservationWindow,
    RootCauseEstimator,
    load_attribution_config,
)
from semifab_poc.models.early_warning import Prediction
from semifab_poc.simulation.chain import (
    ChainEventKind,
    ChainScenario,
    ChainSchedule,
    SyntheticChainRunner,
)
from semifab_poc.simulation.coupling import UtilityCmpTopology
from semifab_poc.simulation.sensors import SensorConfig


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "models" / "attribution.yaml"
RUNTIME_PATH = ROOT / "configs" / "default.yaml"
OUTPUT_DIR = ROOT / "reports" / "attribution"
MODEL_DIR = OUTPUT_DIR / "models"
FIGURE_DIR = OUTPUT_DIR / "figures"
MANIFEST_PATH = OUTPUT_DIR / "wp13_preholdout_manifest.json"
CALIBRATION_PATH = OUTPUT_DIR / "wp13_calibration_report.json"
OPENING_MARKER_PATH = OUTPUT_DIR / "wp13_holdout_opening.json"
RESULTS_PATH = OUTPUT_DIR / "wp13_validation.json"
PREDICTIONS_PATH = OUTPUT_DIR / "wp13_predictions.csv"

METHODS = (
    AttributionMethod.ALWAYS_UNKNOWN,
    AttributionMethod.RULE_ONLY,
    AttributionMethod.LOGISTIC,
    AttributionMethod.HYBRID,
)
FOCUSED_TEST_PATHS = (
    "tests/unit/test_attribution.py",
    "tests/unit/test_wp13_scenario_ensemble.py",
    "tests/integration/test_warning_chain.py",
    "tests/unit/test_wp12_scenario_ensemble.py",
)

UNITS = {
    "electrical.grid_voltage": "pu",
    "electrical.grid_frequency": "Hz",
    "electrical.ups_output_voltage": "pu",
    "electrical.ups_output_frequency": "Hz",
    "electrical.ups_battery_energy": "J",
    "drive.vfd_available_output": "pu",
    "drive.vfd_trip_state": "1",
    "drive.motor_angular_speed": "rad/s",
    "pump.volumetric_flow": "m^3/s",
    "upw.supply_pressure": "Pa",
    "upw.tool_flow": "m^3/s",
    "upw.valve_position": "1",
    "upw.tool_demand": "m^3/s",
    "upw.temperature": "K",
}

LIMITS: dict[str, tuple[float | None, float | None]] = {
    "electrical.grid_voltage": (0.0, 1.5),
    "electrical.grid_frequency": (0.0, 100.0),
    "electrical.ups_output_voltage": (0.0, 1.5),
    "electrical.ups_output_frequency": (0.0, 100.0),
    "electrical.ups_battery_energy": (0.0, None),
    "drive.vfd_available_output": (0.0, 1.0),
    "drive.vfd_trip_state": (None, None),
    "drive.motor_angular_speed": (0.0, None),
    "pump.volumetric_flow": (0.0, 5.0e-4),
    "upw.supply_pressure": (0.0, 600_000.0),
    "upw.tool_flow": (0.0, 5.0e-4),
    "upw.valve_position": (0.0, 1.0),
    "upw.tool_demand": (0.0, 5.0e-4),
    "upw.temperature": (273.15, 373.15),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv_atomic(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty attribution CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _git(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"git precondition failed for {' '.join(arguments)}: {message}")
    return completed


def model_path(method: AttributionMethod) -> Path:
    return MODEL_DIR / f"{method.value.lower()}.pkl"


def required_committed_paths() -> tuple[str, ...]:
    paths = [
        "configs/models/attribution.yaml",
        "orchestration/decisions/wp13_root_cause_attribution.md",
        "orchestration/failures/20260713T141046+0530_wp13_wp12_result_key.md",
        "reports/attribution/wp13_calibration_report.json",
        "reports/attribution/wp13_preholdout_manifest.json",
        "scripts/validate_wp13_attribution.py",
        "src/semifab_poc/models/attribution.py",
        "src/semifab_poc/simulation/chain.py",
        "tests/unit/test_attribution.py",
    ]
    for method in METHODS:
        relative = model_path(method).relative_to(ROOT).as_posix()
        paths.extend((relative, f"{relative}.sha256"))
    return tuple(paths)


def require_clean_committed_checkpoint() -> dict[str, Any]:
    status = _git(["status", "--porcelain=v1", "--untracked-files=all"])
    if status.stdout.strip():
        raise ValueError("WP13 holdout opening requires a completely clean Git worktree")
    head = _git(["rev-parse", "HEAD"]).stdout.strip()
    hashes: dict[str, str] = {}
    for relative_path in required_committed_paths():
        _git(["ls-files", "--error-unmatch", "--", relative_path])
        _git(["cat-file", "-e", f"{head}:{relative_path}"])
        hashes[relative_path] = sha256_file(ROOT / relative_path)
    return {
        "git_head": head,
        "git_worktree_clean": True,
        "required_committed_path_sha256": hashes,
    }


def run_focused_tests() -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        *FOCUSED_TEST_PATHS,
        "-W",
        "error",
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise ValueError("WP13 focused preflight tests did not pass")
    return {
        "passed": True,
        "warning_policy": "ERROR",
        "pytest_cache_provider_disabled": True,
        "test_paths": list(FOCUSED_TEST_PATHS),
        "test_path_sha256": {
            path: sha256_file(ROOT / path) for path in FOCUSED_TEST_PATHS
        },
    }


def sensor_configs(
    config: AttributionConfig,
    robustness: str = "PRIMARY",
) -> tuple[SensorConfig, ...]:
    if robustness == "PRIMARY" or robustness == "PARAMETER_MISMATCH":
        noise_scale = 1.0
        delay_s = config.sensors.delay_s
        loss = config.sensors.packet_loss_probability
    elif robustness == "HIGH_NOISE":
        noise_scale = config.robustness.noise_scale
        delay_s = config.sensors.delay_s
        loss = config.sensors.packet_loss_probability
    elif robustness == "HIGH_DELAY":
        noise_scale = 1.0
        delay_s = config.robustness.delay_s
        loss = config.sensors.packet_loss_probability
    elif robustness == "HIGH_DROPOUT":
        noise_scale = 1.0
        delay_s = config.sensors.delay_s
        loss = config.robustness.packet_loss_probability
    else:
        raise ValueError(f"unknown attribution robustness case: {robustness}")
    sensors: list[SensorConfig] = []
    for index, signal_id in enumerate(config.features.allowed_signal_ids):
        minimum, maximum = LIMITS[signal_id]
        base_noise = config.sensors.noise_by_signal[signal_id]
        sensors.append(
            SensorConfig(
                sensor_id=f"attribution-{index:02d}-{signal_id}",
                signal_id=signal_id,
                unit=UNITS[signal_id],
                sample_period_s=config.features.sensor_sample_period_s,
                provenance_id=f"synthetic-attribution-sensor-v1:{robustness}",
                noise_std=base_noise * noise_scale,
                delay_s=delay_s,
                packet_loss_probability=loss,
                timestamp_jitter_std_s=config.sensors.timestamp_jitter_std_s,
                minimum_value=minimum,
                maximum_value=maximum,
            )
        )
    return tuple(sensors)


def chain_runner(
    config: AttributionConfig,
    robustness: str = "PRIMARY",
) -> SyntheticChainRunner:
    runtime = load_runtime_config(RUNTIME_PATH)
    if robustness == "PARAMETER_MISMATCH":
        runtime = runtime.model_copy(
            update={
                "drive": replace(
                    runtime.drive,
                    motor_time_constant_s=1.25 * runtime.drive.motor_time_constant_s,
                    ramp_down_rate_rad_s2=0.80 * runtime.drive.ramp_down_rate_rad_s2,
                )
            }
        )
    coupling = replace(
        runtime.coupling,
        topology=UtilityCmpTopology(config.simulation.topology),
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
        sensor_configs(config, robustness),
    )


def _uniform(rng: np.random.Generator, bounds: tuple[float, float]) -> float:
    return float(rng.uniform(bounds[0], bounds[1]))


def scenario_for_cause(
    cause: RootCause,
    *,
    config: AttributionConfig,
    split: str,
    index: int,
    count: int,
    seed_start: int,
) -> ChainScenario:
    cause_index = MODEL_CAUSES.index(cause)
    ordinal = cause_index * count + index
    seed = seed_start + ordinal
    rng = np.random.default_rng(seed)
    ranges = config.simulation.scenario_ranges
    default: dict[str, Any] = {
        "run_id": f"{split.lower()}-run-{ordinal:04d}",
        "seed": seed,
        "event_start_s": config.simulation.event_start_s,
        "event_duration_s": config.simulation.event_duration_s,
    }
    if cause is RootCause.UNKNOWN:
        normal = {**default, "event_duration_s": 0.0}
        return ChainScenario(
            **normal,
            family=ChainEventKind.NORMAL,
        )
    if cause is RootCause.GRID_VOLTAGE_SAG:
        return ChainScenario(
            **default,
            family=ChainEventKind.GRID_VOLTAGE_SAG,
            grid_voltage_pu=_uniform(rng, ranges.grid_voltage_sag_pu),
        )
    if cause is RootCause.GRID_VOLTAGE_SWELL:
        return ChainScenario(
            **default,
            family=ChainEventKind.GRID_VOLTAGE_SWELL,
            grid_voltage_pu=_uniform(rng, ranges.grid_voltage_swell_pu),
        )
    if cause is RootCause.GRID_INTERRUPTION:
        return ChainScenario(**default, family=ChainEventKind.GRID_INTERRUPTION)
    if cause is RootCause.GRID_FREQUENCY_DEVIATION:
        magnitude = _uniform(rng, ranges.grid_frequency_deviation_abs_hz)
        sign = -1.0 if seed % 2 == 0 else 1.0
        return ChainScenario(
            **default,
            family=ChainEventKind.GRID_FREQUENCY_DEVIATION,
            grid_frequency_hz=50.0 + sign * magnitude,
        )
    if cause is RootCause.PUMP_TRIP:
        return ChainScenario(**default, family=ChainEventKind.PUMP_TRIP)
    if cause is RootCause.VALVE_RESTRICTION:
        return ChainScenario(
            **default,
            family=ChainEventKind.VALVE_RESTRICTION,
            valve_position=_uniform(rng, ranges.valve_position),
        )
    if cause is RootCause.TOOL_DEMAND_SPIKE:
        return ChainScenario(
            **default,
            family=ChainEventKind.TOOL_DEMAND_SPIKE,
            tool_demand_m3_s=_uniform(rng, ranges.tool_demand_m3_s),
        )
    if cause is RootCause.THERMAL_EXCURSION:
        return ChainScenario(
            **default,
            family=ChainEventKind.THERMAL_EXCURSION,
            inlet_temperature_k=_uniform(rng, ranges.inlet_temperature_k),
        )
    if cause is RootCause.PRESSURE_SENSOR_FAULT:
        sign = -1.0 if seed % 2 == 0 else 1.0
        return ChainScenario(
            **default,
            family=ChainEventKind.PRESSURE_SENSOR_FAULT,
            pressure_sensor_bias_pa=sign
            * _uniform(rng, ranges.pressure_sensor_bias_pa),
        )
    if cause is RootCause.FLOW_SENSOR_FAULT:
        sign = -1.0 if seed % 2 == 0 else 1.0
        return ChainScenario(
            **default,
            family=ChainEventKind.FLOW_SENSOR_FAULT,
            flow_sensor_bias_m3_s=sign
            * _uniform(rng, ranges.flow_sensor_bias_m3_s),
        )
    raise ValueError(f"unsupported attribution cause: {cause.value}")


def scenarios_for_split(
    config: AttributionConfig,
    split: str,
    *,
    count: int,
    seed_start: int,
) -> tuple[tuple[ChainScenario, RootCause], ...]:
    return tuple(
        (
            scenario_for_cause(
                cause,
                config=config,
                split=split,
                index=index,
                count=count,
                seed_start=seed_start,
            ),
            cause,
        )
        for cause in MODEL_CAUSES
        for index in range(count)
    )


@dataclass(frozen=True)
class BuiltSplit:
    dataset: AttributionDataset
    windows: tuple[AttributionObservationWindow, ...]
    scenario_manifest: tuple[dict[str, Any], ...]


def _scenario_payload(scenario: ChainScenario, cause: RootCause) -> dict[str, Any]:
    payload = asdict(scenario)
    payload["family"] = scenario.family.value
    payload["offline_initiating_cause"] = cause.value
    return payload


def build_split(
    config: AttributionConfig,
    split: str,
    scenarios: Sequence[tuple[ChainScenario, RootCause]],
    *,
    robustness: str = "PRIMARY",
    decision_offsets_s: Sequence[float] | None = None,
    truth_override: RootCause | None = None,
) -> BuiltSplit:
    runner = chain_runner(config, robustness)
    extractor = AttributionFeatureExtractor(config.features, config.residuals)
    offsets = tuple(decision_offsets_s or config.simulation.decision_offsets_s)
    names: tuple[str, ...] | None = None
    feature_rows: list[np.ndarray] = []
    labels: list[RootCause] = []
    run_ids: list[str] = []
    split_ids: list[str] = []
    steps: list[int] = []
    timestamps: list[float] = []
    windows: list[AttributionObservationWindow] = []
    manifest: list[dict[str, Any]] = []
    for scenario, cause in scenarios:
        trace = runner.run(scenario)
        manifest.append(_scenario_payload(scenario, cause))
        for offset in offsets:
            decision_timestamp_s = config.simulation.event_start_s + float(offset)
            decision_step_index = round(decision_timestamp_s / config.simulation.dt_s)
            visible = tuple(
                record
                for record in trace.observations
                if record.arrival_timestamp_s <= decision_timestamp_s + 1.0e-12
            )
            window = AttributionObservationWindow(
                run_id=scenario.run_id,
                decision_step_index=decision_step_index,
                decision_timestamp_s=decision_timestamp_s,
                observations=visible,
            )
            vector = extractor.transform(window)
            names = names or vector.names
            if vector.names != names:
                raise ValueError("attribution feature schema changed within one split")
            feature_rows.append(vector.values)
            labels.append(truth_override or cause)
            run_ids.append(scenario.run_id)
            split_ids.append(split)
            steps.append(decision_step_index)
            timestamps.append(decision_timestamp_s)
            windows.append(window)
    if names is None:
        raise ValueError("cannot build an empty attribution split")
    dataset = AttributionDataset(
        feature_names=names,
        features=np.vstack(feature_rows),
        labels=tuple(labels),
        run_ids=tuple(run_ids),
        split_ids=tuple(split_ids),
        decision_step_indices=np.asarray(steps, dtype=int),
        decision_timestamps_s=np.asarray(timestamps, dtype=float),
    )
    dataset.validate()
    return BuiltSplit(dataset, tuple(windows), tuple(manifest))


def combine_datasets(*datasets: AttributionDataset) -> AttributionDataset:
    if not datasets or any(
        dataset.feature_names != datasets[0].feature_names for dataset in datasets
    ):
        raise ValueError("attribution datasets require one shared feature schema")
    combined = AttributionDataset(
        feature_names=datasets[0].feature_names,
        features=np.vstack([dataset.features for dataset in datasets]),
        labels=tuple(label for dataset in datasets for label in dataset.labels),
        run_ids=tuple(run for dataset in datasets for run in dataset.run_ids),
        split_ids=tuple(split for dataset in datasets for split in dataset.split_ids),
        decision_step_indices=np.concatenate(
            [dataset.decision_step_indices for dataset in datasets]
        ),
        decision_timestamps_s=np.concatenate(
            [dataset.decision_timestamps_s for dataset in datasets]
        ),
    )
    combined.validate()
    return combined


def dataset_sha256(dataset: AttributionDataset) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(dataset.features, dtype="<f8").tobytes())
    metadata = {
        "feature_names": dataset.feature_names,
        "labels": [label.value for label in dataset.labels],
        "run_ids": dataset.run_ids,
        "split_ids": dataset.split_ids,
        "decision_step_indices": dataset.decision_step_indices.tolist(),
        "decision_timestamps_s": dataset.decision_timestamps_s.tolist(),
    }
    digest.update(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return digest.hexdigest()


def neutral_positive_prediction(window: AttributionObservationWindow) -> Prediction:
    return Prediction(
        probability=0.90,
        predicted_excursion=True,
        conformal_prediction_set=(1,),
        uncertainty_valid=True,
        feature_cutoff_step_index=window.decision_step_index,
        feature_cutoff_timestamp_s=window.decision_timestamp_s,
        latency_s=0.0,
    )


def evaluate_estimator(
    estimator: RootCauseEstimator,
    built: BuiltSplit,
    method: AttributionMethod,
) -> list[dict[str, Any]]:
    estimator.reset()
    rows: list[dict[str, Any]] = []
    for window, truth in zip(built.windows, built.dataset.labels, strict=True):
        started = time.perf_counter()
        result = estimator.estimate(window, neutral_positive_prediction(window))
        latency_s = time.perf_counter() - started
        row: dict[str, Any] = {
            "model_kind": method.value,
            "run_id": window.run_id,
            "decision_step_index": window.decision_step_index,
            "decision_timestamp_s": window.decision_timestamp_s,
            "event_offset_s": (
                window.decision_timestamp_s
                - estimator.config.simulation.event_start_s
            ),
            "truth_cause": truth.value,
            "predicted_cause": result.predicted_cause.value,
            "rule_chain_ids": "|".join(result.rule_chain_ids),
            "causal_proof": result.causal_proof,
            "latency_s": latency_s,
        }
        for cause in ALL_CAUSES:
            row[f"probability_{cause.value}"] = result.probability_by_cause[cause]
        rows.append(row)
    return rows


def _model_probabilities(row: Mapping[str, Any]) -> np.ndarray:
    values = np.asarray(
        [float(row[f"probability_{cause.value}"]) for cause in MODEL_CAUSES],
        dtype=float,
    )
    total = float(np.sum(values))
    if total <= 0.0:
        raise ValueError("model-cause probability mass must be positive")
    return values / total


def _ece(
    truth: np.ndarray,
    predictions: np.ndarray,
    probabilities: np.ndarray,
    bins: int,
) -> float:
    confidence = np.max(probabilities, axis=1)
    edges = np.linspace(0.0, 1.0, bins + 1)
    value = 0.0
    for index in range(bins):
        upper_inclusive = index == bins - 1
        mask = (confidence >= edges[index]) & (
            confidence <= edges[index + 1]
            if upper_inclusive
            else confidence < edges[index + 1]
        )
        if np.any(mask):
            accuracy = float(np.mean(predictions[mask] == truth[mask]))
            value += float(np.mean(mask)) * abs(accuracy - float(np.mean(confidence[mask])))
    return value


def attribution_metrics(
    rows: Sequence[Mapping[str, Any]],
    config: AttributionConfig,
) -> dict[str, Any]:
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

    latest_by_run: dict[str, Mapping[str, Any]] = {}
    rows_by_run: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        rows_by_run.setdefault(str(row["run_id"]), []).append(row)
        prior = latest_by_run.get(str(row["run_id"]))
        if prior is None or float(row["decision_timestamp_s"]) > float(
            prior["decision_timestamp_s"]
        ):
            latest_by_run[str(row["run_id"])] = row
    final = [latest_by_run[run_id] for run_id in sorted(latest_by_run)]
    labels = [cause.value for cause in MODEL_CAUSES]
    label_index = {label: index for index, label in enumerate(labels)}
    truth_text = np.asarray([str(row["truth_cause"]) for row in final], dtype=object)
    predicted_text = np.asarray(
        [str(row["predicted_cause"]) for row in final], dtype=object
    )
    truth_indices = np.asarray([label_index[value] for value in truth_text], dtype=int)
    predicted_indices = np.asarray(
        [label_index[value] for value in predicted_text], dtype=int
    )
    probabilities = np.vstack([_model_probabilities(row) for row in final])
    confusion = confusion_matrix(truth_text, predicted_text, labels=labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        truth_text,
        predicted_text,
        labels=labels,
        zero_division=0,
    )
    accuracy = float(np.mean(truth_text == predicted_text))
    one_hot = np.eye(len(labels), dtype=float)[truth_indices]
    brier = float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))
    clip = config.fusion.probability_clip
    log_loss = -float(
        np.mean(
            np.log(
                np.clip(
                    probabilities[np.arange(len(probabilities)), truth_indices],
                    clip,
                    1.0,
                )
            )
        )
    )
    top_two = np.argsort(-probabilities, axis=1)[:, :2]
    top_two_accuracy = float(
        np.mean(
            [truth_index in positions for truth_index, positions in zip(truth_indices, top_two)]
        )
    )
    known = truth_text != RootCause.UNKNOWN.value
    selected = predicted_text != RootCause.UNKNOWN.value
    known_coverage = float(np.mean(selected[known])) if np.any(known) else None
    selective_accuracy = (
        float(np.mean(truth_text[selected] == predicted_text[selected]))
        if np.any(selected)
        else None
    )
    unknown_mask = truth_text == RootCause.UNKNOWN.value
    unknown_recall = (
        float(np.mean(predicted_text[unknown_mask] == RootCause.UNKNOWN.value))
        if np.any(unknown_mask)
        else None
    )
    delays: list[float] = []
    for run_rows in rows_by_run.values():
        truth = str(run_rows[0]["truth_cause"])
        if truth == RootCause.UNKNOWN.value:
            continue
        correct = [
            float(row["event_offset_s"])
            for row in run_rows
            if str(row["predicted_cause"]) == truth
        ]
        if correct:
            delays.append(min(correct))
    latencies = np.asarray([float(row["latency_s"]) for row in rows], dtype=float)
    rng = np.random.default_rng(config.evaluation.grouped_bootstrap_seed)
    bootstrap_accuracy = np.empty(
        config.evaluation.grouped_bootstrap_repetitions,
        dtype=float,
    )
    correctness = truth_text == predicted_text
    for index in range(len(bootstrap_accuracy)):
        sample = rng.integers(0, len(final), size=len(final))
        bootstrap_accuracy[index] = float(np.mean(correctness[sample]))
    return {
        "evaluation_unit": "FINAL_WINDOW_PER_WHOLE_RUN",
        "run_count": len(final),
        "row_count": len(rows),
        "accuracy": accuracy,
        "macro_precision": float(np.mean(precision)),
        "macro_recall": float(np.mean(recall)),
        "macro_f1": float(np.mean(f1)),
        "top_two_accuracy": top_two_accuracy,
        "multiclass_brier_score": brier,
        "multiclass_log_loss": log_loss,
        "expected_calibration_error": _ece(
            truth_indices,
            predicted_indices,
            probabilities,
            config.evaluation.calibration_bins,
        ),
        "known_cause_coverage": known_coverage,
        "selective_accuracy": selective_accuracy,
        "unknown_recall": unknown_recall,
        "normal_false_attribution_rate": (
            None if unknown_recall is None else 1.0 - unknown_recall
        ),
        "median_earliest_correct_attribution_delay_s": (
            float(np.median(delays)) if delays else None
        ),
        "correct_attribution_run_count": len(delays),
        "latency_s": {
            "mean": float(np.mean(latencies)),
            "median": float(np.median(latencies)),
            "p95": float(np.percentile(latencies, 95)),
            "maximum": float(np.max(latencies)),
        },
        "grouped_bootstrap_accuracy": {
            "repetitions": len(bootstrap_accuracy),
            "mean": float(np.mean(bootstrap_accuracy)),
            "p05": float(np.percentile(bootstrap_accuracy, 5)),
            "p95": float(np.percentile(bootstrap_accuracy, 95)),
        },
        "labels": labels,
        "confusion_matrix": confusion.tolist(),
        "per_class": {
            label: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(labels)
        },
    }


def build_preholdout_payload(
    config: AttributionConfig,
) -> tuple[BuiltSplit, BuiltSplit, AttributionDataset, dict[str, Any]]:
    train_scenarios = scenarios_for_split(
        config,
        "TRAIN",
        count=config.splits.runs_per_cause.training,
        seed_start=config.splits.train_seed_start,
    )
    calibration_scenarios = scenarios_for_split(
        config,
        "CALIBRATION",
        count=config.splits.runs_per_cause.calibration,
        seed_start=config.splits.calibration_seed_start,
    )
    train = build_split(config, "TRAIN", train_scenarios)
    calibration = build_split(config, "CALIBRATION", calibration_scenarios)
    dataset = combine_datasets(train.dataset, calibration.dataset)
    payload = {
        "config_sha256": sha256_file(CONFIG_PATH),
        "feature_names": dataset.feature_names,
        "feature_count": len(dataset.feature_names),
        "train": {
            "dataset_sha256": dataset_sha256(train.dataset),
            "row_count": len(train.dataset.labels),
            "run_count": len(set(train.dataset.run_ids)),
            "scenario_manifest": train.scenario_manifest,
        },
        "calibration": {
            "dataset_sha256": dataset_sha256(calibration.dataset),
            "row_count": len(calibration.dataset.labels),
            "run_count": len(set(calibration.dataset.run_ids)),
            "scenario_manifest": calibration.scenario_manifest,
        },
        "split_run_overlap": sorted(
            set(train.dataset.run_ids) & set(calibration.dataset.run_ids)
        ),
        "forbidden_feature_names": sorted(
            name
            for name in dataset.feature_names
            if any(
                name.startswith(forbidden)
                for forbidden in config.features.forbidden_signal_ids
            )
        ),
        "online_window_fields": tuple(AttributionObservationWindow.__dataclass_fields__),
        "holdout_generated": False,
    }
    payload["deterministic_payload_sha256"] = canonical_sha256(payload)
    return train, calibration, dataset, payload


def prepare_calibration() -> dict[str, Any]:
    if OPENING_MARKER_PATH.exists() or RESULTS_PATH.exists():
        raise ValueError("WP13 holdout was already opened; preparation cannot overwrite it")
    config = load_attribution_config(CONFIG_PATH)
    train, calibration, dataset, preparation_payload = build_preholdout_payload(config)
    if preparation_payload["split_run_overlap"]:
        raise ValueError("WP13 TRAIN and CALIBRATION runs overlap")
    if preparation_payload["forbidden_feature_names"]:
        raise ValueError("WP13 preholdout features include a forbidden signal")
    if "offline_initiating_cause" in preparation_payload["online_window_fields"]:
        raise ValueError("offline simulator labels leaked into the online window type")

    estimators: dict[AttributionMethod, RootCauseEstimator] = {}
    calibration_results: dict[str, Any] = {}
    model_hashes: dict[str, dict[str, str]] = {}
    for method in METHODS:
        estimator = RootCauseEstimator(config, method)
        if method in {AttributionMethod.LOGISTIC, AttributionMethod.HYBRID}:
            estimator.fit(dataset)
        estimators[method] = estimator
        rows = evaluate_estimator(estimator, calibration, method)
        calibration_results[method.value] = attribution_metrics(rows, config)
        path = model_path(method)
        estimator.save(path)
        model_hashes[method.value] = {
            "artifact": str(path.relative_to(ROOT)),
            "artifact_sha256": sha256_file(path),
            "sidecar_sha256": sha256_file(path.with_suffix(path.suffix + ".sha256")),
            "fit_group_sha256": estimator.fit_group_sha256 or "NOT_APPLICABLE",
            "calibration_temperature": estimator.calibration_temperature,
        }

    calibration_report = {
        "schema_version": "1.0.0",
        "experiment_revision": config.experiment_revision,
        "evidence_plane": "SYNTHETIC_SIMULATOR_ONLY",
        "holdout_generated": False,
        "diagnostic_warning_policy": "NEUTRAL_VALID_POSITIVE_SINGLETON",
        "calibration_metrics_are_not_holdout_metrics": True,
        "results": calibration_results,
        "claim_boundary": (
            "CALIBRATION-ONLY SYNTHETIC DIAGNOSTIC EVIDENCE; "
            "NO CAUSAL PROOF OR REAL-FAB VALIDATION"
        ),
    }
    write_json_atomic(CALIBRATION_PATH, calibration_report)
    manifest = {
        "schema_version": "1.0.0",
        "experiment_revision": config.experiment_revision,
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "preparation_payload": preparation_payload,
        "model_artifacts": model_hashes,
        "calibration_report": str(CALIBRATION_PATH.relative_to(ROOT)),
        "calibration_report_sha256": sha256_file(CALIBRATION_PATH),
        "scientific_choices_frozen_before_holdout": True,
        "holdout_generated": False,
    }
    write_json_atomic(MANIFEST_PATH, manifest)
    return {
        "mode": "PREPARE_TRAIN_CALIBRATION_ONLY",
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "preparation_payload_sha256": preparation_payload[
            "deterministic_payload_sha256"
        ],
        "train_rows": len(train.dataset.labels),
        "calibration_rows": len(calibration.dataset.labels),
        "holdout_generated": False,
    }


def load_manifest() -> dict[str, Any]:
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load frozen WP13 preholdout manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("holdout_generated") is not False:
        raise ValueError("WP13 preholdout manifest is invalid or already opened")
    return payload


def compound_evaluation(
    config: AttributionConfig,
    estimator: RootCauseEstimator,
) -> dict[str, Any]:
    scenarios: list[tuple[ChainScenario, RootCause]] = []
    count = config.splits.runs_per_cause.compound
    demand_bounds = config.simulation.scenario_ranges.tool_demand_m3_s
    for index in range(count):
        seed = config.splits.compound_seed_start + index
        rng = np.random.default_rng(seed)
        scenarios.append(
            (
                ChainScenario(
                    run_id=f"compound-run-{index:04d}",
                    family=ChainEventKind.COMPOUND_INTERRUPTION_DEMAND,
                    seed=seed,
                    event_start_s=config.simulation.event_start_s,
                    event_duration_s=config.simulation.event_duration_s,
                    tool_demand_m3_s=_uniform(rng, demand_bounds),
                ),
                RootCause.UNKNOWN,
            )
        )
    built = build_split(config, "UNSEEN_COMPOUND", scenarios)
    rows = evaluate_estimator(estimator, built, AttributionMethod.HYBRID)
    final: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        prior = final.get(str(row["run_id"]))
        if prior is None or float(row["decision_timestamp_s"]) > float(
            prior["decision_timestamp_s"]
        ):
            final[str(row["run_id"])] = row
    truth = {
        RootCause.GRID_INTERRUPTION.value,
        RootCause.TOOL_DEMAND_SPIKE.value,
    }
    recalls: list[float] = []
    abstentions: list[bool] = []
    for row in final.values():
        ranked = sorted(
            PRIMARY_INITIATING_CAUSES,
            key=lambda cause: -float(row[f"probability_{cause.value}"]),
        )[:2]
        recalls.append(len(truth & {cause.value for cause in ranked}) / len(truth))
        abstentions.append(str(row["predicted_cause"]) == RootCause.UNKNOWN.value)
    return {
        "run_count": len(final),
        "ordered_offline_truth": [
            RootCause.GRID_INTERRUPTION.value,
            RootCause.TOOL_DEMAND_SPIKE.value,
        ],
        "abstention_rate": float(np.mean(abstentions)),
        "truth_set_recall_at_two": float(np.mean(recalls)),
        "rows": rows,
    }


def interpretation_gates(
    config: AttributionConfig,
    model_results: Mapping[str, Mapping[str, Any]],
    compound: Mapping[str, Any],
    preparation_payload: Mapping[str, Any],
) -> dict[str, Any]:
    hybrid = model_results[AttributionMethod.HYBRID.value]
    baseline = model_results[AttributionMethod.ALWAYS_UNKNOWN.value]
    values = {
        "accuracy": hybrid["accuracy"] >= config.evaluation.minimum_accuracy,
        "macro_recall": (
            hybrid["macro_recall"] >= config.evaluation.minimum_macro_recall
        ),
        "accuracy_improvement_over_unknown": (
            hybrid["accuracy"] - baseline["accuracy"]
            >= config.evaluation.minimum_accuracy_improvement_over_unknown
        ),
        "unknown_recall": (
            hybrid["unknown_recall"] >= config.evaluation.minimum_unknown_recall
        ),
        "normal_false_attribution_rate": (
            hybrid["normal_false_attribution_rate"]
            <= config.evaluation.maximum_normal_false_attribution_rate
        ),
        "selective_accuracy": (
            hybrid["selective_accuracy"] is not None
            and hybrid["selective_accuracy"]
            >= config.evaluation.minimum_selective_accuracy
        ),
        "known_cause_coverage": (
            hybrid["known_cause_coverage"]
            >= config.evaluation.minimum_known_cause_coverage
        ),
        "compound_abstention": (
            compound["abstention_rate"]
            >= config.evaluation.minimum_compound_abstention_rate
        ),
        "zero_forbidden_or_future_features": (
            not preparation_payload["forbidden_feature_names"]
            and not preparation_payload["split_run_overlap"]
            and preparation_payload["holdout_generated"] is False
        ),
    }
    return {"checks": values, "all_passed": all(values.values())}


def make_figures(
    metrics: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = list(metrics["labels"])
    short = [
        label.replace("GRID_", "G_").replace("SENSOR_FAULT", "S_FAULT")
        for label in labels
    ]
    confusion = np.asarray(metrics["confusion_matrix"], dtype=float)
    figure, axis = plt.subplots(figsize=(10, 8))
    image = axis.imshow(confusion, cmap="Blues")
    axis.set_xticks(range(len(labels)), short, rotation=55, ha="right", fontsize=7)
    axis.set_yticks(range(len(labels)), short, fontsize=7)
    axis.set_xlabel("Predicted synthetic cause")
    axis.set_ylabel("Offline simulator initiating label")
    axis.set_title("WP13 hybrid held-out run-level confusion")
    for row in range(len(labels)):
        for column in range(len(labels)):
            axis.text(column, row, int(confusion[row, column]), ha="center", va="center")
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.tight_layout()
    confusion_path = output_dir / "wp13_hybrid_confusion.png"
    figure.savefig(confusion_path, dpi=180)
    plt.close(figure)

    recalls = [float(metrics["per_class"][label]["recall"]) for label in labels]
    figure, axis = plt.subplots(figsize=(10, 4.8))
    axis.bar(range(len(labels)), recalls, color="#2c7fb8")
    axis.axhline(0.65, color="#d95f0e", linestyle="--", label="macro gate reference")
    axis.set_xticks(range(len(labels)), short, rotation=55, ha="right", fontsize=7)
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("Held-out recall")
    axis.set_title("WP13 hybrid per-class recall (synthetic)")
    axis.legend(loc="lower right")
    figure.tight_layout()
    recall_path = output_dir / "wp13_hybrid_recall.png"
    figure.savefig(recall_path, dpi=180)
    plt.close(figure)
    return {
        "confusion": str(confusion_path.relative_to(ROOT)),
        "per_class_recall": str(recall_path.relative_to(ROOT)),
    }


def run_one_shot(*, authorize_holdout_open: bool) -> dict[str, Any]:
    if not authorize_holdout_open:
        raise ValueError(
            "--run-one-shot also requires the explicit --authorize-holdout-open flag"
        )
    if OPENING_MARKER_PATH.exists() or RESULTS_PATH.exists():
        raise ValueError(
            "the WP13 one-shot opening was already consumed; follow the failure policy"
        )
    config = load_attribution_config(CONFIG_PATH)
    frozen_manifest = load_manifest()
    _, _, _, replayed_payload = build_preholdout_payload(config)
    if replayed_payload != frozen_manifest["preparation_payload"]:
        raise ValueError("committed WP13 preholdout payload does not replay exactly")
    git_evidence = require_clean_committed_checkpoint()
    test_evidence = run_focused_tests()
    if require_clean_committed_checkpoint() != git_evidence:
        raise ValueError("Git checkpoint changed during WP13 focused preflight tests")
    opening = {
        "schema_version": "1.0.0",
        "state": "OPENING_AUTHORIZATION_CONSUMED_RUN_STARTED",
        "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_evidence["git_head"],
        "preparation_payload_sha256": replayed_payload[
            "deterministic_payload_sha256"
        ],
        "explicit_holdout_authorization": True,
        "claim_boundary": "SYNTHETIC_SIMULATOR_ATTRIBUTION_ONLY",
    }
    write_json_atomic(OPENING_MARKER_PATH, opening)

    test_scenarios = scenarios_for_split(
        config,
        "TEST",
        count=config.splits.runs_per_cause.test,
        seed_start=config.splits.test_seed_start,
    )
    test = build_split(config, "TEST", test_scenarios)
    estimators = {
        method: RootCauseEstimator.load(model_path(method)) for method in METHODS
    }
    all_rows: list[dict[str, Any]] = []
    model_results: dict[str, Any] = {}
    for method, estimator in estimators.items():
        rows = evaluate_estimator(estimator, test, method)
        all_rows.extend(rows)
        model_results[method.value] = attribution_metrics(rows, config)

    hybrid = estimators[AttributionMethod.HYBRID]
    compound = compound_evaluation(config, hybrid)
    compound_rows = list(compound.pop("rows"))
    all_rows.extend(compound_rows)

    robustness_results: dict[str, Any] = {}
    robustness_count = config.splits.runs_per_cause.robustness
    for position, case in enumerate(
        ("HIGH_NOISE", "HIGH_DELAY", "HIGH_DROPOUT", "PARAMETER_MISMATCH")
    ):
        scenarios = scenarios_for_split(
            config,
            case,
            count=robustness_count,
            seed_start=config.splits.robustness_seed_start + 1000 * position,
        )
        built = build_split(config, case, scenarios, robustness=case)
        rows = evaluate_estimator(hybrid, built, AttributionMethod.HYBRID)
        all_rows.extend(rows)
        robustness_results[case] = attribution_metrics(rows, config)

    pre_event_scenarios = scenarios_for_split(
        config,
        "PRE_EVENT",
        count=robustness_count,
        seed_start=config.splits.robustness_seed_start + 5000,
    )
    pre_event = build_split(
        config,
        "PRE_EVENT",
        pre_event_scenarios,
        decision_offsets_s=(-0.50,),
        truth_override=RootCause.UNKNOWN,
    )
    pre_event_rows = evaluate_estimator(hybrid, pre_event, AttributionMethod.HYBRID)
    all_rows.extend(pre_event_rows)
    robustness_results["PRE_EVENT_FALSE_CAUSE_AUDIT"] = attribution_metrics(
        pre_event_rows,
        config,
    )

    gates = interpretation_gates(
        config,
        model_results,
        compound,
        replayed_payload,
    )
    figures = make_figures(
        model_results[AttributionMethod.HYBRID.value],
        FIGURE_DIR,
    )
    deterministic_rows = [
        {
            key: value
            for key, value in row.items()
            if key != "latency_s"
        }
        for row in all_rows
    ]
    deterministic_payload = {
        "experiment_revision": config.experiment_revision,
        "test_dataset_sha256": dataset_sha256(test.dataset),
        "rows": deterministic_rows,
        "compound": compound,
        "gates": gates,
    }
    results = {
        "schema_version": "1.0.0",
        "experiment_revision": config.experiment_revision,
        "evidence_plane": "SYNTHETIC_SIMULATOR_ONLY",
        "diagnostic_warning_policy": "NEUTRAL_VALID_POSITIVE_SINGLETON",
        "model_results": model_results,
        "compound_results": compound,
        "robustness_results": robustness_results,
        "interpretation_gates": gates,
        "test_dataset": {
            "row_count": len(test.dataset.labels),
            "run_count": len(set(test.dataset.run_ids)),
            "sha256": dataset_sha256(test.dataset),
        },
        "preflight_evidence": {
            **git_evidence,
            "focused_tests": test_evidence,
            "opening_marker": str(OPENING_MARKER_PATH.relative_to(ROOT)),
            "opening_marker_sha256": sha256_file(OPENING_MARKER_PATH),
            "scientific_choices_frozen_before_holdout": True,
        },
        "figures": figures,
        "deterministic_payload_sha256": canonical_sha256(deterministic_payload),
        "claim_boundary": (
            "CONDITIONAL SYNTHETIC DIAGNOSTIC ATTRIBUTION ONLY; FEATURE "
            "CONTRIBUTIONS AND RULE CHAINS ARE NOT CAUSAL PROOF"
        ),
    }
    write_csv_atomic(PREDICTIONS_PATH, all_rows)
    results["predictions"] = {
        "path": str(PREDICTIONS_PATH.relative_to(ROOT)),
        "sha256": sha256_file(PREDICTIONS_PATH),
    }
    write_json_atomic(RESULTS_PATH, results)
    return {
        "mode": "ONE_SHOT_SYNTHETIC_ATTRIBUTION_VALIDATION",
        "results": str(RESULTS_PATH.relative_to(ROOT)),
        "results_sha256": sha256_file(RESULTS_PATH),
        "deterministic_payload_sha256": results[
            "deterministic_payload_sha256"
        ],
        "hybrid_accuracy": model_results[AttributionMethod.HYBRID.value][
            "accuracy"
        ],
        "hybrid_macro_recall": model_results[AttributionMethod.HYBRID.value][
            "macro_recall"
        ],
        "all_interpretation_gates_passed": gates["all_passed"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or one-shot evaluate frozen WP13 attribution."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare-calibration",
        action="store_true",
        help="generate only TRAIN/CALIBRATION evidence and fitted artifacts",
    )
    mode.add_argument(
        "--run-one-shot",
        action="store_true",
        help="open and execute the frozen synthetic TEST and robustness sets once",
    )
    parser.add_argument(
        "--authorize-holdout-open",
        action="store_true",
        help="explicitly consume the one-shot synthetic holdout authorization",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.prepare_calibration:
            if args.authorize_holdout_open:
                raise ValueError(
                    "holdout authorization is invalid in calibration-only mode"
                )
            summary = prepare_calibration()
        else:
            summary = run_one_shot(
                authorize_holdout_open=args.authorize_holdout_open
            )
    except ValueError as exc:
        parser.exit(2, f"WP13 guard refused execution: {exc}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
