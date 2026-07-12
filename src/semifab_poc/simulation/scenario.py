"""Strict declarative scenarios with executable profile and cause semantics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from semifab_poc.data.schema import RootCause


class ScenarioError(ValueError):
    """Raised when a declarative scenario violates its deterministic contract."""


class ScenarioProfile(str, Enum):
    STEP = "STEP"
    RAMP = "RAMP"
    PULSE = "PULSE"
    PIECEWISE_LINEAR = "PIECEWISE_LINEAR"


@dataclass(frozen=True)
class _TargetSpec:
    unit: str
    minimum: float
    maximum: float
    binary: bool = False
    ramp_from_zero_allowed: bool = False


_TARGET_SPECS: dict[str, _TargetSpec] = {
    "electrical.grid_voltage_delta_pu": _TargetSpec("pu", -1.0, 0.5, ramp_from_zero_allowed=True),
    "electrical.grid_voltage_pu": _TargetSpec("pu", 0.0, 1.5),
    "electrical.grid_frequency_delta_hz": _TargetSpec(
        "Hz", -50.0, 50.0, ramp_from_zero_allowed=True
    ),
    "electrical.force_interruption": _TargetSpec("1", 0.0, 1.0, binary=True),
    "drive.force_trip": _TargetSpec("1", 0.0, 1.0, binary=True),
    "upw.valve_position": _TargetSpec("1", 0.0, 1.0),
    "upw.tool_demand_m3_s": _TargetSpec("m^3/s", 0.0, 5.0e-4),
    "upw.inlet_temperature_k": _TargetSpec("K", 273.15, 373.15),
    "sensor.pressure.bias": _TargetSpec("Pa", -600_000.0, 600_000.0),
    "sensor.pressure.packet_loss_probability": _TargetSpec("1", 0.0, 1.0),
    "sensor.pressure.drift_per_s": _TargetSpec(
        "Pa/s", -100_000.0, 100_000.0, ramp_from_zero_allowed=True
    ),
}

_TARGET_CAUSES: dict[str, frozenset[RootCause]] = {
    "electrical.grid_voltage_delta_pu": frozenset(
        {RootCause.GRID_VOLTAGE_SAG, RootCause.GRID_VOLTAGE_SWELL}
    ),
    "electrical.grid_voltage_pu": frozenset(
        {RootCause.GRID_VOLTAGE_SAG, RootCause.GRID_VOLTAGE_SWELL}
    ),
    "electrical.grid_frequency_delta_hz": frozenset(
        {RootCause.GRID_FREQUENCY_DEVIATION}
    ),
    "electrical.force_interruption": frozenset({RootCause.GRID_INTERRUPTION}),
    "drive.force_trip": frozenset({RootCause.PUMP_TRIP}),
    "upw.valve_position": frozenset({RootCause.VALVE_RESTRICTION}),
    "upw.tool_demand_m3_s": frozenset({RootCause.TOOL_DEMAND_SPIKE}),
    "upw.inlet_temperature_k": frozenset({RootCause.THERMAL_EXCURSION}),
    "sensor.pressure.bias": frozenset({RootCause.PRESSURE_SENSOR_FAULT}),
    "sensor.pressure.packet_loss_probability": frozenset(
        {RootCause.PRESSURE_SENSOR_FAULT}
    ),
    "sensor.pressure.drift_per_s": frozenset({RootCause.PRESSURE_SENSOR_FAULT}),
}

_PROPAGATION_ONLY_CAUSES = frozenset({RootCause.UPS_TRANSFER, RootCause.VFD_DERATING})
_SCENARIO_SCHEMA_VERSION = "2.0.0"
_SCENARIO_KEYS = frozenset(
    {"schema_version", "scenario_id", "description", "events", "seed", "compound_cause_policy"}
)
_EVENT_KEYS = frozenset(
    {
        "event_id",
        "event_type",
        "start_s",
        "duration_s",
        "priority",
        "target",
        "profile",
        "magnitude",
        "unit",
        "initiating_cause",
        "piecewise_points",
    }
)


def _validate_target_value(target: str, value: float, label: str) -> None:
    spec = _TARGET_SPECS[target]
    if not math.isfinite(value):
        raise ScenarioError(f"{label} must be finite")
    if not spec.minimum <= value <= spec.maximum:
        raise ScenarioError(
            f"{target} {label} must be within [{spec.minimum}, {spec.maximum}]"
        )
    if spec.binary and value not in (0.0, 1.0):
        raise ScenarioError(f"{target} {label} must be binary 0 or 1")


@dataclass(frozen=True)
class ScenarioEvent:
    scenario_id: str
    event_id: str
    event_type: str
    start_s: float
    duration_s: float
    priority: int
    target: str
    profile: ScenarioProfile
    magnitude: float
    unit: str
    initiating_cause: RootCause
    declaration_order: int
    piecewise_points: tuple[tuple[float, float], ...] = ()

    @property
    def end_s(self) -> float:
        return math.inf if self.profile is ScenarioProfile.STEP else self.start_s + self.duration_s

    def overlaps(self, other: ScenarioEvent) -> bool:
        return max(self.start_s, other.start_s) < min(self.end_s, other.end_s)

    def _cause_values(self) -> tuple[float, ...]:
        if self.profile is ScenarioProfile.PIECEWISE_LINEAR:
            return tuple(value for _, value in self.piecewise_points)
        return (self.magnitude,)

    def _validate_initiating_cause(self) -> None:
        if self.initiating_cause in _PROPAGATION_ONLY_CAUSES:
            raise ScenarioError(
                f"{self.initiating_cause.value} is a propagation state, not an initiating disturbance"
            )
        allowed = _TARGET_CAUSES[self.target]
        if self.initiating_cause not in allowed:
            raise ScenarioError(
                f"{self.initiating_cause.value} is incompatible with target {self.target}"
            )
        values = self._cause_values()
        if self.target == "electrical.grid_voltage_delta_pu":
            nonzero = tuple(value for value in values if value != 0.0)
            if not nonzero:
                raise ScenarioError("grid-voltage delta disturbance must contain a nonzero value")
            expected = (
                RootCause.GRID_VOLTAGE_SAG
                if all(value < 0.0 for value in nonzero)
                else RootCause.GRID_VOLTAGE_SWELL
                if all(value > 0.0 for value in nonzero)
                else None
            )
            if expected is None:
                raise ScenarioError("one voltage-delta event cannot mix sag and swell values")
            if self.initiating_cause is not expected:
                raise ScenarioError("grid-voltage delta sign does not match initiating cause")
        elif self.target == "electrical.grid_voltage_pu":
            deviations = tuple(value - 1.0 for value in values if value != 1.0)
            if not deviations:
                raise ScenarioError("absolute grid-voltage disturbance must be non-nominal")
            expected = (
                RootCause.GRID_VOLTAGE_SAG
                if all(value < 0.0 for value in deviations)
                else RootCause.GRID_VOLTAGE_SWELL
                if all(value > 0.0 for value in deviations)
                else None
            )
            if expected is None or self.initiating_cause is not expected:
                raise ScenarioError("absolute grid-voltage values do not match one initiating cause")

    def validate(self) -> None:
        if not self.scenario_id or not self.event_id or not self.event_type:
            raise ScenarioError("scenario_id, event_id, and event_type must be non-empty")
        if not math.isfinite(self.start_s) or self.start_s < 0.0:
            raise ScenarioError("event start_s must be finite and non-negative")
        if not math.isfinite(self.duration_s) or self.duration_s < 0.0:
            raise ScenarioError("event duration_s must be finite and non-negative")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise ScenarioError("event priority must be an integer")
        if self.declaration_order < 0:
            raise ScenarioError("declaration_order must be non-negative")
        spec = _TARGET_SPECS.get(self.target)
        if spec is None:
            raise ScenarioError(f"unknown scenario target: {self.target}")
        if self.unit != spec.unit:
            raise ScenarioError(f"{self.target} requires unit {spec.unit}, got {self.unit}")
        if self.profile is ScenarioProfile.STEP:
            if self.duration_s != 0.0:
                raise ScenarioError("persistent STEP events require duration_s == 0")
        elif self.duration_s <= 0.0:
            raise ScenarioError(f"{self.profile.value} events require positive duration_s")
        if self.profile is ScenarioProfile.RAMP and not spec.ramp_from_zero_allowed:
            raise ScenarioError(f"zero-origin RAMP is not meaningful for target {self.target}")
        _validate_target_value(self.target, self.magnitude, "magnitude")

        if self.profile is ScenarioProfile.PIECEWISE_LINEAR:
            if len(self.piecewise_points) < 2:
                raise ScenarioError("piecewise-linear events require at least two points")
            if self.piecewise_points[0][0] != 0.0:
                raise ScenarioError("piecewise-linear points must start at relative time zero")
            if self.piecewise_points[-1][0] != self.duration_s:
                raise ScenarioError("piecewise-linear points must end at event duration")
            previous_time = -1.0
            for relative_time, value in self.piecewise_points:
                if not math.isfinite(relative_time) or relative_time < 0.0:
                    raise ScenarioError("piecewise point times must be finite and non-negative")
                if relative_time <= previous_time:
                    raise ScenarioError("piecewise point times must be strictly increasing")
                _validate_target_value(self.target, value, "piecewise value")
                previous_time = relative_time
            if not math.isclose(
                self.piecewise_points[-1][1],
                self.magnitude,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ScenarioError("piecewise final value must equal declared magnitude")
        elif self.piecewise_points:
            raise ScenarioError("piecewise_points are allowed only for PIECEWISE_LINEAR")
        self._validate_initiating_cause()

    def active_at(self, time_s: float) -> bool:
        if self.profile is ScenarioProfile.STEP:
            return time_s >= self.start_s
        return self.start_s <= time_s < self.end_s

    def value_at(self, time_s: float) -> float:
        if not self.active_at(time_s):
            raise ScenarioError("event value requested while event is inactive")
        if self.profile in (ScenarioProfile.STEP, ScenarioProfile.PULSE):
            return self.magnitude
        relative_time = time_s - self.start_s
        if self.profile is ScenarioProfile.RAMP:
            return self.magnitude * (relative_time / self.duration_s)
        points = self.piecewise_points
        if relative_time <= points[0][0]:
            return points[0][1]
        for left, right in zip(points, points[1:]):
            if left[0] <= relative_time <= right[0]:
                fraction = (relative_time - left[0]) / (right[0] - left[0])
                return left[1] + fraction * (right[1] - left[1])
        return points[-1][1]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    schema_version: str
    events: tuple[ScenarioEvent, ...] = ()
    seed: int = 0
    compound_cause_policy: str = "SINGLE_EVENT"

    interface_version = "2.0.0"

    def validate(self) -> None:
        if not self.scenario_id or not self.description:
            raise ScenarioError("scenario_id and description must be non-empty")
        if self.schema_version != _SCENARIO_SCHEMA_VERSION:
            raise ScenarioError(
                f"scenario schema_version must be {_SCENARIO_SCHEMA_VERSION}"
            )
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ScenarioError("scenario seed must be a non-negative integer")
        if self.compound_cause_policy not in {"SINGLE_EVENT", "MULTI_LABEL_ORDERED"}:
            raise ScenarioError(
                "compound_cause_policy must be SINGLE_EVENT or MULTI_LABEL_ORDERED"
            )
        event_ids: set[str] = set()
        for event in self.events:
            event.validate()
            if event.scenario_id != self.scenario_id:
                raise ScenarioError("event scenario_id must match its scenario")
            if event.event_id in event_ids:
                raise ScenarioError("event IDs must be unique within a scenario")
            event_ids.add(event.event_id)

        for index, event in enumerate(self.events):
            for other in self.events[index + 1 :]:
                if not event.overlaps(other):
                    continue
                if event.target == other.target:
                    raise ScenarioError("overlapping events on the same target are forbidden")
                if (
                    event.initiating_cause is not other.initiating_cause
                    and self.compound_cause_policy != "MULTI_LABEL_ORDERED"
                ):
                    raise ScenarioError(
                        "overlapping multi-cause events require MULTI_LABEL_ORDERED policy"
                    )

    def events_at(self, time_s: float) -> tuple[ScenarioEvent, ...]:
        if not math.isfinite(time_s) or time_s < 0.0:
            raise ScenarioError("time_s must be finite and non-negative")
        return tuple(
            sorted(
                (event for event in self.events if event.active_at(time_s)),
                key=lambda event: (event.priority, event.declaration_order, event.event_id),
            )
        )

    def values_at(self, time_s: float) -> tuple[tuple[ScenarioEvent, float], ...]:
        return tuple((event, event.value_at(time_s)) for event in self.events_at(time_s))

    def initiating_causes_at(self, time_s: float) -> tuple[RootCause, ...]:
        causes: list[RootCause] = []
        for event in self.events_at(time_s):
            if event.initiating_cause not in causes:
                causes.append(event.initiating_cause)
        return tuple(causes)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        schema_version: str | None = None,
    ) -> Scenario:
        unknown = set(raw) - _SCENARIO_KEYS
        if unknown:
            raise ScenarioError(f"unknown scenario keys: {sorted(unknown)}")
        try:
            scenario_id = str(raw["scenario_id"])
            description = str(raw["description"])
            declared_schema = str(raw.get("schema_version", schema_version))
        except KeyError as exc:
            raise ScenarioError(f"scenario missing required field: {exc.args[0]}") from exc
        if declared_schema == "None":
            raise ScenarioError("scenario schema_version is required")
        if schema_version is not None and declared_schema != schema_version:
            raise ScenarioError("scenario schema version conflicts with library version")

        raw_events = raw.get("events", ())
        if isinstance(raw_events, (str, bytes)) or not isinstance(raw_events, Sequence):
            raise ScenarioError("scenario events must be a sequence")
        events: list[ScenarioEvent] = []
        for declaration_order, item in enumerate(raw_events):
            if not isinstance(item, Mapping):
                raise ScenarioError("scenario events must be mappings")
            unknown_event = set(item) - _EVENT_KEYS
            if unknown_event:
                raise ScenarioError(f"unknown event keys: {sorted(unknown_event)}")
            raw_points = item.get("piecewise_points", ())
            if isinstance(raw_points, (str, bytes)) or not isinstance(raw_points, Sequence):
                raise ScenarioError("piecewise_points must be a sequence of pairs")
            points: list[tuple[float, float]] = []
            for point in raw_points:
                if (
                    isinstance(point, (str, bytes))
                    or not isinstance(point, Sequence)
                    or len(point) != 2
                ):
                    raise ScenarioError("each piecewise point must contain exactly time and value")
                try:
                    points.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError) as exc:
                    raise ScenarioError("piecewise point values must be numeric") from exc
            try:
                event = ScenarioEvent(
                    scenario_id=scenario_id,
                    event_id=str(item["event_id"]),
                    event_type=str(item["event_type"]),
                    start_s=float(item["start_s"]),
                    duration_s=float(item["duration_s"]),
                    priority=int(item.get("priority", 100)),
                    target=str(item["target"]),
                    profile=ScenarioProfile(str(item["profile"])),
                    magnitude=float(item["magnitude"]),
                    unit=str(item["unit"]),
                    initiating_cause=RootCause(str(item["initiating_cause"])),
                    declaration_order=declaration_order,
                    piecewise_points=tuple(points),
                )
            except KeyError as exc:
                raise ScenarioError(f"event missing required field: {exc.args[0]}") from exc
            except (TypeError, ValueError) as exc:
                raise ScenarioError(f"invalid event field: {exc}") from exc
            events.append(event)
        try:
            scenario = cls(
                scenario_id=scenario_id,
                description=description,
                schema_version=declared_schema,
                events=tuple(events),
                seed=int(raw.get("seed", 0)),
                compound_cause_policy=str(
                    raw.get("compound_cause_policy", "SINGLE_EVENT")
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ScenarioError(f"invalid scenario field: {exc}") from exc
        scenario.validate()
        return scenario


def load_scenarios(path: Path) -> dict[str, Scenario]:
    """Load and strictly validate a versioned scenario-library YAML file."""

    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, Mapping):
        raise ScenarioError("scenario library root must be a mapping")
    unknown = set(raw) - {"schema_version", "scenarios"}
    if unknown:
        raise ScenarioError(f"unknown scenario-library keys: {sorted(unknown)}")
    if str(raw.get("schema_version")) != _SCENARIO_SCHEMA_VERSION:
        raise ScenarioError(
            f"scenario library schema_version must be {_SCENARIO_SCHEMA_VERSION}"
        )
    raw_scenarios = raw.get("scenarios")
    if isinstance(raw_scenarios, (str, bytes)) or not isinstance(raw_scenarios, Sequence):
        raise ScenarioError("scenario library must contain a scenarios sequence")
    scenarios: list[Scenario] = []
    for item in raw_scenarios:
        if not isinstance(item, Mapping):
            raise ScenarioError("scenarios must be mappings")
        scenarios.append(
            Scenario.from_mapping(item, schema_version=_SCENARIO_SCHEMA_VERSION)
        )
    if len({scenario.scenario_id for scenario in scenarios}) != len(scenarios):
        raise ScenarioError("scenario IDs must be unique")
    return {scenario.scenario_id: scenario for scenario in scenarios}
