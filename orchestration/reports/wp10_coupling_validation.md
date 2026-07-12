# WP10 utility-to-CMP coupling validation

Date: 2026-07-11  
Task: T-WP10  
Evidence plane: synthetic simulator  
Status: VALIDATED; task-local checks, 50/50 impacted tests, 154/154 full tests, frozen reproduction, strict configuration, and governance pass

## Scope and claim boundary

WP10 implements and validates a declared boundary map from latent UPW state to
the frozen CMP subsystem. It demonstrates only the behavior of the synthetic
models under the declared topologies and parameters. It does not validate the
plumbing of the PHM challenge tool, a real fab, public-data utility coupling,
physical defects, yield, equipment protection, production control, or
controller efficacy.

The local ten-paper review is in
[`wp10_literature_review.md`](wp10_literature_review.md). Literature supports
the existence of DI-water conditioning, pad-state memory, slurry/rinse
interaction, and thermal pathways. No reviewed source calibrates the numerical
header-pressure/flow thresholds or link strengths used here.

## Implemented topology contract

The stateless coupler consumes `UpwState` and returns `CouplingResult`, whose
only process input is the already frozen `CmpBoundaryConditions`. Raw
electrical, UPS, VFD, pump, and sensor values are not accepted. The coupler
does not compute MRR, force a hold, set process discrepancy, control an action,
or inspect the water-quality proxy.

For dimensionless pressure and flow ratios

\[
p=P_s/P_{ref},\qquad q=Q_t/Q_{ref},
\]

the support ramp is

\[
R(x;x_0,x_1)=\operatorname{clip}\left(
\frac{x-x_0}{x_1-x_0},0,1\right).
\]

The hydraulic bottleneck and link blend are

\[
a_h=\min\{R(p;p_0,p_1),R(q;q_0,q_1)\},
\]

\[
a_{eff}=1-\lambda(1-a_h).
\]

The minimum avoids multiplying two correlated outputs of the same hydraulic
network. Both this choice and the ramp are engineering approximations. All
numerical coupling coefficients are synthetic assumptions.

The frozen structures are:

- `NO_CONNECTION`: exact neutral boundary and mandatory default;
- `DRESSING_WATER_SUPPORT`: `dressing_availability = a_eff` only;
- `THERMAL_LOOP`: cooling conductance equals `a_eff` and
  \(T_c=T_{c,0}+\lambda(T_u-T_{u,ref})\);
- `SYNTHETIC_SLURRY_SUPPORT`: `slurry_utility_availability = a_eff` only.

The corrected thermal map distinguishes the CMP-neutral coolant reference
from the UPW reference. Therefore zero link is exactly neutral for any UPW
temperature, and nominal UPW temperature is neutral for any link strength.
The default CMP temperature sensitivity is zero, so the thermal-to-MRR path
also remains an exact structural null in the current material profile.

## Configuration and provenance

Current schema/interface versions are 2.4.0/3.2.0. The complete default
runtime hash is
`b2b07edbaad458f6f66cf26ce88ffc5deef656a33701a7cccd8da94104d7383f`.
The default topology is `NO_CONNECTION` with link strength zero. R3, R4, and
WP08 legacy hashes remain exactly reproducible; coupling is excluded only when
serializing those earlier contract versions.

The nominal connected thresholds are 300 kPa reference supply pressure,
100 mL/s reference tool flow, 0.60/0.95 pressure zero/full fractions, and
0.50/0.95 flow zero/full fractions. These values define the synthetic
experiment; they are not operating requirements for any real CMP tool.

Every numerical `CouplingConfig` field has a machine-readable unit, hard
bound, sensitivity range, expected direction, and `Synthetic assumption`
classification. Functional forms are separately classified. The parameter
registry is embedded in
[`wp10_coupling_validation.json`](../../reports/sensitivity/wp10_coupling_validation.json).

## Negative control

The healthy-UPS 25% voltage sag lasting 400 ms was replayed through the full
electrical, drive, pump, UPW, coupler, and CMP sequence after a 3 s plant
warm-up. The DRESS window lasted 6 s, PREPARE lasted 1 s, and POLISH began at
7 s.

Minimum UPS output was 0.865536 pu, minimum motor speed was
187.16567425102727 rad/s, minimum pump flow was
1.9724374643984813e-4 m³/s, and minimum supply pressure was
298879.7567319125 Pa. Tool flow stayed at 1.0e-4 m³/s. Both hydraulic and
effective support remained exactly one.

The connected and no-connection upstream traces were identical. Their pad
activity, MRR, and cumulative-removal traces were also exactly identical. The
connected negative-control trace hash is
`f8359518903a8def6e02d03a8bc73123cc8a32dc5c32ed39dabc26745bfc3f20`.
This confirms that the coupling was not tuned to turn a well-ridden-through
electrical sag into an artificial CMP excursion.

## Positive declared causal chain

The positive task-local case is a synthetic degraded-UPS interruption during
DRESS. It uses 500 J initial/capacity, a 2500 W load, 0.95 inverter efficiency,
a forced grid interruption from 1 to 4 s, and an explicit VFD restart request.
This is a stress-test configuration, not a real UPS specification.

Observed onset times were:

