# Project status

Last updated: 2026-07-12 13:15 IST<br>
Current phase: Phase 3 — scientific modelling and coupling<br>
Phase state: SCIENTIFIC MODEL FREEZE IN PROGRESS<br>
Active task: T-COMMS-DEMO COMPLETE; T-PAPER-DRAFT READY; scientific critical path remains the WP12 safe-envelope/horizon/uncertainty freeze

## Review outcome

A retrospective scientific audit of Phase 1, Phase 2, the PHM pipeline, and
the proposed CMP model is complete. It found that the repository contains
useful implementation and provenance work, but the Phase 2 checkpoint cannot
serve as a scientific gate without four bounded remediation packages:

1. R1 — contract, native-unit schema, and complete default configuration;
2. R2 — PHM phase semantics, time weighting, label-anomaly policy, and stronger splits;
3. R3 — pump/system operating point, hydraulic conservation, compliance, and UPS/frequency dynamics; and
4. R4 — observation-arrival causality and scenario validation/attribution semantics.

The old direct UPW-to-MRR multiplier decision is withdrawn and retained only
as history. The user approved the replacement CMP redesign as the controlled
implementation basis on 2026-07-11. This approval opens the required
interface/schema impact process; it does not validate an equation or parameter.
R1--R4 now pass. T-WP08 passes its controlled CMP-model implementation and
validation gate. T-WP10 now also passes its declared-topology implementation,
null-control, full-chain, local/global/mismatch sensitivity, historical
reproduction, and validation gates.

Detailed evidence:

- `orchestration/reports/phase_1_2_scientific_audit.md`
- `orchestration/reports/phase_3_cmp_model_redesign.md`
- `orchestration/reports/r1_contract_configuration_validation.md`
- `orchestration/reports/r2_phm_semantics_validation.md`
- `orchestration/reports/r3_plant_physics_validation.md`
- `orchestration/reports/r4_online_scenario_timing_validation.md`
- `orchestration/decisions/wp08_cmp_physics.md`
- `orchestration/reports/wp08_cmp_validation.md`
- `orchestration/decisions/wp10_utility_cmp_coupling.md`
- `orchestration/reports/wp10_literature_review.md`
- `orchestration/reports/wp10_coupling_validation.md`
- `orchestration/decisions/20260711_phase_3_cmp_and_utility_model.md`
- `orchestration/decisions/phase_1_2_remediation.md`

## Evidence retained from prior phases

- The user-supplied PHM archive and all 558 selected raw members passed
  recorded SHA-256/CRC checks; 58 header-only traces remain explicit and were
  not imputed.
- The raw loader enforces exact headers and archive-manifest checks, and the
  training label join is many-to-one audited.
- Latent and observed record types are separate and component state objects
  are immutable and bounded for the cases tested.
- Electrical, drive, pump, UPW, sensor, and scenario code replays
  deterministically for fixed inputs/seeds in the existing test suite.
- Claims controls continue to exclude physical-defect, yield, equipment,
  production-control, and microsecond-response claims.

These statements are provenance or implementation evidence. They are not
validation of real-fab parameters, the complete plant physics, or controller
efficacy.

## Audit findings and remediation disposition

- R1 VALIDATED: canonical schema 2.0.0 preserves native/unknown public units,
  RunManifest requires parameter provenance, DynamicSubsystem 2.0.0 matches all
  four plant components, sensing remains independent, and the complete strict
  `configs/default.yaml` is present and deterministically hashed.
- R2 VALIDATED: PHM processing retains source row order, starts new continuity
  segments at non-positive increments and gaps above 10 s, uses centered
  time-support weights within segments, derives input-only process-mode
  proxies, keeps targets separate from features, and materializes all three
  preregistered four-label treatments without holdout-based selection.
- Official training/test/validation roles and whole-wafer chronological/grouped
  development splits are enforced. Physical-machine holdout is infeasible
  because all records use machine ID 2; `MACHINE_DATA` varies within nearly
  every wafer/stage group and is not represented as a machine or stable regime.
