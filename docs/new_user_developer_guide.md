# New User Developer Guide

## Purpose

This guide is for a new developer, reviewer, or researcher who wants to
understand how to use, extend, or evaluate this CMP predictive-control proof of
concept.

The project has two deliberately separate evidence planes:

- **Public PHM virtual-metrology plane:** uses the PHM 2016 CMP archive for
  offline average-MRR prediction in the source-native target scale.
- **Synthetic simulator/control plane:** uses a reduced-order SI simulator for
  utility disturbances, CMP behavior, warning, attribution, supervisory
  control, and safety-filter evaluation.

Do not mix these planes. Public-data results do not validate the simulator, and
synthetic simulator results do not validate real-fab production control.

## Start Here

Read these files first, in order:

1. [`README.md`](../README.md)
   - Gives the repository purpose, setup commands, current evidence boundaries,
     and the headline results.

2. [`orchestration/project_status.md`](../orchestration/project_status.md)
   - Explains what is complete, what was validated, which claims are supported,
     and which claims remain unsupported.

3. [`orchestration/architecture.md`](../orchestration/architecture.md)
   - Describes the system architecture, runtime signal flow, public/synthetic
     split, and controller/safety separation.

4. [`docs/mathematical_model.md`](mathematical_model.md)
   - Explains the CMP physics, utility-to-CMP coupling math, numerical method,
     and limitations.

5. [`docs/assumptions_and_limitations.md`](assumptions_and_limitations.md)
   - Lists modeling assumptions and what the POC must not claim.

6. [`docs/reproduction.md`](reproduction.md)
   - Shows how to regenerate the main Phase 4 artifacts.

7. [`orchestration/final_audit.md`](../orchestration/final_audit.md)
   - Records the final integration/audit status.

## Repository Map

The core implementation lives under [`src/semifab_poc`](../src/semifab_poc).

### Configuration

- [`configs/default.yaml`](../configs/default.yaml)
  - Main strict runtime configuration.
  - Defines electrical, drive, pump, UPW, CMP, coupling, and sensor settings.

- [`configs/models/virtual_metrology.yaml`](../configs/models/virtual_metrology.yaml)
  - WP09 PHM virtual-metrology experiment contract.

- [`configs/models/early_warning.yaml`](../configs/models/early_warning.yaml)
  - WP12 synthetic early-warning target, features, splits, model families, and
    evaluation gates.

- [`configs/models/attribution.yaml`](../configs/models/attribution.yaml)
  - WP13 root-cause attribution classes, features, rules, hybrid policy, and
    abstention gates.

- [`configs/controllers/predictive.yaml`](../configs/controllers/predictive.yaml)
  - WP15 predictive hold/resume supervisor contract.

- [`configs/controllers/baselines.yaml`](../configs/controllers/baselines.yaml)
  - Baseline controller definitions.

- [`configs/controllers/safety.yaml`](../configs/controllers/safety.yaml)
  - WP16 independent safety-filter constraints.

Unknown config keys are intentionally rejected. When changing behavior, update
the matching strict config and its validation tests rather than adding ad hoc
runtime options.

### Data Plane

- [`src/semifab_poc/data`](../src/semifab_poc/data)
  - PHM archive checks, provenance, schema validation, feature building, and
    leakage-safe splits.

Key files:

- [`data/phm_cmp.py`](../src/semifab_poc/data/phm_cmp.py)
- [`data/build_features.py`](../src/semifab_poc/data/build_features.py)
- [`data/splits.py`](../src/semifab_poc/data/splits.py)
- [`data/provenance.py`](../src/semifab_poc/data/provenance.py)
- [`data/schema.py`](../src/semifab_poc/data/schema.py)

Use this package when working with public PHM data. Do not import simulator
truth into this plane.

### Simulation Plane

- [`src/semifab_poc/simulation`](../src/semifab_poc/simulation)
  - Deterministic synthetic plant and causal observation layer.

Main components:

- [`electrical.py`](../src/semifab_poc/simulation/electrical.py)
  - Grid voltage/frequency, UPS transfer, battery energy, output behavior.

- [`drive.py`](../src/semifab_poc/simulation/drive.py)
  - VFD and motor-speed dynamics.

- [`pump.py`](../src/semifab_poc/simulation/pump.py)
  - Speed-scaled pump curve and hydraulic power proxy.

