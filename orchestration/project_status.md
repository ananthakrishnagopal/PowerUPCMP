# Project status

Last updated: 2026-07-13 14:02 IST<br>
Current phase: Phase 3 — scientific modelling and coupling<br>
Phase state: WP08, WP09, WP10, and WP12 COMPLETE within bounded claims<br>
Active task: none; next scientific decision task is T-WP13

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
validation gate. T-WP10 passes its declared-topology implementation,
null-control, full-chain, local/global/mismatch sensitivity, historical
reproduction, and validation gates. T-WP12 passes its frozen simulation-only
early-warning implementation and validation gate. Its learned models detect
all three independent TEST events, but the small event count and severe
structural-null, compound-shift, and high-noise failures sharply limit the
claim and require an independent applicability/safety gate before control use.
T-WP09 also passes its guarded public-data point-prediction gate: the selected
tree achieves 3.185/3.395 test/validation MAE on precedence-retained whole
wafers. Its interval coverage misses the frozen minimum, the hybrid does not
improve on the tree, and consumable ablation is model-dependent; those failed
interpretation gates remain explicit.

Detailed evidence:

- `orchestration/reports/phase_1_2_scientific_audit.md`
- `orchestration/reports/phase_3_cmp_model_redesign.md`
- `orchestration/reports/r1_contract_configuration_validation.md`
- `orchestration/reports/r2_phm_semantics_validation.md`
- `orchestration/reports/r3_plant_physics_validation.md`
- `orchestration/reports/r4_online_scenario_timing_validation.md`
- `orchestration/decisions/wp08_cmp_physics.md`
- `orchestration/reports/wp08_cmp_validation.md`
- `orchestration/reports/wp09_virtual_metrology_validation.md`
- `orchestration/decisions/wp10_utility_cmp_coupling.md`
- `orchestration/reports/wp10_literature_review.md`
- `orchestration/reports/wp10_coupling_validation.md`
- `orchestration/decisions/wp12_early_warning_target.md`
- `orchestration/decisions/wp12_conformal_separation.md`
- `orchestration/decisions/wp12_observation_robustness_completion.md`
- `orchestration/decisions/wp12_secondary_model_selection_correction.md`
- `orchestration/reports/wp12_revision_1_1_method_audit.md`
- `orchestration/reports/wp12_early_warning_validation.md`
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
- R2/R2.1 VALIDATED: PHM processing retains source row order, starts new continuity
  segments at non-positive increments and gaps above 10 s, uses centered
  time-support weights within segments, derives input-only process-mode
  proxies, keeps targets separate from features, and materializes all three
  preregistered four-label treatments without holdout-based selection.
- Official source partitions reuse 113/115/34 wafer IDs across their three
  role pairs in opposite stages. The accepted `training > test > validation`
  precedence retains 1,981/311/275 rows from 1,699/302/267 mutually disjoint
  wafers; the full 424-row source holdouts are contaminated diagnostics only.
  Inner whole-wafer chronological/grouped development splits are enforced.
  Physical-machine holdout is infeasible
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
- WP12 VALIDATED: target `SIM_ACTIVE_POLISH_MRR_TRAJECTORY_V1` uses a paired
  event-disabled reference, a ±5% active-POLISH envelope, 0.25 s persistence,
  and a 3 s forward horizon. Labels are censored after onset, when the horizon
  is incomplete, and when no active-POLISH opportunity exists. Features use
  only arrived observations available by each decision time; MRR, latent CMP
  states, event truth, and cause labels are prohibited.
- TRAIN, probability CALIBRATION, independent CONFORMAL_CALIBRATION, and TEST
  roles are disjoint by whole run. All preregistered models receive the same
  TEST, target-sensitivity, observation-robustness, unseen-compound, and
  structural-null analyses; TEST results are not used to choose a downstream
  model.

## Current evidence state

- Public PHM data: locally present; raw integrity/schema, label joins, R2
  semantic preprocessing, anomaly-policy materialization, and split/fit-scope
  contracts are verified. The processed offline bundle contains 1,981 training,
  424 test, and 424 validation wafer/stage rows with 405 target-free predictor
  columns. R2.1 retains 1,981/311/275 mutually wafer-disjoint modelling rows.
- WP09 public virtual metrology is complete. The target-blind manifest assigns
  1,396/299/286 training rows to fit/selection/calibration and preserves
  311/275 retained holdout rows with zero pairwise wafer overlap. After the
  frozen tree recommendation, the one-shot run opened targets and reported
  test/validation MAE 3.185/3.395, RMSE 5.176/6.693, and R² 0.975/0.958 in the
  source-native undeclared target scale. Coverage 0.839/0.847 fails the frozen
  0.85 minimum; the hybrid-improvement and cross-model consumable gates also
  fail. The validation JSON SHA-256 is
  `52d25cf92c4eea24158e0821cd7b7dd60fabe2ec04967443e3417397313bd10c`.
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
- Early warning: the frozen v1.4 simulation-only experiment contains 8,784
  eligible decision rows and 336 positive rows across disjoint split roles.
  TEST contains 1,932 rows, 84 positives, and only three independent
  event-bearing runs. Logistic regression attains PR-AUC 0.9904, row recall
  0.9286, event recall 3/3, and median warning lead 2.71 s; gradient-boosted
  trees attain PR-AUC 0.9130, row recall 1.0, event recall 3/3, and the same
  median lead. These are simulator results, not public-data or real-fab
  validation.