- R3 VALIDATED: the speed-scaled pump curve is evaluated against network
  differential pressure; the supply compliance uses a unique implicit balance
  with explicit tool, return, relief, and storage flows; pump-trip and
  closed-valve limiting cases conserve mass; thermal flushing uses pump inflow;
  and water quality is only a dimensionless synthetic deviation proxy.
- UPS output frequency, battery energy/load, charging, depletion, overload,
  and forced interruption are explicit. R3 schema/registry 2.1.0 is preserved
  in its checkpoint and superseded by the R4 contracts; the
  `DynamicSubsystem` method contract remains 2.0.0.
- R4 VALIDATED: source, reported, and arrival clocks are distinct; generated
  observations are queued until arrival and released exactly once; source
  boundaries are validated; scenario profiles are executable; targets are
  unit/range checked; unknown keys and ambiguous overlaps are rejected; and
  initiating disturbances are distinct from propagation states.
- R4 canonical schema 2.2.0 and interface registry 3.0.0 remain reproducible
  checkpoints. SensorModel and Scenario remain 2.0.0; DynamicSubsystem remains
  2.0.0.
- WP08 VALIDATED: the standalone synthetic CMP subsystem implements explicit
  process modes, signed slew-limited spindle states, normalized rotary-offset
  pressure--velocity exposure, dynamic slurry and consumables, interface
  energy balance, cumulative removal, recovery dwell, and a neutral typed
  boundary. Its frozen canonical schema/interface versions remain 2.3.0/3.1.0.
- WP10 VALIDATED: a stateless coupler maps latent UPW pressure, flow, and
  temperature into the frozen CMP boundary under no-connection,
  dressing-water, thermal-loop, or explicitly synthetic slurry-support
  structures. Current canonical schema/interface versions are 2.4.0/3.2.0;
  DynamicSubsystem remains 2.0.0 and CmpBoundaryConditions remains 1.0.0.
- The default topology is `NO_CONNECTION`. Zero link, nominal connected
  service, and default thermal-to-MRR behavior are exact structural nulls.
  Water-quality deviation has no CMP effect.
- The healthy-UPS 25 percent, 400 ms sag yields only a small downstream
  response and unchanged tool flow in the current model. It is a valuable
  negative control, not a scenario to tune into a large excursion.

## Current evidence state

- Public PHM data: locally present; raw integrity/schema, label joins, R2
  semantic preprocessing, anomaly-policy materialization, and split/fit-scope
  contracts are verified. The processed offline bundle contains 1,981 training,
  424 test, and 424 validation wafer/stage rows with 405 target-free predictor
  columns; public virtual-metrology modelling has not begun.
- Dataset licence: not separately stated; local research use is limited to
  the user's recorded authorization.
- Synthetic simulator: corrected R3 utility-plant components pass equilibrium,
  conservation, limiting-case, and timestep-refinement checks; R4 causal
  delivery/scenario semantics and standalone WP08 CMP invariants also pass.
- CMP/coupling: standalone CMP physics and declared synthetic utility
  topologies are implemented and validated within their tested envelopes. A
  healthy 25%/400 ms sag remains full-support; a separately declared degraded
  500 J UPS interruption during DRESS reduces stored pad activity and later
  simulated MRR by 3.19% versus no connection. This is not real-tool
  calibration or controller efficacy.
- R1/R2 verification: R1 focused tests passed 21/21; R2 focused tests passed
  13/13; real-data integration tests passed 6/6; and the complete suite passed
  82/82 with zero warnings in conda environment `devkki`.
- R3 verification: 52/52 focused tests and 94/94 complete tests passed. At the
  10 ms default step, the 0.70-pu speed test differs from the 0.5 ms reference
  by 36.19 Pa (0.0121% nominal); generated mass-balance residuals remain below
  1.0e-12 m³/s.
- R4 verification: 45/45 focused tests and 107/107 complete tests passed. The
  deterministic audit released 101/101 samples exactly once, including 49
  negative reported-clock jitters, with zero early deliveries; all 14
  scenarios validate under schema 2.0.0.