- [`upw.py`](../src/semifab_poc/simulation/upw.py)
  - Conserved hydraulic pressure/flow, relief, thermal state, water-quality
    proxy.

- [`cmp.py`](../src/semifab_poc/simulation/cmp.py)
  - CMP process-state machine, rotary kinematics, pressure-velocity exposure,
    pad/dresser/slurry/thermal states, and MRR.

- [`coupling.py`](../src/semifab_poc/simulation/coupling.py)
  - Stateless latent-UPW-to-CMP boundary mapping.

- [`sensors.py`](../src/semifab_poc/simulation/sensors.py)
  - Noise, delay, dropout, jitter, and causal observation arrival.

- [`chain.py`](../src/semifab_poc/simulation/chain.py)
  - Open-loop synthetic chain runner used for WP12/WP13 datasets.

- [`runtime.py`](../src/semifab_poc/simulation/runtime.py)
  - Integrated runtime with plant, sensors, predictor, attribution, controller,
    safety filter, action staging, and logs.

### Models

- [`src/semifab_poc/models`](../src/semifab_poc/models)
  - Offline PHM virtual metrology and synthetic online models.

Main files:

- [`virtual_metrology.py`](../src/semifab_poc/models/virtual_metrology.py)
  - WP09 public PHM average-MRR prediction.
  - Model families: mean, linear, ridge, physics proxy, tree, hybrid residual.

- [`early_warning.py`](../src/semifab_poc/models/early_warning.py)
  - WP12 synthetic future-MRR-excursion warning.
  - Model families: prevalence baseline, logistic regression, gradient
    boosting.

- [`attribution.py`](../src/semifab_poc/models/attribution.py)
  - WP13 synthetic root-cause attribution.
  - Methods: always-UNKNOWN, rule-only, logistic, hybrid.

Model artifacts and hashes live under:

- [`reports/virtual_metrology/models`](../reports/virtual_metrology/models)
- [`reports/early_warning/models`](../reports/early_warning/models)
- [`reports/attribution/models`](../reports/attribution/models)

### Control And Safety

- [`src/semifab_poc/control`](../src/semifab_poc/control)
  - Controller interfaces, baselines, predictive supervisor, and independent
    safety filter.

Main files:

- [`base.py`](../src/semifab_poc/control/base.py)
  - Controller and safety-filter interfaces.

- [`contracts.py`](../src/semifab_poc/control/contracts.py)
  - Strict action, controller, baseline, and safety schemas.

- [`baselines.py`](../src/semifab_poc/control/baselines.py)
  - No-action, process-MRR-threshold, and utility-threshold controllers.

- [`predictive.py`](../src/semifab_poc/control/predictive.py)
  - Predictive hold/resume supervisor.

- [`safety.py`](../src/semifab_poc/control/safety.py)
  - Independent safety-filter implementation.

The primary predictive policy only uses:

- `NO_ACTION`
- `ADVISORY_WARNING`
- `SAFE_HOLD`
- `CONTROLLED_RESUME`

Numeric actions exist in the schema but are disabled for the primary claim
because the validated disturbance mechanism is under-removal after
conditioning-service loss, and the available numeric reductions are not a
validated compensation mechanism.

### Evaluation

- [`src/semifab_poc/evaluation`](../src/semifab_poc/evaluation)
  - Paired evaluation and metrics.

Main files:

- [`metrics.py`](../src/semifab_poc/evaluation/metrics.py)
  - Active-polish progress-matched MRR error metrics, hold/cycle metrics,
    safety violations, and latency summaries.

- [`experiments.py`](../src/semifab_poc/evaluation/experiments.py)
  - Batch primary scenario/controller comparisons.

Review note: the current Phase 4 experiment script is useful for runtime and
dashboard plumbing, but inspect whether predictors/estimators are actually
loaded in the path you are using before treating an evaluation artifact as a
closed-loop predictive-control result.

### Dashboard

- [`src/semifab_poc/dashboard`](../src/semifab_poc/dashboard)
  - Read-only local dashboard for generated artifacts and demonstration traces.

Main files:

- [`server.py`](../src/semifab_poc/dashboard/server.py)
- [`index.html`](../src/semifab_poc/dashboard/index.html)
- [`app.js`](../src/semifab_poc/dashboard/app.js)
- [`style.css`](../src/semifab_poc/dashboard/style.css)

Speaker notes:

- [`docs/dashboard_demo_speaker_notes.md`](dashboard_demo_speaker_notes.md)