- Early-warning robustness is not sufficient for autonomous use. Under the
  structural-null topology, logistic regression produces 30 false-alarm
  episodes and the tree model nine; under high observation noise, logistic
  specificity falls to 0.0657 and tree PR-AUC to 0.5283. The observed-signal
  models therefore require topology/applicability checking and an independent
  WP16 safety filter.
- R1/R2 verification: the historical R2 gate passed 13 focused, 6 real-data,
  and 82 complete tests. The R2.1 correction passed 16 focused tests, then the
  complete repository passed 173/173 in 49.71 s with warnings treated as errors
  in conda environment `devkki`.
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
- WP12 verification: 16/16 focused tests and 170/170 complete tests pass with
  warnings treated as errors in `devkki`. The dataset hash is
  `fabe232a503320c59e9a201b62731adc8bf4c6b1f5fd5ee57bb30091a30b43fa`;
  the probability-payload hash, which intentionally excludes measured
  latency and set-valued outputs, is
  `5a4fb7011fd6688718455c9692689937caa679ea29c884cdca099835a9830ede`.
  The runtime and WP12 configuration hashes are respectively
  `b2b07edbaad458f6f66cf26ce88ffc5deef656a33701a7cccd8da94104d7383f`
  and
  `b53730011cb4f3c26173c727ba9fc562e9677a24a422f558a1c3330ab2df1e05`.
- Post-manuscript verification reran the complete suite with warnings treated
  as errors: 170/170 tests passed in 51.32 s in `devkki`.
- WP09 closeout verification passes 19/19 focused tests in 5.08 s and 192/192
  complete repository tests in 51.13 s with warnings treated as errors in
  `devkki`.
- Historical reproduction: R3 validation JSON/trace hashes are restored to
  `02ba8166715c1022d54685d96ded8b85c196dbd0dbc6b29ea544dd4b085eddb7`
  and
  `5191cbdcbf36c8709d92ed0de9662104c3ba6adfdd030ac45a661020ea17fdd0`;
  R4 hashes and the WP08 trace hash also reproduce exactly.
- The passing suite validates corrective gates R1--R4, standalone synthetic
  CMP invariants, declared synthetic coupling mechanics, and the frozen WP12
  simulation-only early-warning experiment. The separately hashed WP09 result
  artifact supports its bounded public-data point-prediction claim; test count
  alone does not. Neither source validates attribution, safety, controller
  efficacy, actual CMP plumbing, or a real-fab causal effect.
- Supported implementation claims: C-001 for bounded offline public-data point
  prediction; C-002 and C-011 at the explicitly limited simulation level; and
  C-003 only for the frozen in-distribution synthetic WP12 experiment. C-003
  fails to generalize safely across all audited shifts. C-008 and the
  cross-model C-009 gate are rejected on public data. Supported real-fab,
  physical-defect, yield, or control-efficacy claims: none.
- Dataset network transfer: none; the archive was supplied locally.
- Agent/subagent actions: one user-authorized bounded manuscript agent created
  the journal-format LaTeX draft; all scientific modelling, WP12 execution,
  validation, governance, and repository integration remain primary-agent
  work.

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
- The committed interim deck predates WP12 and therefore still marks public-data
  modelling, early warning, attribution, controllers, safety filtering, and
  paired efficacy evaluation as pending. Its scientific claims remain valid,
  but a later presentation revision should add the frozen WP12 evidence.
- T-PAPER-DRAFT is COMPLETE. The journal-neutral two-column LaTeX source builds
  a visually reviewed 15-page A4 PDF containing public-data WP09 methods,
  results, failed gates and figures alongside bounded WP08/WP10/WP12 evidence,
  while retaining visible pending markers for unexecuted work. The PDF SHA-256
  is `34a8a4be5826f47ff4c67af7bfd700610ccc759f88129546f824606a51760138`;
  the final LaTeX log has no overfull box, undefined-reference,
  undefined-citation, or rerun warning.

## WP09 controlled execution

The frozen implementation and target-blind split evidence are documented in
`orchestration/reports/wp09_preholdout_checkpoint.md`. The one-shot script
verified pre-holdout commit `01c59a6`, replayed the exact manifest, reran the
focused suite, wrote the persistent opening marker, and then consumed the
authorized target access. The complete result and interpretation gates are in
`orchestration/reports/wp09_virtual_metrology_validation.md`. The guard now
refuses a silent rerun, preserving the one-shot audit trail.

## Next Phase 3 work

T-WP08, T-WP09, T-WP10, and T-WP12 are scientifically closed within their
stated claim boundaries. Remaining Phase 3 decision work is:

1. T-WP13 — freeze attribution scoring, residual-chain logic, and the
   mandatory `UNKNOWN` outcome, with feature attribution explicitly excluded
   as causal proof;
2. T-WP15 — freeze the predictive supervisory objective, action set, horizon,
   penalties, and fallback policy; and
3. T-WP16 — freeze independent safety limits, applicability checks, sensor and
   uncertainty rejection rules, hold replacement, and controlled-resume
   criteria.

No controller-efficacy comparison or WP17 integrated closed-loop runtime is
authorized by this status; those remain downstream work.

Current governance evidence: 16 YAML files parse with zero duplicate keys; all
29 tasks form an acyclic dependency graph and reference 25 valid assumptions;
116 Markdown files contain 122 valid local links and zero missing local links.