| Event | First source time (s) |
|---|---:|
| Grid interruption | 1.00 |
| UPS output below 0.9 pu | 1.03 |
| Pump flow below 99% reference | 1.04 |
| Motor speed below 99% nominal | 1.19 |
| UPW pressure below full-support threshold | 1.24 |
| Effective coupling availability below one | 1.24 |
| POLISH start | 7.00 |

The minimum UPS output approached zero, pump flow reached zero, supply
pressure approached the 100 kPa return boundary, tool flow approached zero,
and dressing availability reached zero. The no-connection and connected runs
used identical upstream states.

| Metric | No connection | Dressing-water support | Relative decrease |
|---|---:|---:|---:|
| Pad activity at end of DRESS | 0.5511876609 | 0.5216572820 | 5.3576% |
| Mean MRR during subsequent POLISH (m/s) | 1.0198314108e-9 | 9.8727270376e-10 | 3.1926% |
| Final cumulative removal (m) | 2.0396628215e-9 | 1.9745454075e-9 | 3.1926% |

MRR remains exactly zero during DRESS in both cases. The later difference is
therefore mediated by stored pad-surface activity rather than a direct or
instantaneous UPW-to-MRR multiplier. No threshold was selected from this
outcome; the topology, values, and sensitivity ranges were frozen first.

The no-connection and connected positive trace hashes are respectively
`3560cb28a4cc8e87d778146f2cf0964290d733da2a0b59bee283659644ae41fc`
and
`19f440b2fd31959c619c31b851003ac496ff4d3b66c1643a6c6fbbb4951dfa10`.

## Local and global sensitivity

Centered finite differences were evaluated at off-kink pressure-limiting,
flow-limiting, and thermal-deviation states. Signs match the frozen
expectations: increasing link strength, reference pressure/flow, or either
transition threshold reduces availability at the selected transition points;
increasing the UPW reference temperature changes mapped coolant temperature
with derivative -0.5 for the 0.5-link thermal case. Derivatives at ramp/minimum
knots are deliberately not reported.

Global analysis used seeded Saltelli pick-freeze Monte Carlo estimators with
seed 20260711, 4096 base samples, seven independently sampled parameters, and
36,864 coupler evaluations at a representative degraded state. Raw estimates
are retained without clipping or renormalization.

| Parameter | First-order estimate | Total-order estimate |
|---|---:|---:|
| Link strength | 0.5268 | 0.6127 |
| Reference supply pressure | 0.1551 | 0.2603 |
| Pressure zero fraction | 0.0875 | 0.1147 |
| Pressure full fraction | 0.0194 | 0.0201 |
| Reference tool flow | 0.0971 | 0.1705 |
| Flow zero fraction | 0.0038 | 0.0718 |
| Flow full fraction | 0.0178 | 0.0128 |

These indices rank uncertainty within this chosen state, range, topology, and
output. They are not empirical feature importance, causal proof, or a basis to
claim actual tool sensitivity. Small first/total inconsistencies can occur in
finite-sample estimators and are preserved rather than cosmetically corrected.

Mismatch cases include zero, 0.25, and 1.0 link strengths plus earlier- and
later-response threshold sets. Mean later MRR spans
9.8585309520e-10 to 1.0198314108e-9 m/s across those cases. Zero link exactly
matches no connection, confirming that the size of the simulated effect is
materially contingent on structural and parameter assumptions.

## Numerical correction exposed during validation

The first positive evidence run exposed an upstream exact-depletion roundoff:
nineteen 26.315789473684212 J draws from 500 J produced
-1.4921397450962104e-13 J. The electrical model now preserves its existing
energy decision and projects only the accepted subtraction residue to the
configured minimum. An exact-multiple regression test verifies that the
exhausted interval ends at zero and the next unsupported interval enters
BYPASS. This is a numerical-bound correction, not a change in UPS physics.

R3 was regenerated after the fix. Its healthy-sag reference remains unchanged
in interpretation: tool flow is unchanged; maximum pressure deviation is
1118.5096867848188 Pa; pump-curve residual is
5.820766091346741e-11 Pa; and hydraulic residual remains below 1e-12 m³/s.

## Validation inventory

Task-local evidence currently includes:

- exact no-connection and zero-link nulls;
- nominal neutral behavior for all four topologies;
- strict threshold/reference/topology validation;
- boundary-field isolation by topology;
- water-quality proxy non-effect;
- bounded and monotone pressure/flow support;
- default thermal-to-MRR structural null;
- delayed DRESS-to-POLISH pad-memory effect;
- deterministic full-chain replay and identical upstream projections;
- pump-curve and hydraulic-balance residual checks;
- local, global, structural, and mismatch sensitivity;
- 50/50 WP10-impacted tests passing in conda environment `devkki`;
- 154/154 complete repository tests passing in 43.92 s;
- exact frozen WP08 trace reproduction under additive compatibility;
- strict default configuration validation at schema/interface 2.4.0/3.2.0;
- governance validation of 14 YAML files, 27 acyclic tasks, 25 assumptions,
  and 72 Markdown files with zero missing local links.

No control comparison, early warning, attribution, or safety filter has been
implemented or validated by WP10.