## Mathematical Links To Understand

### Utility Chain

The synthetic utility path is:

```text
grid/UPS -> VFD/motor -> pump -> UPW pressure/flow/temperature
```

The pump uses a speed-scaled curve:

```text
H_p(Q, n, d) = d H_shut n^2 - k_Q Q^2
```

where `n` is normalized motor speed.

The UPW subsystem solves hydraulic balance with compliance, tool flow, return
flow, relief flow, and storage. Its pressure and flow become inputs to the
coupler, not directly to CMP MRR.

### CMP Removal

CMP uses area-averaged rotary pressure-velocity exposure:

```text
Phi_PV = (P_c / P_0)^alpha * <(v_R / V_0)^beta>_A
```

The true synthetic MRR is:

```text
R_eq = chi_polish * R_0 * Phi_PV * m_slurry * m_temperature * m_pad * m_recipe
R_true = clip(R_eq + epsilon_proc, 0, R_max)
```

Only `POLISH` contributes material removal and active polish time.

### Coupling

The stateless coupler computes availability from pressure and flow ramps:

```text
R(x; x0, x1) = clip((x - x0) / (x1 - x0), 0, 1)
a_h = min(R(p; p0, p1), R(q; q0, q1))
a_eff = 1 - lambda * (1 - a_h)
```

Topologies decide which CMP boundary fields receive `a_eff`:

- `NO_CONNECTION`: no CMP effect.
- `DRESSING_WATER_SUPPORT`: dressing availability.
- `THERMAL_LOOP`: coolant temperature/conductance.
- `SYNTHETIC_SLURRY_SUPPORT`: slurry utility availability.

The primary supported synthetic mechanism is:

```text
loss of dressing support during DRESS
-> less pad recovery
-> lower pad modifier during later POLISH
-> under-removal
```

### Warning Target

WP12 labels a decision row positive when a persistent future active-polish MRR
excursion begins within the 3.0 s horizon:

```text
y(t_d) = 1[t_d < t_event <= t_d + H]
```

The event itself is defined against a paired event-disabled reference and
requires a persistent ±5% active-polish MRR deviation for 0.25 s.

### Control

The predictive supervisor proposes hold when:

```text
p_k >= 0.50 and conformal_set == {1}
```

It proposes resume when:

```text
p_k <= 0.20 and conformal_set == {0}
```

The safety filter then independently validates timing, action schema,
observation validity, uncertainty/applicability, process mode, action envelope,
and restart conditions.

## Current Model Results

### WP09 Public PHM Virtual Metrology

Selected model: gradient-boosted tree.

Held-out retained results:

- Test MAE: `3.1852`
- Validation MAE: `3.3954`
- Test RMSE: `5.1756`
- Validation RMSE: `6.6932`
- Test R2: `0.9751`
- Validation R2: `0.9585`
- Interval coverage: `0.8392 / 0.8473`, below the frozen minimum `0.85`

Interpretation: offline average-MRR point prediction is supported with limits;
uncertainty coverage failed.

Primary report:

- [`orchestration/reports/wp09_virtual_metrology_validation.md`](../orchestration/reports/wp09_virtual_metrology_validation.md)

### WP12 Synthetic Early Warning

Models:

- prevalence baseline
- logistic regression
- gradient boosting

Primary synthetic TEST results:

- Logistic PR-AUC: `0.9904`
- Logistic row recall: `0.9286`
- Logistic event recall: `3/3`
- Logistic median warning lead: `2.71 s`
- Gradient-boosted PR-AUC: `0.9130`
- Gradient-boosted row recall: `1.0`
- Gradient-boosted event recall: `3/3`

Interpretation: supports only the named synthetic primary ensemble. Robustness
failures under structural-null and high-noise settings prohibit autonomous or
topology-independent use.

Primary report:

- [`orchestration/reports/wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md)

### WP13 Synthetic Attribution

Models:

- always-UNKNOWN
- rule-only
- logistic
- hybrid

Primary frozen model: hybrid.

Held-out results:

- Hybrid accuracy/macro recall: `0.8636`
- Hybrid known-cause coverage: `0.85`
- Hybrid selective accuracy: `1.0`
- Rule-only accuracy/macro recall: `0.9242`

Interpretation: conditional synthetic attribution is supported with mandatory
abstention. The rule-only comparator was stronger; this should inform a future
preregistered revision, not a post-hoc model switch.

Primary report:

- [`orchestration/reports/wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md)

