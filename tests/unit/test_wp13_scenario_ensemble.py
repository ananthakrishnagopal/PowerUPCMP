from __future__ import annotations

from pathlib import Path

from scripts.validate_wp13_attribution import (
    build_split,
    scenarios_for_split,
    sensor_configs,
)
from semifab_poc.config import load_runtime_config
from semifab_poc.data.schema import RootCause
from semifab_poc.models.attribution import (
    MODEL_CAUSES,
    AttributionObservationWindow,
    load_attribution_config,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "models" / "attribution.yaml"


def test_wp13_scenario_roles_are_disjoint_opaque_and_validate() -> None:
    config = load_attribution_config(CONFIG_PATH)
    runtime = load_runtime_config(ROOT / "configs" / "default.yaml")
    roles = {
        "TRAIN": (
            config.splits.runs_per_cause.training,
            config.splits.train_seed_start,
        ),
        "CALIBRATION": (
            config.splits.runs_per_cause.calibration,
            config.splits.calibration_seed_start,
        ),
        "TEST": (
            config.splits.runs_per_cause.test,
            config.splits.test_seed_start,
        ),
    }
    run_ids_by_role: dict[str, set[str]] = {}
    for role, (count, seed_start) in roles.items():
        scenarios = scenarios_for_split(
            config,
            role,
            count=count,
            seed_start=seed_start,
        )
        assert {cause for _, cause in scenarios} == set(MODEL_CAUSES)
        assert len(scenarios) == count * len(MODEL_CAUSES)
        run_ids_by_role[role] = {scenario.run_id for scenario, _ in scenarios}
        for scenario, cause in scenarios:
            scenario.validate(runtime, config.simulation.duration_s)
            assert cause.value.lower() not in scenario.run_id
            assert cause not in {RootCause.UPS_TRANSFER, RootCause.VFD_DERATING}
    assert not (run_ids_by_role["TRAIN"] & run_ids_by_role["CALIBRATION"])
    assert not (run_ids_by_role["TRAIN"] & run_ids_by_role["TEST"])
    assert not (run_ids_by_role["CALIBRATION"] & run_ids_by_role["TEST"])


def test_wp13_smoke_ensemble_emits_only_arrived_features_without_label_fields() -> None:
    config = load_attribution_config(CONFIG_PATH)
    scenarios = scenarios_for_split(
        config,
        "SMOKE",
        count=1,
        seed_start=123000,
    )
    built = build_split(config, "SMOKE", scenarios)
    assert len(built.dataset.labels) == len(MODEL_CAUSES) * len(
        config.simulation.decision_offsets_s
    )
    assert not any(
        any(name.startswith(forbidden) for forbidden in config.features.forbidden_signal_ids)
        for name in built.dataset.feature_names
    )
    assert "offline_initiating_cause" not in AttributionObservationWindow.__dataclass_fields__
    assert all(
        observation.arrival_timestamp_s <= window.decision_timestamp_s
        for window in built.windows
        for observation in window.observations
    )
    configurations = sensor_configs(config)
    assert {item.signal_id for item in configurations} == set(
        config.features.allowed_signal_ids
    )
    trip = next(
        item for item in configurations if item.signal_id == "drive.vfd_trip_state"
    )
    assert trip.noise_std == 0.0
