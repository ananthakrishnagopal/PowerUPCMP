# Project charter

## Project

Semiconductor CMP Predictive-Control Proof of Concept

## Objective

Build a scientifically defensible, simulation-first proof of concept that tests whether a predictive supervisory-control layer can warn of an impending Chemical Mechanical Planarization process excursion caused by simulated electrical and ultrapure-water disturbances, attribute the simulated initiating cause, and reduce the resulting material-removal-rate excursion relative to no intervention and fixed-threshold control without violating predefined simulation safety constraints.

## Research question

Can a predictive supervisory-control layer detect an upcoming CMP process excursion caused by simulated electrical and UPW disturbances, and reduce that excursion relative to no intervention and fixed-threshold control without violating predefined safety constraints?

## Primary validated target

Average material removal rate, written as \(\widehat{MRR}\), is the sole
primary measured target. The PHM 2016 CMP archive is locally present and its
raw integrity, selected schema, training-label joins, native-unit handling,
phase-aware/time-weighted preprocessing, preregistered label-anomaly policies,
source-role construction, and a conservative whole-wafer precedence split are
verified. The source partitions reuse wafer IDs across opposite stages; the
retained training/test/validation roles contain 1,981/311/275 mutually
wafer-disjoint rows. A physical-machine holdout is impossible because only
machine ID 2 is present. The frozen tree supports bounded offline average-MRR
point prediction on these retained roles, with test/validation MAE 3.185/3.395
in the source-native undeclared target scale. Its uncertainty-coverage gate
fails, the physics-plus-residual hybrid does not improve on the tree, and no
SI-unit or control bridge is supported. Simulator-control results remain a
separate SI evidence plane.

## Causal hypothesis under test

```text
Simulated electrical disturbance
→ simulated UPS/VFD response
→ simulated motor and pump response
→ simulated UPW pressure, flow, and thermal response
→ simulated CMP process disturbance
→ simulated MRR excursion
→ early-warning prediction
→ attribution against simulator cause labels
→ safety-filtered supervisory intervention
```

The simulator establishes an explicit mechanistic hypothesis; it does not establish real-fab causality.

## Evidence streams

1. **Public-data virtual metrology:** PHM 2016 CMP data, only after source, licence, checksum, schema, grouping, and leakage controls are verified.
2. **Mechanistic simulation:** electrical, drive, pump, UPW, sensor, CMP, and controller state trajectories with known assumptions and deterministic seeds.
3. **Controlled comparison:** identical disturbance scenarios and random seeds evaluated with no-action, fixed-threshold, and predictive controllers.
4. **Robustness evaluation:** parameter mismatch, sensor corruption, ageing, degradation, tool variation, and unseen compound simulated disturbances.

Public-data predictive accuracy and simulation-control efficacy must be reported separately.

## In scope

- Average MRR virtual metrology and uncertainty.
- Tool-state and consumable-age features.
- Electrical disturbance, UPS, VFD, motor, pump, UPW hydraulic/thermal, sensor, and CMP process simulation.
- Explicit utility-to-CMP connection topologies and typed boundary conditions
  with provenance classifications, including zero-link and no-connection
  structural controls.
- Declarative deterministic scenarios.
- Horizon-based active-polish MRR and predicted cumulative-removal early
  warning.
- Root-cause classification evaluated against simulator labels, supported by residual and rule-chain evidence.
- No-action, threshold, and bounded predictive supervisory controllers.
- Independent safety filtering, hold, and controlled resume.
- Reproducible batch and Monte Carlo evaluation.
- Synthetic spatial-uniformity proxies only when labelled exactly as required.

## Out of scope and prohibited claims

The proof of concept will not claim validated prediction or prevention of scratches, dishing, erosion, corrosion, particle contamination, delamination, cracking, real wafer-yield loss, real equipment damage, real production control, or microsecond production response. It will not use reinforcement learning in the initial PoC. It will not deploy to equipment or issue real actuator commands.

## Required semantic distinctions

Every schema, report, plot, and dashboard must distinguish:

- measured process output;
- simulated physical state;
- process excursion;
- quality-risk proxy;
- physical defect; and
- yield outcome.

A simulated state is not a measurement. An excursion is not a defect. A risk proxy is not a yield outcome.

## Success criteria

The PoC is successful only if all of the following are demonstrated reproducibly:

1. The integrated simulator deterministically propagates at least the reference 25% voltage sag for 400 ms through the complete declared causal chain.
2. No-action, arrived process-MRR threshold, predictive control, and the
   mandatory upstream utility-threshold comparator use identical scenario
   definitions, initial conditions, seeds, sensor corruptions, and model
   parameters within each comparison.
3. Predictive control reduces both peak MRR deviation and integrated absolute MRR error relative to no action for the predefined primary scenario set.
4. Relative to the primary arrived process-MRR threshold, predictive control
   improves at least one of peak MRR deviation or integrated absolute MRR
   error by the preregistered amount without worsening the other or cumulative
   removal beyond the preregistered tolerance. Results against the upstream
   utility threshold are always reported separately.
5. No final action violates configured magnitude, slew-rate, sensor-validity, uncertainty, process-envelope, hold, or restart constraints.
6. Early-warning results include precision, recall, PR-AUC, false alarms per simulated hour, missed-event rate, median warning time, and uncertainty/coverage evidence.
7. Root-cause accuracy is evaluated against simulator truth and never presented as causal proof for real equipment.
8. All coupling coefficients and model parameters have a provenance class, units, bounds, and sensitivity result.
9. All public-data results, if any, use leakage-safe grouped or temporal splits and are reported separately from simulator results.
10. Every controller completes the same recipe scope, or is explicitly marked
    as a failed completion at the frozen extension limit; comparisons align by
    active-polish progress and report hold, recovery, and cycle-time costs.
11. Installation, tests, reference runs, reports, and the dashboard reproduce
    from documented commands.

The Phase 3 controller and safety decisions preregister the numerical model-
comparison gates, seed ranges, synthetic operating envelopes, hold/restart
conditions, and latency budgets. They must not be changed after Phase 4 TEST
access to obtain a favorable result.

## Deliverables

- Installable Python package and CLI.
- Canonical schema, provenance records, dataset manifests, and validated loaders.
- Modular deterministic simulator and scenario engine.
- Virtual-metrology and early-warning model comparisons.
- Root-cause estimator, baseline controllers, predictive controller, and independent safety filter.
- Integrated runtime, evaluation suite, dashboard, automated report, and final audit.
- Tests covering equations, properties, integrations, regressions, scientific checks, and reproducibility.

## Governance

- The user owns changes to scope, primary claims, external data access, credentials, deployment, and irreversible decisions.
- The sole engineering agent owns implementation within approved scope and the frozen contracts.
- `orchestration/task_manifest.yaml` is the task source of truth.
- `orchestration/interface_registry.yaml` and `orchestration/canonical_schema.yaml` are frozen after Phase 1 and require a decision record, impact analysis, tests, and documentation to change.
- Unexpected failures trigger the stop-and-report procedure.
- Phase boundaries require a checkpoint and manual model switch when recommended.
