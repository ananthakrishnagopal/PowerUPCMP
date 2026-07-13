from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from semifab_poc.config import load_runtime_config
from semifab_poc.models.early_warning import load_early_warning_config
from semifab_poc.models.early_warning import generate_excursion_labels
from scripts.validate_wp12_early_warning import chain_runner
from semifab_poc.simulation.chain import (
    ChainEventKind,
    ChainScenario,
    ChainSchedule,
    SyntheticChainRunner,
)
from semifab_poc.simulation.coupling import UtilityCmpTopology
from semifab_poc.simulation.sensors import SensorConfig


ROOT = Path(__file__).resolve().parents[2]


def _runner() -> SyntheticChainRunner:
    runtime = load_runtime_config(ROOT / "configs" / "default.yaml")
    warning = load_early_warning_config(ROOT / "configs" / "models" / "early_warning.yaml")
    units = {
        "electrical.grid_voltage": "pu",
        "electrical.ups_output_voltage": "pu",
        "electrical.ups_battery_energy": "J",
        "drive.motor_angular_speed": "rad/s",
        "pump.volumetric_flow": "m^3/s",
        "upw.supply_pressure": "Pa",
        "upw.tool_flow": "m^3/s",
        "upw.temperature": "K",
    }
    sensors = tuple(
        SensorConfig(
            sensor_id=f"warning-{index}",
            signal_id=signal_id,
            unit=units[signal_id],
            sample_period_s=warning.sensors.sample_period_s,
            delay_s=warning.sensors.delay_s,
            noise_std=warning.sensors.noise_by_signal[signal_id],
            packet_loss_probability=warning.sensors.packet_loss_probability,
            timestamp_jitter_std_s=warning.sensors.timestamp_jitter_std_s,
        )
        for index, signal_id in enumerate(warning.features.allowed_signal_ids)
    )
    return SyntheticChainRunner(
        runtime,
        ChainSchedule(
            dt_s=runtime.dt_s,
            duration_s=2.0,
            plant_warmup_s=0.5,
            dress_end_s=0.5,
            polish_start_s=1.0,
        ),
        replace(
            runtime.coupling,
            topology=UtilityCmpTopology.DRESSING_WATER_SUPPORT,
            link_strength=1.0,
        ),
        sensors,
    )


def test_warning_chain_replays_truth_and_observations_deterministically() -> None:
    runner = _runner()
    scenario = ChainScenario(
        run_id="warning-chain",
        family=ChainEventKind.HEALTHY_SAG,
        seed=1234,
        event_start_s=0.2,
        event_duration_s=0.2,
        grid_voltage_pu=0.75,
    )
    first = runner.run(scenario)
    second = runner.run(scenario)
    assert first == second
    assert len(first.truth_rows) == 200
    assert first.observations
    assert all(
        observation.arrival_timestamp_s >= observation.source_timestamp_s
        for observation in first.observations
        if observation.source_timestamp_s is not None
    )
    assert not any(
        observation.signal_id.startswith("cmp.")
        or observation.signal_id.startswith("coupling.")
        for observation in first.observations
    )


def test_full_dress_service_loss_reaches_frozen_positive_target() -> None:
    warning = load_early_warning_config(ROOT / "configs" / "models" / "early_warning.yaml")
    runner = chain_runner(warning, UtilityCmpTopology.DRESSING_WATER_SUPPORT)
    reference = runner.run(
        ChainScenario(
            run_id="warning-reference",
            family=ChainEventKind.NORMAL,
            seed=900,
            event_start_s=0.0,
            event_duration_s=0.0,
        )
    )
    disturbed = runner.run(
        ChainScenario(
            run_id="warning-full-dress-trip",
            family=ChainEventKind.PUMP_TRIP,
            seed=901,
            event_start_s=warning.simulation.full_dress_anchor_start_s,
            event_duration_s=(
                warning.simulation.full_dress_anchor_end_s
                - warning.simulation.full_dress_anchor_start_s
            ),
        )
    )
    steps = [int(row["step_index"]) for row in disturbed.truth_rows]
    stride = round(warning.target.decision_period_s / warning.simulation.dt_s)
    labels = generate_excursion_labels(
        run_id=disturbed.run_id,
        timestamps_s=[float(row["timestamp_s"]) for row in disturbed.truth_rows],
        true_mrr_m_s=[float(row["cmp_mrr_m_s"]) for row in disturbed.truth_rows],
        reference_mrr_m_s=[float(row["cmp_mrr_m_s"]) for row in reference.truth_rows],
        process_modes=[str(row["cmp_mode"]) for row in disturbed.truth_rows],
        decision_step_indices=steps[stride - 1 :: stride],
        trace_step_indices=steps,
        config=warning.target,
    )
    assert labels.episode_onset_step_indices
    assert sum(label.excursion_within_horizon for label in labels.labels) > 0
