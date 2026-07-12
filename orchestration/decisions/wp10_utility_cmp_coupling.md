# Decision: WP10 utility-to-CMP coupling

Date: 2026-07-11  
Status: FROZEN FOR IMPLEMENTATION AND TASK-LOCAL VALIDATION  
Task: T-WP10  
Scientific basis: `orchestration/reports/wp10_literature_review.md`  
Upstream contract: `orchestration/decisions/wp08_cmp_physics.md`

## Decision summary

Amendment after pre-implementation invariant review: the thermal map uses
distinct CMP-neutral and UPW-reference temperatures. This null-preserving
correction was authorized after the invariant report dated 2026-07-11.

WP10 will implement a deterministic, stateless, typed coupler from validated
latent `UpwState` to the already frozen `CmpBoundaryConditions`. It will not
accept raw electrical, UPS, VFD, or pump values and will not produce MRR. The
full causal chain is obtained by ordered composition of the existing plant
subsystems, the coupler, and the CMP subsystem.

Four mutually exclusive structural topologies are frozen:

1. `NO_CONNECTION` — mandatory repository default and structural null;
2. `DRESSING_WATER_SUPPORT` — primary connected PoC topology;
3. `THERMAL_LOOP` — conditional thermal connection;
4. `SYNTHETIC_SLURRY_SUPPORT` — explicitly synthetic structural sensitivity.

All outputs are synthetic physical boundary states. No topology is asserted to
describe the PHM challenge tool or a real fab.

## Why a direct MRR multiplier remains prohibited

The local literature supports water use in pad conditioning/rinsing, pad-state
memory, slurry mixing/availability effects, and dynamic thermal behavior. It
does not calibrate facility-header pressure/flow thresholds or actual PHM tool
plumbing. A direct relation such as `MRR = MRR0 * f(UPW pressure)` would skip
the physical intermediate and make controller performance an artifact of a
chosen gain. The typed boundary instead preserves:

```text
electrical disturbance
→ UPS/VFD/motor/pump
→ latent UPW pressure, flow, temperature
→ explicitly selected coupling topology
→ CMP boundary state
→ CMP pad/slurry/thermal dynamics
→ simulated MRR
```

## Interface and causality

The coupler has the pure interface

```text
couple(upw_state, upw_config, cmp_config) -> CouplingResult
```

`CouplingResult` contains a frozen `CmpBoundaryConditions` plus finite,
unit-declared diagnostics. It has no internal memory. Memory belongs to the
physical subsystem affected by the boundary: pad activity for dressing,
slurry availability for synthetic slurry support, and interface temperature
for the thermal loop.

The input is latent simulator state because the coupler represents a physical
connection. Online predictors and controllers remain restricted to arrived
sensor observations. Sensor faults cannot alter latent coupling physics.

The coupler never asserts `force_hold`, rejects/approves an action, or changes
`utilities_valid`; these are safety/control semantics and will be handled by
WP16. A severe but numerically valid utility state remains valid plant state.

## Hydraulic availability map

Let (P_s) be UPW supply pressure and (Q_t) be tool-branch flow. Define
dimensionless ratios

\[
p=P_s/P_{ref},\qquad q=Q_t/Q_{ref}.
\]

For lower and upper fractions (x_0<x_1), define the continuous bounded ramp

\[
R(x;x_0,x_1)=\operatorname{clip}
\left(\frac{x-x_0}{x_1-x_0},0,1\right).
\]

Pressure and flow support are

\[
a_P=R(p;p_0,p_1),\qquad a_Q=R(q;q_0,q_1).
\]

The raw hydraulic support is the bottleneck

\[
a_h=\min(a_P,a_Q).
\]

The minimum is used instead of a product because pressure and flow are
correlated outputs of the same hydraulic network. Multiplication would
double-count a common disturbance and create a stronger unsupported
nonlinearity. The bottleneck relation is an engineering approximation, not a
calibrated tool curve.

