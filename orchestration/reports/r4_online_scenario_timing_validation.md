# R4 online and scenario-timing validation

Date: 2026-07-11  
Gate: T-PHASE12-REMEDIATION / R4  
Environment: conda `devkki`  
Decision basis: `orchestration/decisions/r4_online_scenario_timing.md`

## Outcome

R4 is **VALIDATED for the synthetic PoC**. Observation generation, reported
sensor time, communication arrival, online delivery, declarative profiles,
target bounds, interval overlap, and initiating-cause semantics satisfy the
approved causal contracts. Canonical schema 2.2.0 and interface registry 3.0.0
are frozen. `DynamicSubsystem` remains 2.0.0; `SensorModel` and `Scenario` are
2.0.0.

This validates software timing and scenario behavior inside the simulator. It
does not validate a physical sensor, network, clock protocol, fault rate,
real-fab causal mechanism, production response, MRR model, or controller.

## Observation timing and visibility

R4 distinguishes

\[
t_{source}=t_k,
\qquad
t_{reported}=\max(0,t_{source}+\epsilon_{clock}),
\qquad
t_{arrival}=t_{source}+d_{comm}.
\]

`observed_timestamp_s` is retained as the serialized name of
\(t_{reported}\); R4-generated records also carry `source_timestamp_s`.
Negative or positive clock jitter cannot change source generation or arrival.
The canonical record rejects \(t_{arrival}<t_{source}\).

New samples enter a private delivery queue. `SensorModel.sample` returns only
records satisfying

\[
t_{arrival}\le t_{source,current},
\]

and `release_arrived(t_d)` returns only queued records with
\(t_{arrival}\le t_d\). Each record is removed on release, so delivery is at
most once. Output ordering is arrival time, source step, sensor ID, then sample
index. Source run ID, step, and timestamp must match the supplied latent
boundary, and source/release calls must be monotone.

The machine-readable audit in `reports/timing/r4_validation.json` generated
101 pressure samples at 10 ms intervals with 20 ms Gaussian reported-clock
jitter, 25 ms communication delay, 10% packet-loss probability, and seed
20260711. Results:

- 101 generated and 101 released sample indices;
- 10 explicit missing/dropped observation records;
- 49 reported timestamps earlier than source and 51 later than source;
- arrival-minus-source from 0.02499999999999991 to
  0.025000000000000022 s (floating-point representation of 25 ms);
- zero records released before arrival;
- zero records pending after the final drain; and
- two complete fixed-seed replays exactly equal.

The 101-row evidence trace is
`reports/timing/r4_sensor_delivery_trace.csv`.

## Executable scenario semantics

Scenario-library schema 2.0.0 defines:

- persistent `STEP` with exactly zero duration;
- finite positive-duration half-open `PULSE`;
- finite positive-duration zero-origin `RAMP` only for compatible targets; and
- finite positive-duration `PIECEWISE_LINEAR` with exact start/end points,
  strictly increasing times, bounded values, and final value equal to the
  declared magnitude.

Unknown library/scenario/event keys are rejected. All endpoint and piecewise
values use a target-specific unit and range. Same-target overlaps are forbidden.
Distinct initiating causes with intersecting active intervals require
`MULTI_LABEL_ORDERED`, even when start times differ.

The corrected library contains 14 scenario families and 14 events: 13 PULSE
and one RAMP. Its only overlap is `compound-sag` with `compound-demand`; they
have different targets and the declared ordered multilabel policy. There are:

- zero same-target overlaps;
- zero propagation states used as initiating causes; and
- one intentional ordered two-cause overlap.

The short-interruption scenario now has initiating cause `GRID_INTERRUPTION`.
`UPS_TRANSFER` is retained as a possible simulated propagation/attribution
state, not rewritten as the initiating disturbance. The canonical vocabulary
also adds `GRID_VOLTAGE_SWELL` and `GRID_FREQUENCY_DEVIATION`.

A canonical replay over ten audit times for all scenarios has SHA-256
`ef7c6393a77283d6542e64c493a53da25c6019bfc1ef549781ca080b7f17f518`.

## Interface and schema disposition

- Canonical schema: 2.2.0. `source_timestamp_s` is optional for legacy
  readability but mandatory in every R4-generated sensor record. A legacy
  record without source time is not online-eligible without an audited join.
- Interface registry/runtime contract: 3.0.0, reflecting queued delivery.
- SensorModel: 2.0.0 with `sample` plus `release_arrived`.
- Scenario: 2.0.0 with versioned strict mappings and executable profiles.
- DynamicSubsystem: unchanged at 2.0.0.
- The frozen R3 runtime configuration is preserved at
  `configs/checkpoints/r3_default.yaml`; its canonical hash remains
  `6a47eefbefee0fa3084b3f4f2e780d0aa430bf3cad1f3dbb64a988398bbbaf97`.

## Tests and hashes

- R4-focused schema/config/interface/sensor/scenario/replay suite: 45/45
  passed.
- Complete repository suite: 107/107 passed in 38.60 s.
- Current canonical runtime-config SHA-256:
  `7a66469391268dae6e0458255ff88b263e6bf84965e87c93a7b04676caf4fd86`.
- Current default YAML SHA-256:
  `2bb497b1a05a299d421689ea2ac5c3a04ea058acdd3fecad6f5b6fa5208a9c84`.
- Scenario-library SHA-256:
  `1cec330dfb59657e553d760ec409968d22c1c9e8608c4fc78baa97c586e4add6`.
- R4 validation JSON SHA-256:
  `a828e5b27718e557c90aecbe5144d0f7283919bf0a61dd8d038ee16205aa22a1`.
- Sensor-delivery trace SHA-256:
  `49796301894b69b057d1b2c4b3ec573a64c6943a19b88d723f4398b82aa23ee8`.

## Residual limitations

- Sampling schedules anchor on the first supplied source state; the intended
  integrated runtime begins at step zero. The model does not reconstruct
  source values for calls skipped by an external caller.
- Communication delay is deterministic per sensor configuration; a future
  distribution requires separate provenance and tests.
- Timestamp jitter is an independent synthetic clock-error draw, not a model
  of synchronization dynamics or correlated drift.
- Queue delivery is an in-process simulation abstraction, not a broker,
  network stack, historian, or real latency guarantee.
- Scenario bounds are configured PoC envelopes, not measured fault
  distributions or safety certifications.
- Persistent STEP is implemented and tested but intentionally unused in the
  current finite-event library.
- Initiating labels are simulator definitions. They support offline synthetic
  evaluation only and do not prove real causality.
- CMP dynamics, utility topology, MRR, prediction, attribution algorithms,
  safety constraints, and control remain to be implemented or frozen.

## Gate disposition

R4 is closed as VALIDATED. All Phase 1/2 corrective gates R1--R4 are now
validated. T-PHASE12-REMEDIATION may close after the governance and living-paper
records are reconciled. The next Phase 3 task is to freeze and implement the
CMP process model and explicit utility-connection topology without reviving
the withdrawn direct MRR multiplier.
