# Implementation plan

## Operating method

Work is phase-gated and single-agent. Only tasks marked `READY` in `task_manifest.yaml` may be implemented. After each meaningful task, update its state and the project status. Stop on the first unexpected failure, preserve logs, create the required failure report, and wait for user direction. At every phase boundary, save a checkpoint and recommend the next model tier.

Formatting and path preflight is mandatory because even non-functional hygiene
failures invoke the same stop policy:

- resolve paths with `rg --files` before opening inferred filenames;
- inspect exact current context immediately before each patch;
- use small file-specific patches;
- do not encode Markdown line breaks with trailing spaces; and
- run `git diff --check` after each patch batch and before tests or builds.

## Phase 1 — Architecture and planning

Status: completed on 2026-07-10; controlled corrections are required by the
2026-07-11 retrospective scientific audit before downstream integration.

Deliver and cross-check the repository assessment, charter, claims matrix, architecture, canonical schema, interface registry, assumptions, risks, data-source plan, dependency DAG, task manifest, and this implementation plan. Freeze schema and interface version 1.0.0. Do not implement the package.

Acceptance gate:

- All required files exist and are non-empty.
- YAML files parse with PyYAML.
- Every task has the required fields and an allowed state.
- Task dependencies refer to known IDs and form an acyclic graph.
- Each work package WP00–WP20 has a manifest task.
- Required interfaces and safety outcomes exist.
- Schema contains semantic origin classes and separate latent/observation records.
- Claims matrix explicitly rejects prohibited physical-defect, yield, damage, production, and microsecond claims.
- Phase 1 checkpoint and status agree.

## Phase 2 — Repository and routine components

Recommended execution tier: economical model, medium reasoning.

Historical status: checkpointed on 2026-07-11 after 60 tests passed. A later
high-reasoning audit found scientific acceptance gaps not covered by those
tests. The checkpoint remains an execution record, but its scientific gate is
provisional pending T-PHASE12-REMEDIATION.

### Sequence

1. **WP01 foundation:** create `pyproject.toml`, `src/semifab_poc`, strict Pydantic configuration, logging, CLI entry point, pytest layout, Makefile, README and documentation skeleton. Avoid optional dependencies.
2. **WP02 schema/provenance:** implement canonical record types, unit conversions, dataset/run manifests, strict validation, split audit primitives, and `data/README.md`.
3. **Data acquisition preparation:** implement `scripts/fetch_data.py` as a disabled-by-default registry-driven tool. Do not download anything. It must refuse unapproved or incomplete source entries.
4. **WP04 simple electrical model:** implement normal grid, sag/swell, interruption, frequency deviation, UPS transfer and recovery with synthetic parameters only.
5. **WP05 drive/pump model:** implement commands, derating, ramp, motor lag, trip/restart, and bounded affinity relations.
6. **WP06 UPW model:** implement lumped pressure/flow/compliance/resistance/valve/demand/temperature and proxy quality state using explicitly synthetic defaults.
7. **WP07 sensors:** implement all specified corruption modes with named seeds and immutable latent input.
8. **WP11 scenarios:** implement strict declarative schemas and deterministic event replay; provide all named scenario configurations without tuning scientific coupling.
9. Add unit/property tests and thin CLI wrappers as each component lands.

Stop Phase 2 before selecting difficult coupling coefficients, safe-envelope thresholds, uncertainty methods, or controller objectives. If a missing package is required and cannot be installed locally, invoke the failure policy rather than substituting an undeclared implementation.

### Phase 2 acceptance gate

- Clean local editable installation from declared dependencies.
- CLI configuration and scenario validation work.
- Normal operation is stable for a small reference trace.
- Pump monotonicity/non-negativity and sensor-state separation pass.
- Fixed seeds replay exactly.
- No network access or public-data claims occur.

## Phase 3 — Scientific modelling and coupling

Recommended execution tier: strong model, high reasoning.

### Corrective gate opened by scientific audit

Before T-WP08 or T-WP10 resumes, complete the four gates defined in
`orchestration/reports/phase_1_2_scientific_audit.md`:

1. R1: reconcile frozen interfaces, native/unknown public units, and the
   complete default configuration through versioned change control.
2. R2: implement PHM phase-aware, time-weighted processing, the preregistered
   four-label anomaly sensitivities, source-role audits, whole-wafer precedence,
   and inner wafer/time/machine split evidence.
3. R3: solve the pump/system operating point, conserve hydraulic mass through
   explicit relief/bypass paths, restore compliance-governed transients, and
   reconcile frequency/UPS-energy claims.
4. R4: enforce source-to-arrival causality and executable, target-bounded,
   interval-aware scenario validation.

Gate status: R1, R3, and R4 are VALIDATED; R2 is VALIDATED with the
2026-07-13 whole-wafer precedence correction. R2
evidence is recorded in `orchestration/reports/r2_phm_semantics_validation.md`;
R3 evidence is recorded in
`orchestration/reports/r3_plant_physics_validation.md`; R4 evidence is recorded
in `orchestration/reports/r4_online_scenario_timing_validation.md`. These gates
do not authorize a controller-efficacy claim. T-WP08, T-WP09, T-WP10, T-WP12,
and T-WP13 are COMPLETE within their recorded boundaries. The reduced-order
CMP equations and declared utility topology pass their synthetic checks; the
PHM tree supports bounded offline point prediction but not calibrated
uncertainty or hybrid improvement; early warning is limited by three TEST
events and severe shift failures; and attribution is conditional on a valid
diagnostic warning with communication-driven availability limits. The
withdrawn direct UPW-to-MRR modifier must not be restored.

