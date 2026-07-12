import pytest

from semifab_poc.data.schema import DataOrigin, LatentStateRecord, QualityFlag
from semifab_poc.simulation.sensors import SensorConfig, SensorModel, SensorModelError


def _latent(value: float, step: int = 0, timestamp_s: float = 0.0) -> LatentStateRecord:
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


def test_noise_bias_drift_quantisation_delay_and_jitter_are_explicit() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                bias=10.0,
                drift_per_s=2.0,
                quantization_step=1.0,
                delay_s=0.02,
                timestamp_jitter_std_s=0.001,
            ),
        ),
    )
    model.reset(11)
    assert model.sample((_latent(100_000.0, 100, 1.0),), 100, 1.0) == ()
    assert model.release_arrived(1.019) == ()
    observation = model.release_arrived(1.02)[0]
    assert observation.value == 100_012.0
    assert observation.source_timestamp_s == 1.0
    assert observation.arrival_timestamp_s - observation.source_timestamp_s == pytest.approx(0.02)
    assert QualityFlag.BIASED in observation.quality_flags
    assert QualityFlag.DRIFTING in observation.quality_flags
    assert QualityFlag.QUANTISED in observation.quality_flags
    assert QualityFlag.DELAYED in observation.quality_flags
    assert QualityFlag.TIMESTAMP_JITTERED in observation.quality_flags


def test_packet_loss_creates_explicit_missing_observation() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                packet_loss_probability=1.0,
            ),
        ),
    )
    observation = model.sample((_latent(100_000.0),), 0, 0.0)[0]
    assert observation.value is None
    assert QualityFlag.MISSING in observation.quality_flags
    assert QualityFlag.DROPPED in observation.quality_flags
    assert observation.data_origin is DataOrigin.SYNTHETIC_SIMULATOR


def test_stuck_sensor_reuses_prior_observed_value() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                stuck_probability=1.0,
            ),
        ),
    )
    first = model.sample((_latent(100_000.0),), 0, 0.0)[0]
    second = model.sample((_latent(120_000.0, 1, 0.01),), 1, 0.01)[0]
    assert first.value == 100_000.0
    assert second.value == first.value
    assert QualityFlag.STUCK in second.quality_flags


def test_sampling_rate_mismatch_preserves_source_timestamps() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.10,
            ),
        ),
    )
    first = model.sample((_latent(100_000.0, 0, 0.0),), 0, 0.0)
    skipped = model.sample((_latent(101_000.0, 5, 0.05),), 5, 0.05)
    second = model.sample((_latent(102_000.0, 10, 0.10),), 10, 0.10)
    assert len(first) == 1
    assert skipped == ()
    assert second[0].source_step_index == 10
    assert second[0].source_timestamp_s == 0.10
    assert second[0].observed_timestamp_s == 0.10


def test_reported_jitter_cannot_accelerate_delivery_and_release_is_exactly_once() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                delay_s=0.02,
                timestamp_jitter_std_s=0.10,
            ),
        ),
    )
    model.reset(19)
    assert model.sample((_latent(100_000.0, 100, 1.0),), 100, 1.0) == ()
    assert model.pending_count == 1
    assert model.release_arrived(1.019999) == ()
    delivered = model.release_arrived(1.02)
    assert len(delivered) == 1
    assert delivered[0].arrival_timestamp_s >= delivered[0].source_timestamp_s
    assert delivered[0].arrival_timestamp_s == pytest.approx(1.02)
    assert model.release_arrived(1.02) == ()
    assert model.pending_count == 0


def test_source_boundary_mismatch_and_nonmonotone_calls_are_rejected() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="pressure-1",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
            ),
        ),
    )
    with pytest.raises(SensorModelError, match="step index"):
        model.sample((_latent(100_000.0, 1, 0.0),), 0, 0.0)
    model.sample((_latent(100_000.0, 0, 0.0),), 0, 0.0)
    with pytest.raises(SensorModelError, match="strictly increasing"):
        model.sample((_latent(100_000.0, 0, 0.0),), 0, 0.0)

    different_run = _latent(100_000.0, 1, 0.01).model_copy(
        update={"run_id": "other-run"}
    )
    with pytest.raises(SensorModelError, match="run_id"):
        model.sample((different_run,), 1, 0.01)


def test_pending_delivery_order_is_arrival_then_source_and_sensor() -> None:
    model = SensorModel(
        "sensor-run",
        (
            SensorConfig(
                sensor_id="z-pressure",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                delay_s=0.02,
            ),
            SensorConfig(
                sensor_id="a-pressure",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                delay_s=0.02,
            ),
        ),
    )
    assert model.sample((_latent(100_000.0),), 0, 0.0) == ()
    delivered = model.release_arrived(0.02)
    assert [record.sensor_id for record in delivered] == ["a-pressure", "z-pressure"]
