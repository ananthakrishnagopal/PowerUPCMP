from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from semifab_poc.config import load_runtime_config
from semifab_poc.data.schema import (
    DataOrigin,
    ObservationRecord,
    QualityFlag,
    RootCause,
)
from semifab_poc.models.attribution import (
    ALL_CAUSES,
    MODEL_CAUSES,
    AttributionDataset,
    AttributionError,
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


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "models" / "attribution.yaml"

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

NORMAL = {
    "electrical.grid_voltage": 1.0,
    "electrical.grid_frequency": 50.0,
    "electrical.ups_output_voltage": 1.0,
    "electrical.ups_output_frequency": 50.0,
    "electrical.ups_battery_energy": 3_600_000.0,
    "drive.vfd_available_output": 1.0,
    "drive.vfd_trip_state": False,
    "drive.motor_angular_speed": 188.5,
    "pump.volumetric_flow": 2.0e-4,
    "upw.supply_pressure": 300_000.0,
    "upw.tool_flow": 1.0e-4,
    "upw.valve_position": 1.0,
    "upw.tool_demand": 1.0e-4,
    "upw.temperature": 293.15,
}


def _records(
    run_id: str,
    values: dict[str, float | bool] | None = None,
) -> tuple[ObservationRecord, ...]:
    current = dict(NORMAL)
    current.update(values or {})
    records: list[ObservationRecord] = []
    source_times = np.arange(0.25, 1.001, 0.05)
    for signal_position, signal_id in enumerate(UNITS):
        for sample_position, source_s in enumerate(source_times):
            records.append(
                ObservationRecord(
                    run_id=run_id,
                    sample_index=sample_position,
                    source_step_index=int(round(source_s / 0.05)),
                    source_timestamp_s=float(source_s),
                    observed_timestamp_s=float(source_s),
                    arrival_timestamp_s=float(source_s),
                    sensor_id=f"sensor-{signal_position:02d}-{signal_id}",
                    signal_id=signal_id,
                    value=current[signal_id],
                    unit=UNITS[signal_id],
                    quality_flags=(QualityFlag.VALID,),
                    uncertainty_std=0.0,
                    data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
                )
            )
    return tuple(records)


def _window(
    run_id: str,
    values: dict[str, float | bool] | None = None,
) -> AttributionObservationWindow:
    return AttributionObservationWindow(
        run_id=run_id,
        decision_step_index=20,
        decision_timestamp_s=1.0,
        observations=_records(run_id, values),
    )


def _positive_prediction() -> Prediction:
    return Prediction(
        probability=0.90,
        predicted_excursion=True,
        conformal_prediction_set=(1,),
        uncertainty_valid=True,
        feature_cutoff_step_index=20,
        feature_cutoff_timestamp_s=1.0,
        latency_s=0.0,
    )


CAUSE_VALUES = {
    RootCause.GRID_VOLTAGE_SAG: {"electrical.grid_voltage": 0.80},
    RootCause.GRID_VOLTAGE_SWELL: {"electrical.grid_voltage": 1.15},
    RootCause.GRID_INTERRUPTION: {"electrical.grid_voltage": 0.0},
    RootCause.GRID_FREQUENCY_DEVIATION: {"electrical.grid_frequency": 48.5},
    RootCause.PUMP_TRIP: {
        "drive.vfd_available_output": 0.0,
        "drive.vfd_trip_state": True,
        "drive.motor_angular_speed": 80.0,
        "pump.volumetric_flow": 8.0e-5,
        "upw.supply_pressure": 140_000.0,
        "upw.tool_flow": 4.0e-5,
    },
    RootCause.VALVE_RESTRICTION: {
        "upw.valve_position": 0.50,
        "upw.tool_flow": 1.0e-4,
    },
    RootCause.TOOL_DEMAND_SPIKE: {"upw.tool_demand": 2.0e-4},
    RootCause.THERMAL_EXCURSION: {"upw.temperature": 296.15},
    RootCause.PRESSURE_SENSOR_FAULT: {"upw.supply_pressure": 375_000.0},
    RootCause.FLOW_SENSOR_FAULT: {"upw.tool_flow": 1.5e-4},
}


def test_wp13_configuration_is_strict_and_preregistered() -> None:
    config = load_attribution_config(CONFIG_PATH)
    assert config.experiment_revision == "1.0-preregistered"
    assert config.estimator.primary_method is AttributionMethod.HYBRID
    assert config.estimator.causal_proof is False
    assert len(config.estimator.primary_initiating_causes) == 10
    assert config.estimator.propagation_evidence_causes == (
        RootCause.UPS_TRANSFER,
        RootCause.VFD_DERATING,
    )
    assert config.unknown_policy.forced_unknown_probability == 0.80


def test_feature_extractor_enforces_arrival_source_and_forbidden_boundaries() -> None:
    config = load_attribution_config(CONFIG_PATH)
    extractor = AttributionFeatureExtractor(config.features, config.residuals)
    vector = extractor.transform(_window("feature-run"))
    assert vector.feature_cutoff_step_index == 20
    assert vector.critical_signal_stale is False
    assert vector.aggregate_missing_fraction == pytest.approx(0.0)
    assert "residual:pressure_fraction" in vector.names
    future = next(iter(_records("future-run"))).model_copy(
        update={"arrival_timestamp_s": 1.1}
    )
    with pytest.raises(AttributionError, match="future-arrival"):
        extractor.transform(
            AttributionObservationWindow("future-run", 20, 1.0, (future,))
        )
    forbidden = ObservationRecord(
        run_id="forbidden-run",
        sample_index=0,
        source_step_index=20,
        source_timestamp_s=1.0,
        observed_timestamp_s=1.0,
        arrival_timestamp_s=1.0,
        sensor_id="forbidden-mrr",
        signal_id="cmp.mrr",
        value=1.0e-9,
        unit="m/s",
        quality_flags=(QualityFlag.VALID,),
        uncertainty_std=0.0,
        data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
    )
    with pytest.raises(AttributionError, match="forbidden"):
        extractor.transform(
            AttributionObservationWindow("forbidden-run", 20, 1.0, (forbidden,))
        )


@pytest.mark.parametrize("cause", tuple(CAUSE_VALUES))
def test_rule_estimator_supports_each_primary_initiating_cause(cause: RootCause) -> None:
    config = load_attribution_config(CONFIG_PATH)
    estimator = RootCauseEstimator(config, AttributionMethod.RULE_ONLY)
    result = estimator.estimate(
        _window(f"rule-{cause.value.lower()}", CAUSE_VALUES[cause]),
        _positive_prediction(),
    )
    assert result.predicted_cause is cause
    assert set(result.probability_by_cause) == set(ALL_CAUSES)
    assert sum(result.probability_by_cause.values()) == pytest.approx(1.0)
    assert result.causal_proof is False
    assert not any("causal" in chain_id.lower() for chain_id in result.rule_chain_ids)


def test_propagation_states_are_evidence_not_initiating_predictions() -> None:
    config = load_attribution_config(CONFIG_PATH)
    estimator = RootCauseEstimator(config, AttributionMethod.RULE_ONLY)
    result = estimator.estimate(
        _window(
            "propagation-run",
            {
                "electrical.grid_voltage": 0.75,
                "electrical.ups_output_voltage": 1.0,
                "drive.vfd_available_output": 0.60,
            },
        ),
        _positive_prediction(),
    )
    assert result.predicted_cause is RootCause.GRID_VOLTAGE_SAG
    assert result.residual_evidence["propagation_score:UPS_TRANSFER"] > 0.0
    assert result.residual_evidence["propagation_score:VFD_DERATING"] > 0.0
    assert result.predicted_cause not in {
        RootCause.UPS_TRANSFER,
        RootCause.VFD_DERATING,
    }


def test_warning_uncertainty_and_compound_evidence_force_unknown() -> None:
    config = load_attribution_config(CONFIG_PATH)
    estimator = RootCauseEstimator(config, AttributionMethod.RULE_ONLY)
    no_warning = replace(_positive_prediction(), predicted_excursion=False, probability=0.10)
    first = estimator.estimate(
        _window("no-warning", CAUSE_VALUES[RootCause.GRID_VOLTAGE_SAG]),
        no_warning,
    )
    assert first.predicted_cause is RootCause.UNKNOWN
    assert "ABSTAIN_NO_POSITIVE_WARNING" in first.rule_chain_ids
    assert first.probability_by_cause[RootCause.UNKNOWN] >= 0.80

    uncertain = replace(
        _positive_prediction(),
        conformal_prediction_set=(0, 1),
        uncertainty_valid=False,
    )
    second = estimator.estimate(
        _window("uncertain-warning", CAUSE_VALUES[RootCause.GRID_VOLTAGE_SAG]),
        uncertain,
    )
    assert second.predicted_cause is RootCause.UNKNOWN
    assert "ABSTAIN_WARNING_UNCERTAINTY_INVALID" in second.rule_chain_ids

    compound = estimator.estimate(
        _window(
            "compound-run",
            {
                "electrical.grid_voltage": 0.0,
                "upw.tool_demand": 2.5e-4,
            },
        ),
        _positive_prediction(),
    )
    assert compound.predicted_cause is RootCause.UNKNOWN
    assert "ABSTAIN_COMPOUND_EVIDENCE" in compound.rule_chain_ids


def _dataset(config_path: Path = CONFIG_PATH) -> AttributionDataset:
    config = load_attribution_config(config_path)
    extractor = AttributionFeatureExtractor(config.features, config.residuals)
    feature_names: tuple[str, ...] | None = None
    rows: list[np.ndarray] = []
    labels: list[RootCause] = []
    run_ids: list[str] = []
    splits: list[str] = []
    steps: list[int] = []
    times: list[float] = []
    for split, repetitions in (("TRAIN", 2), ("CALIBRATION", 1)):
        for cause in MODEL_CAUSES:
            values = {} if cause is RootCause.UNKNOWN else CAUSE_VALUES[cause]
            for repetition in range(repetitions):
                run_id = f"{split.lower()}-{cause.value.lower()}-{repetition}"
                vector = extractor.transform(_window(run_id, values))
                feature_names = feature_names or vector.names
                assert vector.names == feature_names
                rows.append(vector.values)
                labels.append(cause)
                run_ids.append(run_id)
                splits.append(split)
                steps.append(20)
                times.append(1.0)
    assert feature_names is not None
    return AttributionDataset(
        feature_names=feature_names,
        features=np.vstack(rows),
        labels=tuple(labels),
        run_ids=tuple(run_ids),
        split_ids=tuple(splits),
        decision_step_indices=np.asarray(steps, dtype=int),
        decision_timestamps_s=np.asarray(times, dtype=float),
    )


def test_hybrid_fit_uses_grouped_roles_and_checksum_round_trips(tmp_path: Path) -> None:
    config = load_attribution_config(CONFIG_PATH)
    dataset = _dataset()
    estimator = RootCauseEstimator(config, AttributionMethod.HYBRID).fit(dataset)
    assert estimator.fit_group_sha256 is not None
    assert estimator.calibration_temperature in config.model.calibration_temperature_grid
    destination = tmp_path / "attribution.pkl"
    estimator.save(destination)
    loaded = RootCauseEstimator.load(destination)
    window = _window("loaded-sag", CAUSE_VALUES[RootCause.GRID_VOLTAGE_SAG])
    original = estimator.estimate(window, _positive_prediction())
    restored = loaded.estimate(window, _positive_prediction())
    assert restored.predicted_cause is original.predicted_cause
    assert np.array_equal(
        np.asarray(list(restored.probability_by_cause.values())),
        np.asarray(list(original.probability_by_cause.values())),
    )
    assert any(
        key.startswith("feature_contribution:")
        for key in restored.residual_evidence
    )
    destination.write_bytes(destination.read_bytes() + b"tamper")
    with pytest.raises(AttributionError, match="checksum"):
        RootCauseEstimator.load(destination)


def test_sensor_fault_changes_observation_not_latent_upw_state() -> None:
    runtime = load_runtime_config(ROOT / "configs" / "default.yaml")
    runner = SyntheticChainRunner(
        runtime,
        ChainSchedule(
            dt_s=runtime.dt_s,
            duration_s=1.0,
            plant_warmup_s=0.5,
            dress_end_s=0.5,
            polish_start_s=0.8,
        ),
        replace(
            runtime.coupling,
            topology=UtilityCmpTopology.DRESSING_WATER_SUPPORT,
            link_strength=1.0,
        ),
        (
            SensorConfig(
                sensor_id="pressure-sensor",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=runtime.dt_s,
            ),
        ),
    )
    normal = runner.run(
        ChainScenario(
            run_id="normal-pressure",
            family=ChainEventKind.NORMAL,
            seed=501,
            event_start_s=0.2,
            event_duration_s=0.2,
        )
    )
    fault = runner.run(
        ChainScenario(
            run_id="fault-pressure",
            family=ChainEventKind.PRESSURE_SENSOR_FAULT,
            seed=501,
            event_start_s=0.2,
            event_duration_s=0.2,
            pressure_sensor_bias_pa=50_000.0,
        )
    )
    assert [row["upw_supply_pressure_pa"] for row in normal.truth_rows] == [
        row["upw_supply_pressure_pa"] for row in fault.truth_rows
    ]
    active = next(
        observation
        for observation in fault.observations
        if observation.source_timestamp_s is not None
        and 0.2
        <= observation.source_timestamp_s - runtime.dt_s
        < 0.4
    )
    truth = fault.truth_rows[int(active.source_step_index) - 1]
    assert float(active.value) == pytest.approx(
        float(truth["upw_supply_pressure_pa"]) + 50_000.0
    )
    assert QualityFlag.BIASED not in active.quality_flags
