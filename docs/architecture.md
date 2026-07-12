# Implementation architecture status

The Phase 1 architecture and its corrective-audit disposition are maintained
in [`orchestration/architecture.md`](../orchestration/architecture.md).
Phase 2 components, corrective gates R1--R4, and the standalone WP08 CMP
subsystem are validated. Utility-to-CMP coupling, prediction, and control
remain unimplemented. The approved redesign basis is documented in
[`phase_3_cmp_model_redesign.md`](../orchestration/reports/phase_3_cmp_model_redesign.md).
Frozen CMP equations and evidence are documented in
[`mathematical_model.md`](mathematical_model.md)
and
[`wp08_cmp_validation.md`](../orchestration/reports/wp08_cmp_validation.md).

The package must preserve:

- canonical SI units inside the simulator while preserving PHM native/unknown
  source units in the public-data plane;
- separate latent simulator state and observed sensor state;
- one-step action timing to prevent algebraic loops and target leakage;
- controller proposals separated from independent safety decisions; and
- public measured data separated from synthetic simulator evidence.