With declared link strength \(\lambda\in[0,1]\), effective availability is

\[
a_{eff}=1-\lambda(1-a_h).
\]

This form freezes two exact nulls:

- \(\lambda=0\Rightarrow a_{eff}=1\) for every UPW state;
- normal support \(a_h=1\Rightarrow a_{eff}=1\) for every link strength.

It is monotone nondecreasing in supply pressure and tool flow and
nonincreasing in link strength whenever support is degraded.

## Topology maps

Let \(T_u\) be UPW temperature, \(T_{u,ref}\) its configured upstream
reference, and \(T_{c,0}\) the CMP subsystem's frozen neutral coolant
temperature.

| Topology | CMP boundary output | Required interpretation |
|---|---|---|
| `NO_CONNECTION` | \(a_d=1,\ a_s=1,\ T_c=T_{c,0},\ f_{UA}=1\) | Exact neutral boundary; configuration requires \(\lambda=0\). |
| `DRESSING_WATER_SUPPORT` | \(a_d=a_{eff}\); all other fields neutral | Only DRESS conditioning activity is reduced. Subsequent MRR changes through stored pad-surface activity. |
| `THERMAL_LOOP` | \(T_c=T_{c,0}+\lambda(T_u-T_{u,ref})\), \(f_{UA}=a_{eff}\); availability fields neutral | Conditional heat-transfer connection. Zero link and nominal UPW temperature are exact boundary nulls; default \(\beta_T=0\) also preserves an exact MRR null. |
| `SYNTHETIC_SLURRY_SUPPORT` | \(a_s=a_{eff}\); all other fields neutral | Artificial common-utility dependency used only for structural sensitivity. It is not inferred from CMP slurry plumbing. |

`process_discrepancy_m_s` remains zero in every topology. The water-quality
deviation proxy is logged upstream but has no coupling effect.

## Frozen synthetic reference and threshold values

The nominal connected profiles use:

| Parameter | Nominal | Unit | Hard validity bounds | Sensitivity range | Provenance class | Expected effect |
|---|---:|---|---|---|---|---|
| link strength \(\lambda\) | 1.0 connected; 0.0 default | 1 | [0, 1] | [0, 1] including zero | Synthetic assumption | Greater value increases the magnitude of a degraded connection; no effect at healthy support. |
| reference supply pressure \(P_{ref}\) | 300000 | Pa | positive finite | [250000, 350000] | Synthetic assumption | At fixed pressure, a larger reference generally lowers normalized support. |
| pressure zero fraction \(p_0\) | 0.60 | 1 | [0, 1), below \(p_1\) | [0.40, 0.75] | Synthetic assumption | Increasing it can reduce support in the transition region. |
| pressure full fraction \(p_1\) | 0.95 | 1 | (0, 1], above \(p_0\) | [0.85, 1.00] | Synthetic assumption | Increasing it can reduce support in the transition region. |
| reference tool flow \(Q_{ref}\) | 0.0001 | m³/s | positive finite | [0.00008, 0.00012] | Synthetic assumption | At fixed flow, a larger reference generally lowers normalized support. |
| flow zero fraction \(q_0\) | 0.50 | 1 | [0, 1), below \(q_1\) | [0.30, 0.70] | Synthetic assumption | Increasing it can reduce support in the transition region. |
| flow full fraction \(q_1\) | 0.95 | 1 | (0, 1], above \(q_0\) | [0.85, 1.00] | Synthetic assumption | Increasing it can reduce support in the transition region. |
| reference UPW temperature \(T_{u,ref}\) | 293.15 | K | inside the configured UPW thermal envelope | [288.15, 298.15] | Synthetic assumption | Defines the upstream temperature deviation; the neutral CMP boundary remains independently fixed by `CmpConfig`. |

The ramp and bottleneck functional forms are classified as **Engineering
approximation**. The existence of DI-water conditioning, pad-state memory, and
dynamic heat/slurry pathways is **Literature-supported**. No WP10 numerical
coupling coefficient is `Data-calibrated` or `Literature-supported`.

