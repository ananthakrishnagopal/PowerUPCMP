from semifab_poc.data.schema import LatentStateRecord
from semifab_poc.simulation.sensors import SensorConfig, SensorModel


def _latent(value: float, step: int, timestamp_s: float) -> LatentStateRecord:
    return LatentStateRecord(
        run_id="sensor-run",
        step_index=step,
        timestamp_s=timestamp_s,
        signal_id="upw.supply_pressure",
        value=value,
        unit="Pa",
        subsystem="upw",
        provenance_id="synthetic-default-v1",
    )


def _model() -> SensorModel:
    return SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                noise_std=20.0,
                bias=5.0,
                drift_per_s=1.0,
                quantization_step=0.5,
                delay_s=0.01,
                timestamp_jitter_std_s=0.002,
            ),
        ),
    )


def test_sensor_corruption_does_not_mutate_latent_state() -> None:
    latent = _latent(100_000.0, 3, 0.03)
    before = latent.model_dump()
    _model().sample((latent,), 3, 0.03)
    assert latent.model_dump() == before


def test_fixed_seed_replays_identical_observations() -> None:
    trace = tuple(_latent(100_000.0 + step, step, step * 0.01) for step in range(5))
    first = _model()
    second = _model()
    first.reset(73)
    second.reset(73)
    outputs_one = tuple(first.sample((record,), record.step_index, record.timestamp_s) for record in trace)
    outputs_two = tuple(second.sample((record,), record.step_index, record.timestamp_s) for record in trace)
    assert outputs_one == outputs_two


def test_reported_clock_jitter_never_changes_source_or_arrival_causality() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                timestamp_jitter_std_s=0.05,
            ),
        ),
    )
    model.reset(917)
    saw_reported_early = False
    saw_reported_late = False
    for step in range(100):
        timestamp_s = step * 0.01
        observation = model.sample(
            (_latent(100_000.0 + step, step, timestamp_s),),
            step,
            timestamp_s,
        )[0]
        assert observation.source_timestamp_s == timestamp_s
        assert observation.arrival_timestamp_s == timestamp_s
        assert observation.arrival_timestamp_s >= observation.source_timestamp_s
        saw_reported_early |= observation.observed_timestamp_s < timestamp_s
        saw_reported_late |= observation.observed_timestamp_s > timestamp_s
    assert saw_reported_early
    assert saw_reported_late