## How To Patch In A New Model

### New Early-Warning Model

Use this path when replacing or adding a model that predicts future synthetic
MRR excursions.

Look at:

- [`src/semifab_poc/models/early_warning.py`](../src/semifab_poc/models/early_warning.py)
- [`configs/models/early_warning.yaml`](../configs/models/early_warning.yaml)
- [`configs/controllers/predictive.yaml`](../configs/controllers/predictive.yaml)
- [`configs/controllers/safety.yaml`](../configs/controllers/safety.yaml)
- [`tests/unit/test_early_warning.py`](../tests/unit/test_early_warning.py)
- [`tests/integration/test_warning_chain.py`](../tests/integration/test_warning_chain.py)

Required contract:

- Input must be derived from `WarningObservationWindow`.
- Features must use only observations that arrived by the decision timestamp.
- Forbidden inputs remain forbidden: future MRR, latent CMP state, coupling
  truth, event labels, scenario family, and target labels.
- Output must preserve the `Prediction` fields used by the controller and
  safety filter: calibrated probability, predicted class, conformal set,
  uncertainty validity, feature cutoff time/step, and latency.

After adding a model:

- add or update strict YAML config;
- save artifact and metadata under `reports/early_warning/models`;
- update SHA-256 fields in predictive and safety configs if the model is used
  for control;
- update tests and validation reports.

### New Attribution Model

Use this path when replacing or adding a synthetic root-cause estimator.

Look at:

- [`src/semifab_poc/models/attribution.py`](../src/semifab_poc/models/attribution.py)
- [`configs/models/attribution.yaml`](../configs/models/attribution.yaml)
- [`tests/unit/test_attribution.py`](../tests/unit/test_attribution.py)

Required contract:

- Input must be `AttributionObservationWindow` plus contemporaneous warning
  result.
- It must support the frozen initiating-cause vocabulary plus `UNKNOWN`.
- It must preserve mandatory abstention behavior.
- It must keep `causal_proof=false`.
- It must not use simulator truth, scenario labels, or future samples online.

### New PHM Virtual-Metrology Model

Use this path when adding a public-data average-MRR model.

Look at:

- [`src/semifab_poc/models/virtual_metrology.py`](../src/semifab_poc/models/virtual_metrology.py)
- [`configs/models/virtual_metrology.yaml`](../configs/models/virtual_metrology.yaml)
- [`src/semifab_poc/data`](../src/semifab_poc/data)
- [`tests/unit/test_virtual_metrology.py`](../tests/unit/test_virtual_metrology.py)
- [`tests/integration/test_vm_evaluation.py`](../tests/integration/test_vm_evaluation.py)

Required contract:

- Preserve whole-wafer split boundaries.
- Fit preprocessing only inside the allowed training role.
- Do not use simulator SI quantities.
- Keep the target in source-native undeclared units.
- Do not change target access or model-selection policy after holdout opening.

### New Controller

Use this path when adding a new supervisory policy.

Look at:

- [`src/semifab_poc/control/base.py`](../src/semifab_poc/control/base.py)
- [`src/semifab_poc/control/contracts.py`](../src/semifab_poc/control/contracts.py)
- [`src/semifab_poc/control/predictive.py`](../src/semifab_poc/control/predictive.py)
- [`src/semifab_poc/control/baselines.py`](../src/semifab_poc/control/baselines.py)
- [`configs/controllers`](../configs/controllers)

Required contract:

- A controller proposes an `ActionRecord`; it does not mutate plant state.
- The action must be staged as `PROPOSED`.
- The safety filter must issue the final action.
- One-step effective timing must be preserved.
- New numeric actuation requires a separate scientific justification and
  safety-envelope update.

### New Safety Rule

Use this path when changing safety constraints.

Look at:

- [`src/semifab_poc/control/safety.py`](../src/semifab_poc/control/safety.py)
- [`configs/controllers/safety.yaml`](../configs/controllers/safety.yaml)
- [`tests/unit/test_safety_filter.py`](../tests/unit/test_safety_filter.py)
- [`tests/property/test_safety_properties.py`](../tests/property/test_safety_properties.py)

Required contract:

- Safety filter must remain independent of controller implementation.
- It must return exactly one final action.
- Invalid sensing may authorize hold, but not resume or numeric actuation.
- Rejection, clipping, replacement, and approval outcomes must remain explicit.