### Scientific decisions frozen at the Phase 3 gate

1. Electrical, motor, hydraulic, thermal, and CMP equations have canonical
   units, integration/stability checks, and bounded literature use.
2. The Preston coefficient interpretation, modifier forms, phase gating,
   cumulative removal, and consumable-memory states are frozen in WP08.
3. Each utility-to-CMP coefficient has a four-way provenance class, nominal
   value, bounds, sign, uncertainty treatment, and sensitivity evidence in
   WP10.
4. The average-MRR safe envelope, 0.25 s persistence, 3.0 s horizon, feature
   cutoff, label censoring, and event unit are frozen in WP12.
5. Public-data model isolation and uncertainty gates are complete in WP09;
   the failed coverage and hybrid-improvement gates remain visible.
6. Compound-cause and `UNKNOWN` attribution policy is frozen and conditionally
   validated in WP13.
7. The predictive controller uses a four-action hold/resume policy, explicit
   recipe clock, lexicographic objective, fixed probability gates, synthetic
   penalties, and 10/50 ms controller/end-to-end p95 budgets. Numerical
   compensation actions are disabled because the current plant does not have
   defensible authority for the primary under-removal mechanism.
8. The independent safety contract freezes action/slew limits, sensor and
   applicability rejection, fail-closed behavior, battery reserve, hold and
   recovery state, and controlled-resume dwell.
9. The required primary threshold is an arrived process-MRR hysteresis policy;
   a direct upstream utility threshold is a mandatory fourth comparator. New
   TEST seed ranges, equal-recipe completion, paired bootstrap gates, 5%
   threshold tolerances, negative-control hold rate, and zero final constraint
   violations are frozen before Phase 4 results.

### Scientific validation

- Dimensional and limiting-case checks.
- Equilibrium, stability, and timestep convergence.
- Local and global parameter sensitivity.
- Residual diagnostics and grouped public-data splits if PHM is verified.
- Calibration/coverage and scenario-shift evaluation.
- Safety feasibility and failure-mode analysis.

All Phase 3 scientific contracts now pass their bounded acceptance gates. The
remaining work is routine implementation and evaluation against frozen
criteria; it does not authorize a controller-efficacy or real-safety claim.

## Phase 4 — Routine completion and testing

Recommended execution tier: economical model, medium reasoning.

Reuse the completed WP08, WP09, WP10, WP12, and WP13 implementations without
retuning their frozen evidence. Begin only with tasks currently marked `READY`:
T-WP14 baseline controllers, T-WP15-IMPL predictive controller, and
T-WP16-IMPL independent safety filter. Their completion unlocks T-WP17
integrated runtime, followed by T-WP18 paired/robustness evaluation, T-WP19
dashboard, and T-WP20 documentation/report generation. Add the specified unit,
property, integration, regression, scientific, and performance tests and
generate only bounded evidence with the preregistered settings.

Acceptance gate:

- Full causal chain executes deterministically.
- No action, process-threshold, and predictive control run paired scenarios,
  with the mandatory utility-threshold comparator reported beside them.
- Every final action has a safety disposition and remains within the frozen envelope.
- Required metrics and distribution summaries are generated.
- Synthetic/public provenance is visible in every artifact.
- Dashboard reads artifacts without unique model or control logic.

Stop on integration or numerical issues; do not retune tests or scientific thresholds to obtain passing results.

## Phase 5 — Final integration and review

Recommended execution tier: strong model, high or extra-high reasoning.

Review implementation, equations, units, provenance, parameter sensitivity, leakage, uncertainty, attribution language, controller pairing, safety independence, and claim boundaries. Run clean installation, full tests, reproducibility, the 25%/400 ms reference demonstration, report generation, dashboard smoke test, secret scan, and final audit.

The final report must show mean, median, standard deviation, 5th percentile, 95th percentile, and worst case for applicable metrics; separate public-data and simulator results; state limitations; and retain the mandatory spatial-proxy label wherever applicable.

## Test strategy by layer

| Layer | Unit/property evidence | Integration/scientific evidence |
|---|---|---|
| Configuration/schema | strict keys, ranges, unit conversions, serialization | config-to-run manifest reproducibility |
| Electrical/drive/pump | transitions, ramp, trip, affinity monotonicity | sag → derating → speed/flow trace; limiting cases |
| UPW | resistance/compliance/thermal updates, non-negativity | balance residual, equilibrium, timestep convergence |
| Sensors | corruption types, delay queue, seeded determinism | latent state unchanged; rate mismatch and loss traces |
| CMP/coupling | Preston units, modifiers, bounds | sensitivity, mismatch, age and flow limiting cases |
| Models | features, split audit, fit/save/load | grouped evaluation, calibration, uncertainty coverage |
| Controllers | no-action identity, threshold hysteresis, action bounds | paired scenario outcomes, hold/restart, latency |
| Safety | every disposition, clipping, slew, invalid sensor | independence, fail-safe coverage, zero final violations |
| Runtime | update order, atomic step, log schema | deterministic replay and full reference trace |
| Reports/dashboard | metric formulas and mandatory labels | regeneration, source separation, claims scan |

## Data acquisition decision point

The fetch/extraction tool was implemented and used only on the user-supplied
local archive after explicit authorization; no dataset network transfer
occurred. Archive integrity, selected filenames, raw headers, and label joins
are verified. The dataset licence is still not separately stated, so use is
limited to the recorded local authorization. Any future network transfer or
mirror still requires an approved registry URL, licence/size review, and the
original failure policy. Synthetic outputs must never substitute under the
PHM dataset ID.
