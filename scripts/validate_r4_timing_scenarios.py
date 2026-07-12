#!/usr/bin/env python3
"""Generate deterministic R4 sensor-delivery and scenario audit evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from semifab_poc.config import load_runtime_config, runtime_config_sha256
from semifab_poc.data.schema import LatentStateRecord, QualityFlag
from semifab_poc.simulation.scenario import ScenarioProfile, load_scenarios
from semifab_poc.simulation.sensors import SensorConfig, SensorModel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "timing"


def _latent(step: int, timestamp_s: float) -> LatentStateRecord:
    return LatentStateRecord(
        run_id="r4-timing-audit",
        step_index=step,
        timestamp_s=timestamp_s,
        signal_id="upw.supply_pressure",
        value=300_000.0 + step,
        unit="Pa",
        subsystem="upw",
        provenance_id="synthetic-upw-conserved-v2",
    )


def sensor_delivery_trace(seed: int = 20260711) -> list[dict[str, object]]:
    model = SensorModel(
        "r4-timing-audit",
        (
            SensorConfig(
                sensor_id="pressure-audit",
                signal_id="upw.supply_pressure",
                unit="Pa",
                sample_period_s=0.01,
                provenance_id="synthetic-r4-timing-audit-v1",
                noise_std=2.0,
                delay_s=0.025,
                packet_loss_probability=0.10,
                timestamp_jitter_std_s=0.020,
            ),
        ),
    )
    model.reset(seed)
    rows: list[dict[str, object]] = []
    for step in range(101):
        timestamp_s = step * 0.01
        arrived = model.sample((_latent(step, timestamp_s),), step, timestamp_s)
        for record in arrived:
            rows.append(
                {
                    "release_cutoff_s": timestamp_s,
                    "sample_index": record.sample_index,
                    "source_step_index": record.source_step_index,
                    "source_timestamp_s": record.source_timestamp_s,
                    "reported_timestamp_s": record.observed_timestamp_s,
                    "arrival_timestamp_s": record.arrival_timestamp_s,
                    "arrival_minus_source_s": (
                        record.arrival_timestamp_s - float(record.source_timestamp_s)
                    ),
                    "reported_minus_source_s": (
                        record.observed_timestamp_s - float(record.source_timestamp_s)
                    ),
                    "released_before_arrival": (
                        timestamp_s + 1.0e-12 < record.arrival_timestamp_s
                    ),
                    "missing": QualityFlag.MISSING in record.quality_flags,
                    "quality_flags": "|".join(flag.value for flag in record.quality_flags),
                    "value": record.value,
                }
            )
    final_cutoff = 1.025
    for record in model.release_arrived(final_cutoff):
        rows.append(
            {
                "release_cutoff_s": final_cutoff,
                "sample_index": record.sample_index,
                "source_step_index": record.source_step_index,
                "source_timestamp_s": record.source_timestamp_s,
                "reported_timestamp_s": record.observed_timestamp_s,
                "arrival_timestamp_s": record.arrival_timestamp_s,
                "arrival_minus_source_s": (
                    record.arrival_timestamp_s - float(record.source_timestamp_s)
                ),
                "reported_minus_source_s": (
                    record.observed_timestamp_s - float(record.source_timestamp_s)
                ),
                "released_before_arrival": (
                    final_cutoff + 1.0e-12 < record.arrival_timestamp_s
                ),
                "missing": QualityFlag.MISSING in record.quality_flags,
                "quality_flags": "|".join(flag.value for flag in record.quality_flags),
                "value": record.value,
            }
        )
    if model.pending_count:
        raise RuntimeError("R4 audit did not drain the delivery queue")
    return rows


def scenario_audit() -> dict[str, object]:
    path = ROOT / "configs" / "scenarios" / "library.yaml"
    scenarios = load_scenarios(path)
    profile_counts = {profile.value: 0 for profile in ScenarioProfile}
    events = []
    overlap_pairs = []
    for scenario in scenarios.values():
        for event in scenario.events:
            profile_counts[event.profile.value] += 1
            events.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "event_id": event.event_id,
                    "target": event.target,
                    "profile": event.profile.value,
                    "start_s": event.start_s,
                    "end_s": None if event.end_s == float("inf") else event.end_s,
                    "initiating_cause": event.initiating_cause.value,
                }
            )
        for index, event in enumerate(scenario.events):
            for other in scenario.events[index + 1 :]:
                if event.overlaps(other):
                    overlap_pairs.append(
                        {
                            "scenario_id": scenario.scenario_id,
                            "left_event": event.event_id,
                            "right_event": other.event_id,
                            "same_target": event.target == other.target,
                            "causes": [
                                event.initiating_cause.value,
                                other.initiating_cause.value,
                            ],
                            "policy": scenario.compound_cause_policy,
                        }
                    )

    replay_rows = []
    replay_times = (0.0, 0.5, 1.0, 1.05, 1.10, 1.25, 1.50, 2.0, 5.0, 10.5)
    for scenario in scenarios.values():
        for time_s in replay_times:
            replay_rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "time_s": time_s,
                    "values": [
                        {
                            "event_id": event.event_id,
                            "value": value,
                            "cause": event.initiating_cause.value,
                        }
                        for event, value in scenario.values_at(time_s)
                    ],
                }
            )
    replay_payload = json.dumps(
        replay_rows,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "library_path": str(path.relative_to(ROOT)),
        "library_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "scenario_schema_version": "2.0.0",
        "scenario_count": len(scenarios),
        "event_count": len(events),
        "profile_counts": profile_counts,
        "events": events,
        "overlap_pairs": overlap_pairs,
        "same_target_overlap_count": sum(pair["same_target"] for pair in overlap_pairs),
        "propagation_state_as_initiating_cause_count": sum(
            event["initiating_cause"] in {"UPS_TRANSFER", "VFD_DERATING"}
            for event in events
        ),
        "replay_time_grid_s": list(replay_times),
        "replay_sha256": hashlib.sha256(replay_payload).hexdigest(),
    }


def write_csv_atomic(path: Path, rows: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> int:
    config = load_runtime_config(ROOT / "configs" / "checkpoints" / "r4_default.yaml")
    first_trace = sensor_delivery_trace()
    second_trace = sensor_delivery_trace()
    if first_trace != second_trace:
        raise RuntimeError("fixed-seed R4 sensor replay is not deterministic")
    if len(first_trace) != 101:
        raise RuntimeError("R4 audit did not release every generated sample exactly once")

    report = {
        "report_id": "R4_ONLINE_SCENARIO_TIMING_VALIDATION_V1",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "real_network_or_fault_frequency_validation": False,
        "schema_version": config.schema_version,
        "interface_version": config.interface_version,
        "default_config_sha256": runtime_config_sha256(config),
        "sensor_delivery": {
            "seed": 20260711,
            "generated_and_released_count": len(first_trace),
            "unique_sample_index_count": len(
                {int(row["sample_index"]) for row in first_trace}
            ),
            "missing_record_count": sum(bool(row["missing"]) for row in first_trace),
            "reported_before_source_count": sum(
                float(row["reported_minus_source_s"]) < 0.0 for row in first_trace
            ),
            "reported_after_source_count": sum(
                float(row["reported_minus_source_s"]) > 0.0 for row in first_trace
            ),
            "minimum_arrival_minus_source_s": min(
                float(row["arrival_minus_source_s"]) for row in first_trace
            ),
            "maximum_arrival_minus_source_s": max(
                float(row["arrival_minus_source_s"]) for row in first_trace
            ),
            "released_before_arrival_count": sum(
                bool(row["released_before_arrival"]) for row in first_trace
            ),
            "deterministic_replay_equal": True,
            "pending_after_final_drain": 0,
        },
        "scenarios": scenario_audit(),
    }
    if report["sensor_delivery"]["released_before_arrival_count"] != 0:
        raise RuntimeError("R4 audit observed early delivery")
    if report["scenarios"]["same_target_overlap_count"] != 0:
        raise RuntimeError("scenario library contains same-target overlap")
    if report["scenarios"]["propagation_state_as_initiating_cause_count"] != 0:
        raise RuntimeError("scenario library uses a propagation state as initiating cause")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "r4_validation.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(report_path)
    trace_path = OUTPUT_DIR / "r4_sensor_delivery_trace.csv"
    write_csv_atomic(trace_path, first_trace)
    print(
        json.dumps(
            {
                "report": str(report_path.relative_to(ROOT)),
                "trace": str(trace_path.relative_to(ROOT)),
                **report["sensor_delivery"],
                "scenario_count": report["scenarios"]["scenario_count"],
                "event_count": report["scenarios"]["event_count"],
                "scenario_replay_sha256": report["scenarios"]["replay_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