## Validation Reports To Read Before Changing Claims

Each major claim has a validation report. Read the relevant report before
changing code, config, or presentation language.

- R1 configuration/schema:
  [`orchestration/reports/r1_contract_configuration_validation.md`](../orchestration/reports/r1_contract_configuration_validation.md)

- R2 PHM semantics:
  [`orchestration/reports/r2_phm_semantics_validation.md`](../orchestration/reports/r2_phm_semantics_validation.md)

- R3 utility-plant physics:
  [`orchestration/reports/r3_plant_physics_validation.md`](../orchestration/reports/r3_plant_physics_validation.md)

- R4 scenario/sensor timing:
  [`orchestration/reports/r4_online_scenario_timing_validation.md`](../orchestration/reports/r4_online_scenario_timing_validation.md)

- WP08 CMP model:
  [`orchestration/reports/wp08_cmp_validation.md`](../orchestration/reports/wp08_cmp_validation.md)

- WP10 utility-to-CMP coupling:
  [`orchestration/reports/wp10_coupling_validation.md`](../orchestration/reports/wp10_coupling_validation.md)

- WP09 public virtual metrology:
  [`orchestration/reports/wp09_virtual_metrology_validation.md`](../orchestration/reports/wp09_virtual_metrology_validation.md)

- WP12 early warning:
  [`orchestration/reports/wp12_early_warning_validation.md`](../orchestration/reports/wp12_early_warning_validation.md)

- WP13 attribution:
  [`orchestration/reports/wp13_attribution_validation.md`](../orchestration/reports/wp13_attribution_validation.md)

- WP15/WP16 control and safety contracts:
  [`orchestration/reports/phase3_control_contract_validation.md`](../orchestration/reports/phase3_control_contract_validation.md)

## Common Development Workflows

### Understand The Current POC

1. Read `README.md`.
2. Read `orchestration/project_status.md`.
3. Read `orchestration/architecture.md`.
4. Read `docs/mathematical_model.md`.
5. Read the specific validation report for the work package you are touching.
6. Inspect the corresponding code and config.

### Change A Physical Simulator Component

1. Identify the subsystem under `src/semifab_poc/simulation`.
2. Check its strict config in `configs/default.yaml`.
3. Read the corresponding decision/report under `orchestration/decisions` and
   `orchestration/reports`.
4. Preserve `DynamicSubsystem` interface behavior.
5. Preserve state/observation separation.
6. Add focused unit/property tests.
7. Update mathematical documentation if equations change.

### Change A Model

1. Identify the evidence plane: PHM public data or synthetic simulator.
2. Update the strict model config.
3. Preserve fit/selection/calibration/test boundaries.
4. Save artifact metadata and hashes.
5. Update validation report language only after validation is rerun.

### Change Controller Behavior

1. Read the WP15 and WP16 decisions.
2. Confirm the proposed action has scientific authority.
3. Update controller contract config.
4. Update safety filter config if action envelopes change.
5. Preserve one-step action timing.
6. Compare against no-action, process-threshold, and utility-threshold
   baselines.

### Update The Dashboard

1. Keep it read-only.
2. Do not introduce new domain logic in dashboard JavaScript.
3. Label synthetic data clearly.
4. Prefer generated artifacts as the source of truth.
5. Check `docs/dashboard_demo_speaker_notes.md` before changing demo language.

## Claim Boundaries To Preserve

This POC does not validate:

- real-fab production control;
- real equipment safety;
- wafer yield improvement;
- scratch, dishing, erosion, corrosion, contamination, delamination, cracking,
  or other physical-defect prevention;
- actual UPW-to-CMP plumbing;
- real-time microsecond response;
- topology-independent early warning;
- causal root-cause proof.

Use wording like:

```text
synthetic simulator result
offline source-native PHM average-MRR prediction
conditional synthetic attribution
bounded supervisory-control demonstration
```

Avoid wording like:

```text
validated fab controller
proven defect prevention
causal diagnosis
production-ready safety system
real-time equipment protection
```

## Known Review Caveat

The documentation and implementation contain a strong handoff trail, but always
check the exact runtime path you are using. In particular, confirm whether
`IntegratedRuntime` is being constructed with real loaded predictor and
estimator artifacts, or with `predictor=None` and `estimator=None` for plumbing
or dashboard demonstrations.

This distinction matters: a runtime plumbing/demo artifact is not the same as a
closed-loop predictive-control efficacy result.