## Structural and parameter uncertainty

The sensitivity report must include all four topologies and zero link strength.
It must not condition the choice of topology or coefficient on which one makes
predictive control look best.

Task-local analysis will include:

1. exact structural null tests for `NO_CONNECTION` and \(\lambda=0\);
2. limiting cases at zero, transition, full, and above-reference pressure/flow;
3. monotonic property tests away from floating-point tolerance boundaries;
4. centered finite-difference local sensitivity at declared off-kink points;
5. a deterministic seeded global variance-based analysis over preregistered
   parameter ranges for connected cases;
6. explicit parameter-mismatch cases comparing nominal controller-model
   assumptions with weaker, stronger, earlier, and later physical links;
7. identical-seed topology comparison using the same upstream plant trace.

Because `min` and `clip` are nonsmooth at their knots, derivatives at a knot
are undefined and will not be reported as local physical sensitivities.

## Validation scenarios

### Structural negative controls

- nominal plant, all topologies: connected boundary must be neutral when both
  support ramps equal one;
- arbitrary bounded UPW trace with `NO_CONNECTION`: CMP boundary and MRR must
  equal the neutral trace exactly;
- arbitrary bounded UPW trace with \(\lambda=0\): same exact equality;
- healthy-UPS 25% voltage sag for 400 ms: retain the R3 result as a negative
  control and do not tune coupling to create an excursion.

### Positive causal demonstration for WP10

A separately named **synthetic degraded-UPS interruption during DRESS** will
be used to exercise the complete electrical→UPW→CMP pathway. The UPS energy
capacity, disturbance duration, dressing window, and initial pad activity are
declared in the evidence artifact. The connected and null runs use identical
plant parameters, exogenous event, initial state, timestep, and seed. The
expected chain is:

```text
grid interruption
→ depleted synthetic UPS and reduced drive output
→ VFD trip/derating and pump-speed loss
→ UPW supply pressure/flow loss
→ lower dressing availability during DRESS
→ lower stored pad-surface activity
→ lower subsequent POLISH MRR
```

This scenario demonstrates the model’s declared causal mechanics. It does not
show a real-fab response or validate the chosen UPS/coupling values.

## Numerical and safety constraints

- All config and state inputs are immutable, finite, and strictly validated.
- Threshold pairs must be ordered and fractions remain within [0, 1].
- Reference pressure/flow are strictly positive.
- Reference UPW temperature must lie in the configured UPW envelope; every
  mapped coolant temperature must lie in the CMP envelope.
- Coupling outputs must validate through `CmpBoundaryConditions`.
- The coupler introduces no timestep and cannot destabilize the upstream
  conserved hydraulic solver.
- The physical coupler does not inspect corrupted observations, predict,
  attribute, control, or safety-filter.

## Interface and schema impact analysis

This is an additive change:

- add `CouplingConfig`, `UtilityCmpTopology`, `CouplingResult`, and
  `UtilityToCmpCoupler` under `simulation/coupling.py`;
- add coupling configuration to the current runtime profile;
- add latent coupling diagnostics to the canonical signal catalog;
- retain `DynamicSubsystem` 2.0.0 unchanged because the stateless coupler is
  not a dynamic subsystem;
- retain `CmpBoundaryConditions` 1.0.0 fields unchanged;
- add and freeze a `UtilityToCmpCoupler` 1.0.0 interface;
- advance schema/interface versions additively while preserving the exact R3,
  R4, and WP08 canonical hashes through compatibility exclusions;
- update unit, property, integration, governance, configuration, mathematical,
  and running-paper documentation.

## Claim boundary

WP10 may support only the statement that the synthetic simulator propagates a
declared disturbance through its declared topology while satisfying null,
boundedness, monotonicity, replay, and sensitivity checks. It cannot validate
actual tool plumbing, a real electrical/UPW causal effect, physical defects,
yield, equipment protection, production control, or controller efficacy.
