"""Deterministic sensor and communication corruption for latent simulator records.

This module creates canonical observation records only. It never mutates or
returns latent physical-state records.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

from semifab_poc.data.schema import (
    DataOrigin,
    LatentStateRecord,
    ObservationRecord,
    QualityFlag,
)


class SensorModelError(ValueError):
    """Raised when sensor configuration or sampling input is invalid."""


@dataclass(frozen=True)
class SensorConfig:
    sensor_id: str
    signal_id: str
    unit: str
    sample_period_s: float
    provenance_id: str = "synthetic-sensor-v1"
    noise_std: float = 0.0
    bias: float = 0.0
    drift_per_s: float = 0.0
    quantization_step: float | None = None
    delay_s: float = 0.0
    packet_loss_probability: float = 0.0
    stuck_probability: float = 0.0
    timestamp_jitter_std_s: float = 0.0
    minimum_value: float | None = None
    maximum_value: float | None = None

    def validate(self) -> None:
        if not self.sensor_id or not self.signal_id or not self.unit:
            raise SensorModelError("sensor_id, signal_id, and unit must be non-empty")
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise SensorModelError("provenance_id must be a non-empty string")
        positive = {"sample_period_s": self.sample_period_s}
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise SensorModelError(f"{name} must be finite and positive")
        nonnegative = {
            "noise_std": self.noise_std,
            "delay_s": self.delay_s,
            "timestamp_jitter_std_s": self.timestamp_jitter_std_s,
        }
        for name, value in nonnegative.items():
            if not math.isfinite(value) or value < 0.0:
                raise SensorModelError(f"{name} must be finite and non-negative")
        for name, value in {
            "bias": self.bias,
            "drift_per_s": self.drift_per_s,
        }.items():
            if not math.isfinite(value):
                raise SensorModelError(f"{name} must be finite")
        if self.quantization_step is not None and (
            not math.isfinite(self.quantization_step) or self.quantization_step <= 0.0
        ):
            raise SensorModelError("quantization_step must be finite and positive when configured")
        for name, value in {
            "packet_loss_probability": self.packet_loss_probability,
            "stuck_probability": self.stuck_probability,
        }.items():
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise SensorModelError(f"{name} must be within [0, 1]")
        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.minimum_value > self.maximum_value
        ):
            raise SensorModelError("minimum_value cannot exceed maximum_value")


@dataclass
class _SensorRuntime:
    next_sample_timestamp_s: float | None = None
    sample_index: int = 0
    stuck_value: float | str | bool | None = None
    is_stuck: bool = False


class SensorModel:
    """Seeded causal sensor sampler with queued communication delivery."""

    interface_version = "2.0.0"

    def __init__(self, run_id: str, configurations: Sequence[SensorConfig]) -> None:
        if not run_id:
            raise SensorModelError("run_id must be non-empty")
        if not configurations:
            raise SensorModelError("at least one sensor configuration is required")
        self.run_id = run_id
        self.configurations = tuple(sorted(configurations, key=lambda item: item.sensor_id))
        if len({config.sensor_id for config in self.configurations}) != len(self.configurations):
            raise SensorModelError("sensor IDs must be unique")
        for config in self.configurations:
            config.validate()
        self._rng = random.Random()
        self._runtime: dict[str, _SensorRuntime] = {}
        self._pending: list[ObservationRecord] = []
        self._last_source_step_index: int | None = None
        self._last_source_timestamp_s: float | None = None
        self._last_release_cutoff_s: float = 0.0
        self.reset(seed=0)

    def reset(self, seed: int, config: object | None = None) -> None:
        """Reset stochastic and per-sensor communication state for deterministic replay."""

        del config
        if not isinstance(seed, int) or seed < 0:
            raise SensorModelError("seed must be a non-negative integer")
        self._rng = random.Random(seed)
        self._runtime = {item.sensor_id: _SensorRuntime() for item in self.configurations}
        self._pending = []
        self._last_source_step_index = None
        self._last_source_timestamp_s = None
        self._last_release_cutoff_s = 0.0

    @property
    def pending_count(self) -> int:
        """Number of generated observations not yet visible by arrival time."""

        return len(self._pending)

    def sample(
        self,
        state: Sequence[LatentStateRecord],
        step_index: int,
        timestamp_s: float,
    ) -> tuple[ObservationRecord, ...]:
        """Generate due samples and return only records arrived by this boundary."""

        if step_index < 0 or not math.isfinite(timestamp_s) or timestamp_s < 0.0:
            raise SensorModelError("step_index and timestamp_s must be non-negative and finite")
        if self._last_source_step_index is not None and step_index <= self._last_source_step_index:
            raise SensorModelError("source step indices must be strictly increasing")
        if (
            self._last_source_timestamp_s is not None
            and timestamp_s <= self._last_source_timestamp_s + 1.0e-12
        ):
            raise SensorModelError("source timestamps must be strictly increasing")
        if timestamp_s + 1.0e-12 < self._last_release_cutoff_s:
            raise SensorModelError("source time cannot precede an already released decision cutoff")
        latent_by_signal = {record.signal_id: record for record in state}
        if len(latent_by_signal) != len(state):
            raise SensorModelError("latent records must have unique signal IDs per sample")
        for record in state:
            if record.run_id != self.run_id:
                raise SensorModelError("latent record run_id must match the sensor model run")
            if record.step_index != step_index:
                raise SensorModelError("latent record step index must match the source boundary")
            if not math.isclose(
                record.timestamp_s,
                timestamp_s,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise SensorModelError("latent record timestamp must match the source boundary")
        observations: list[ObservationRecord] = []
        for config in self.configurations:
            record = latent_by_signal.get(config.signal_id)
            if record is None:
                raise SensorModelError(f"missing latent record for {config.signal_id}")
            if record.unit != config.unit:
                raise SensorModelError(f"unit mismatch for {config.signal_id}")
            runtime = self._runtime[config.sensor_id]
            if runtime.next_sample_timestamp_s is None:
                runtime.next_sample_timestamp_s = timestamp_s
            if timestamp_s + 1.0e-12 < runtime.next_sample_timestamp_s:
                continue
            while runtime.next_sample_timestamp_s <= timestamp_s + 1.0e-12:
                runtime.next_sample_timestamp_s += config.sample_period_s
            observations.append(self._sample_one(config, runtime, record, step_index, timestamp_s))
        self._pending.extend(observations)
        self._last_source_step_index = step_index
        self._last_source_timestamp_s = timestamp_s
        return self.release_arrived(timestamp_s)

    def release_arrived(self, decision_timestamp_s: float) -> tuple[ObservationRecord, ...]:
        """Release queued observations visible by a monotone decision cutoff."""

        if not math.isfinite(decision_timestamp_s) or decision_timestamp_s < 0.0:
            raise SensorModelError("decision timestamp must be finite and non-negative")
        if decision_timestamp_s + 1.0e-12 < self._last_release_cutoff_s:
            raise SensorModelError("decision cutoffs must be monotone")
        arrived = [
            record
            for record in self._pending
            if record.arrival_timestamp_s <= decision_timestamp_s + 1.0e-12
        ]
        self._pending = [
            record
            for record in self._pending
            if record.arrival_timestamp_s > decision_timestamp_s + 1.0e-12
        ]
        self._last_release_cutoff_s = decision_timestamp_s
        return tuple(
            sorted(
                arrived,
                key=lambda record: (
                    record.arrival_timestamp_s,
                    -1 if record.source_step_index is None else record.source_step_index,
                    record.sensor_id,
                    record.sample_index,
                ),
            )
        )

    def _sample_one(
        self,
        config: SensorConfig,
        runtime: _SensorRuntime,
        record: LatentStateRecord,
        step_index: int,
        timestamp_s: float,
    ) -> ObservationRecord:
        jitter = self._rng.gauss(0.0, config.timestamp_jitter_std_s) if config.timestamp_jitter_std_s else 0.0
        observed_timestamp = max(0.0, timestamp_s + jitter)
        flags: list[QualityFlag] = []
        if config.timestamp_jitter_std_s:
            flags.append(QualityFlag.TIMESTAMP_JITTERED)
        if config.delay_s:
            flags.append(QualityFlag.DELAYED)
        if self._rng.random() < config.packet_loss_probability:
            flags.extend((QualityFlag.MISSING, QualityFlag.DROPPED))
            observation = ObservationRecord(
                run_id=self.run_id,
                sample_index=runtime.sample_index,
                source_step_index=step_index,
                source_timestamp_s=timestamp_s,
                observed_timestamp_s=observed_timestamp,
                arrival_timestamp_s=timestamp_s + config.delay_s,
                sensor_id=config.sensor_id,
                signal_id=config.signal_id,
                value=None,
                unit=config.unit,
                quality_flags=tuple(flags),
                uncertainty_std=config.noise_std,
                data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
            )
            runtime.sample_index += 1
            return observation

        value = self._corrupt_value(config, runtime, record.value, timestamp_s, flags)
        if not flags:
            flags.append(QualityFlag.VALID)
        observation = ObservationRecord(
            run_id=self.run_id,
            sample_index=runtime.sample_index,
            source_step_index=step_index,
            source_timestamp_s=timestamp_s,
            observed_timestamp_s=observed_timestamp,
            arrival_timestamp_s=timestamp_s + config.delay_s,
            sensor_id=config.sensor_id,
            signal_id=config.signal_id,
            value=value,
            unit=config.unit,
            quality_flags=tuple(flags),
            uncertainty_std=config.noise_std,
            data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
        )
        runtime.sample_index += 1
        return observation

    def _corrupt_value(
        self,
        config: SensorConfig,
        runtime: _SensorRuntime,
        latent_value: float | str | bool,
        timestamp_s: float,
        flags: list[QualityFlag],
    ) -> float | str | bool:
        if runtime.is_stuck:
            flags.append(QualityFlag.STUCK)
            assert runtime.stuck_value is not None
            return runtime.stuck_value
        if isinstance(latent_value, bool) or isinstance(latent_value, str):
            if any(
                value != 0.0
                for value in (config.noise_std, config.bias, config.drift_per_s)
            ) or config.quantization_step is not None:
                raise SensorModelError("numeric corruptions require a numeric latent signal")
            value: float | str | bool = latent_value
        else:
            value = float(latent_value)
            if config.noise_std:
                value += self._rng.gauss(0.0, config.noise_std)
            if config.bias:
                value += config.bias
                flags.append(QualityFlag.BIASED)
            if config.drift_per_s:
                value += config.drift_per_s * timestamp_s
                flags.append(QualityFlag.DRIFTING)
            if config.quantization_step is not None:
                value = round(value / config.quantization_step) * config.quantization_step
                flags.append(QualityFlag.QUANTISED)
            if config.minimum_value is not None and value < config.minimum_value:
                value = config.minimum_value
                flags.append(QualityFlag.OUT_OF_RANGE)
            if config.maximum_value is not None and value > config.maximum_value:
                value = config.maximum_value
                flags.append(QualityFlag.OUT_OF_RANGE)
        if self._rng.random() < config.stuck_probability:
            runtime.is_stuck = True
            runtime.stuck_value = value
            flags.append(QualityFlag.STUCK)
        return value