- WP08 verification: 48/48 focused impacted tests and 130/130 complete tests
  passed. The 700-row deterministic trace hash is
  `902fa4283ef8cf2150efef14aa08ca6f478aad55503e6d9b111584c33175626e`;
  maximum absolute energy residual is 1.419e-8 W, and 40/20/10/5/2.5 ms
  errors decrease against a 1 ms reference.
- WP10 verification: 50/50 impacted tests and 154/154 complete tests pass in
  conda environment `devkki`. The runtime hash is
  `b2b07edbaad458f6f66cf26ce88ffc5deef656a33701a7cccd8da94104d7383f`.
  The connected negative-control trace hash is
  `f8359518903a8def6e02d03a8bc73123cc8a32dc5c32ed39dabc26745bfc3f20`;
  positive no-connection/connected trace hashes are
  `3560cb28a4cc8e87d778146f2cf0964290d733da2a0b59bee283659644ae41fc`
  and
  `19f440b2fd31959c619c31b851003ac496ff4d3b66c1643a6c6fbbb4951dfa10`.
- Historical reproduction: R3 validation JSON/trace hashes are restored to
  `02ba8166715c1022d54685d96ded8b85c196dbd0dbc6b29ea544dd4b085eddb7`
  and
  `5191cbdcbf36c8709d92ed0de9662104c3ba6adfdd030ac45a661020ea17fdd0`;
  R4 hashes and the WP08 trace hash also reproduce exactly.
- The passing suite validates corrective gates R1--R4, standalone synthetic
  CMP invariants, and the declared synthetic coupling mechanics. It does not
  validate virtual metrology performance, early warning, attribution, safety,
  controller efficacy, actual CMP plumbing, or a real-fab causal effect.
- Supported implementation claims: C-002 and C-011 at the explicitly limited
  simulation level. Supported public VM, real-fab, physical-defect, yield, or
  control-efficacy claims: none.
- Dataset network transfer: none; the archive was supplied locally.
- Agent/subagent actions: none.

## Git and interim communication state

- Git is active on branch `main`. Commit `51ba07a` is the protected validated
  WP10 scientific/software baseline; raw PHM tables, the source archive, local
  paper PDFs, private Codex/agent state, and transient build files remain
  excluded by policy.
- T-COMMS-DEMO is COMPLETE. One canonical Markdown source reproducibly builds
  a 17-page PDF and a 23-slide editable PPTX from six figures regenerated from
  frozen WP08/WP10 artifacts. The figure manifest records all input/output
  SHA-256 values and the synthetic-only claim boundary.
- The PDF passed representative-page visual review. The PPTX passes file-type,
  ZIP-member, embedded-media, and non-empty slide-content checks; independent
  LibreOffice rendering is recorded as an environment limitation, not a
  passed test.
- The deck explicitly marks public-data modelling, early warning, attribution,
  controllers, safety filtering, and paired efficacy evaluation as pending.
  It makes no physical-defect, yield, equipment-protection, real-fab, or
  production-control claim.
- T-PAPER-DRAFT is READY. It will convert the running evidence ledger into a
  journal-neutral two-column LaTeX manuscript while retaining visible pending
  markers for unexecuted Phase 3/4 work.

## Next Phase 3 work

T-WP08 and T-WP10 are scientifically closed within their synthetic claim
boundaries. The critical-path next activity is to freeze the WP12 average-MRR
safe envelope, persistence rule, warning horizon, label censoring, streaming
feature cutoff, uncertainty method, calibration split, and coverage target.
T-WP12 must remain PLANNED until that blocker is cleared. WP09 public
virtual-metrology decisions also remain unfrozen and cannot mix the PHM native
numeric target with SI simulator coefficients.

Current governance evidence: 14 YAML files parse with zero duplicate keys; all
29 tasks form an acyclic dependency graph and reference 25 valid assumptions;
81 Markdown files contain 55 valid local links and zero missing local links.
