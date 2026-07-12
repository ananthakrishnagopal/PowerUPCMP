# Decision: R4 causal observation delivery and executable scenarios

Date: 2026-07-11  
Status: APPROVED IMPLEMENTATION BASIS  
Gate: T-PHASE12-REMEDIATION / R4  
Owner: sole engineering agent  
User authorization: recorded in the active conversation

## Context

The Phase 1/2 audit identified that negative reported-timestamp jitter could
make `arrival_timestamp_s` earlier than the latent source state. Further code
review found two related issues:

1. delayed observations were returned from `SensorModel.sample` immediately,
   even when their stamped arrival time was in the future; and
2. the sampling boundary did not verify that supplied latent records shared
   the declared run, step, and source timestamp.

Scenario review also confirmed that zero-duration RAMP events passed validation
and failed at execution, finite STEP and PULSE events behaved identically,
target bounds were incomplete, unknown keys were ignored, overlap detection
considered equal starts rather than interval intersection, and an initiating
grid interruption was labelled `UPS_TRANSFER` (an intermediate response).

## Observation-clock decision

Every generated observation has three distinct clocks:

\[
t_{source}=t_k,
\qquad
t_{reported}=\max(0,t_{source}+\epsilon_{clock}),
\qquad
t_{arrival}=t_{source}+d_{comm},\quad d_{comm}\ge0.
\]

`observed_timestamp_s` remains the serialized field name for compatibility but
is explicitly the reported sensor-clock timestamp. A new optional
`source_timestamp_s` field is added to canonical ObservationRecord. R4-generated
records always populate it. Older v2.1 records without it may remain readable
but are not eligible for online visibility without a separately audited source
join.

Reported clock jitter never changes source generation or delivery time.
`arrival_timestamp_s >= source_timestamp_s` is enforced. Online visibility at
decision time \(t_d\) is

\[
\mathcal O(t_d)=\{o:\ t_{arrival}(o)\le t_d\}.
\]

`SensorModel.sample` therefore enqueues newly generated records and returns
only records whose arrival is no later than the current source boundary. A new
`release_arrived(decision_timestamp_s)` method releases due queued records
without requiring a new latent state. Records are ordered by arrival, source
step, sensor ID, and sample index. Source steps/timestamps and release cutoffs
must be monotone. Input latent records must match the model run ID and the
declared source boundary exactly. Packet-loss records follow the same delivery
queue and remain explicit missing observations.

This is a causal software-clock model, not a clock-synchronization protocol,
historian, or certified communication network.

## Scenario-profile decision

- `STEP`: persistent from `start_s`; requires `duration_s == 0`.
- `PULSE`: constant on the finite half-open interval
  `[start_s, start_s + duration_s)`; requires positive duration.
- `RAMP`: linear from zero to the declared magnitude over a positive finite
  duration and then inactive; allowed only for targets whose zero baseline is
  meaningful.
- `PIECEWISE_LINEAR`: positive finite duration; points must begin at relative
  time zero, end at the declared duration, be strictly time ordered, remain in
  target bounds, and end at the declared magnitude.

Dynamic profiles can no longer validate with zero duration. The library and
every mapping reject unknown keys. Library schema version `2.0.0` is explicit.

## Target contract

Each target has a frozen unit, finite range, binary flag where applicable, and
whether a zero-origin RAMP is meaningful. R4 initially supports:

| Target | Unit | Allowed range |
|---|---|---:|
| electrical.grid_voltage_delta_pu | pu | [-1.0, 0.5] |
| electrical.grid_voltage_pu | pu | [0.0, 1.5] |
| electrical.grid_frequency_delta_hz | Hz | [-50, 50] |
| electrical.force_interruption | 1 | {0,1} |
| drive.force_trip | 1 | {0,1} |
| upw.valve_position | 1 | [0,1] |
| upw.tool_demand_m3_s | m³/s | [0, 5e-4] |
| upw.inlet_temperature_k | K | [273.15, 373.15] |
| sensor.pressure.bias | Pa | [-600000, 600000] |
| sensor.pressure.packet_loss_probability | 1 | [0,1] |
| sensor.pressure.drift_per_s | Pa/s | [-100000, 100000] |

These are simulation-envelope choices, not measured fault distributions. A
future target requires a reviewed contract entry; it may not be accepted by a
generic numeric fallback.

## Overlap and cause decision

Two events overlap when their half-open active intervals intersect; persistent
STEP intervals end at infinity. Overlapping events on the same target are
rejected because implicit last-write-wins composition is forbidden. Overlapping
events with distinct initiating causes require `MULTI_LABEL_ORDERED`; ordered
causes follow event priority then declaration order.

The root-cause vocabulary is extended with initiating disturbances
`GRID_VOLTAGE_SWELL`, `GRID_INTERRUPTION`, and
`GRID_FREQUENCY_DEVIATION`. `UPS_TRANSFER` and `VFD_DERATING` remain valid
propagation/attribution states but are forbidden as declarative initiating
causes. Target/cause compatibility and voltage sign are validated. The
`ups_transfer` scenario is corrected to use `GRID_INTERRUPTION`; the simulated
UPS state may subsequently record TRANSFER.

Feature attribution or a propagation-state label is not causal proof.

## Version and impact analysis

- Canonical schema advances additively from 2.1.0 to 2.2.0 with optional
  `source_timestamp_s` and additional root-cause vocabulary. Old records remain
  parseable; online eligibility is stricter.
- Interface registry advances to 3.0.0 because `SensorModel.sample` delivery
  behavior changes and `release_arrived` is added. The overall runtime
  interface version becomes 3.0.0.
- `DynamicSubsystem` remains 2.0.0.
- `SensorModel` advances from 1.0.0 to 2.0.0.
- `Scenario` advances from 1.0.0 to 2.0.0.
- Strict default configuration, scenario library, schema implementation,
  tests, architecture, task/status records, and the living paper must be
  updated together.

## Acceptance tests

1. Negative or positive reported jitter never makes arrival earlier than
   source generation.
2. A delayed observation is not returned before its arrival cutoff and is
   released exactly once afterward.
3. Source run/step/timestamp mismatches and non-monotone calls are rejected.
4. Fixed seed/config/source history replays identical generated and delivered
   observations without mutating latent state.
5. Zero-duration dynamic profiles and nonzero-duration STEP profiles are
   rejected before replay.
6. All target endpoint and piecewise values obey declared units/ranges.
7. Unknown library/scenario/event keys and malformed piecewise points are
   rejected.
8. Same-target interval overlaps are rejected; distinct-cause overlaps require
   ordered multilabel policy even when starts differ.
9. Propagation states cannot be initiating scenario labels; target/cause/sign
   mismatches are rejected.
10. The complete scenario library validates and deterministic replay remains
    stable under the corrected initiating label.
11. Full tests, YAML/DAG, and documentation-link checks pass.

## Claims boundary

Passing R4 validates causal software visibility and declarative scenario
behavior inside the synthetic PoC. It does not establish measured sensor/network
reliability, real fault frequencies, real causal mechanisms, production timing,
physical defects, yield, or controller performance.
