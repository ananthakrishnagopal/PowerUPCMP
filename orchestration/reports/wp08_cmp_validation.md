# WP08 CMP physics validation

Date: 2026-07-11  
Task: T-WP08  
Decision: `orchestration/decisions/wp08_cmp_physics.md`  
Evidence plane: synthetic simulator only  
Environment: conda `devkki`, Python 3.13.12

## Outcome

The reduced-order CMP subsystem satisfies its frozen dimensional, limiting,
state-transition, numerical, and claims-boundary acceptance tests. This
supports use of the model as a bounded synthetic CMP plant in later coupling
and control experiments. It does not validate a real material stack, tool,
spatial metrology, physical defect, yield outcome, or production controller.

Focused CMP and impacted contract tests passed 48/48. The complete repository
suite passed 130/130 in 38.09 s.

Machine-readable evidence:

- `reports/cmp/wp08_validation.json`
- `reports/cmp/wp08_reference_trace.csv`
- reference-trace SHA-256:
  `902fa4283ef8cf2150efef14aa08ca6f478aad55503e6d9b111584c33175626e`
- canonical runtime-config SHA-256:
  `99d7876eb76d561de97ed577d77da30e929c70276070bb6f84df0fb9c9e91670`

## Reference normalization and dimensions

The 16 radial by 64 angular quadrature gives the nominal power-mean relative
velocity

\[
V_0=1.6070416183328249\ \mathrm{m/s}.
\]

At 30,000 Pa, platen/head speeds 8/6 rad/s, unit slurry availability, fresh
consumables, and neutral recipe/thermal modifiers, the normalized exposure is
0.9999999999999999. The instantaneous reference MRR is

\[
R_0=1.6666666666667\times10^{-9}\ \mathrm{m/s}
=100.000000000002\ \mathrm{nm/min}.
\]

For the classical \(\alpha=\beta=1\) baseline, the derived coefficient is

\[
K_P=3.4570078908840606\times10^{-14}\ \mathrm{Pa}^{-1}.
\]

Thus \(K_PP_0V_0=R_0\) to floating-point tolerance. Zero pressure and zero
speed each produce exactly zero exposure and zero removal.

## Kinematics and quadrature

The implementation subtracts signed platen and wafer velocity vectors.
Equal co-rotation gives the exact constant field
\(|\omega_pr_{cc}|\); both axes stopped give zero. Counter-rotation produces a
nonuniform local velocity field without converting signed angular speeds to
magnitudes.

The constant-field integral differs from one by at most
\(2.22\times10^{-16}\) across 8x32, 16x64, 32x128, and 48x192 grids. The area
mean nominal velocity differs from the 48x192 result by at most
\(4.44\times10^{-16}\) m/s across those grids. This smooth reference case is
quadrature-converged well below the declared tolerance.

The nominal annular exposure coefficient of variation is
0.0025316618572622336. It is reported only as:

> Simulated spatial-uniformity proxy; not experimentally validated WIWNU.

It is not measured WIWNU and has no public-data validation.

## Process modes and cumulative removal

The deterministic reference run contains 1 s PREPARE, 5 s POLISH, and 1 s
HOLD at 10 ms. PREPARE and HOLD have exactly zero MRR. Only the 5 s POLISH
interval increases active time and cumulative removal. Final values are:

- active polish time: 4.999999999999938 s;
- cumulative removal: 8.276153498157771e-9 m;
- stage-average MRR: 1.6552306996315749e-9 m/s.

The average is below the fresh-pad 100 nm/min reference because the trace
includes explicit pad-surface decay during active polish. HOLD retains the
cumulative thickness and active time while pressure, speed, and slurry states
decay; it does not score as active zero-MRR polishing.

Transition tests also verify forced HOLD, explicit hold reason, and 0.5 s of
continuous valid RECOVER dwell before POLISH can resume. COMPLETE is terminal
until reset.

## Consumable behavior

A 10 s DRESS limiting case starts with pad activity 0.5, remaining pad life
0.8, and dresser effectiveness 0.9. It ends with:

- pad activity 0.5823912561285373;
- remaining pad life 0.7994999999999968;
- dresser effectiveness 0.8998200179088174;
- instantaneous MRR exactly zero.

This confirms the frozen structure: dressing can restore reversible surface
activity while consuming irreversible pad life and dresser effectiveness.
Long-polish/dress property tests keep all three states inside [0,1]. The rates
and resulting magnitudes remain synthetic assumptions.

## Interface thermal balance

Across the 700-step reference trace, the maximum absolute discrete energy
residual is

\[
\max|e_E|=1.4188941577231162\times10^{-8}\ \mathrm{W},
\]

below the 1e-7 W audit tolerance. With the default structural-null
\(\beta_T=0\), cold and warm coolant boundaries move interface temperature to
292.7859817900356 K and 293.567268397958 K after 1 s but yield an exact zero
instantaneous-MRR difference. Thermal-to-MRR coupling is therefore absent in
the conservative default and cannot arise without a named configuration
change.

## Timestep refinement

The 70% pressure-command case was integrated for 1 s. Errors are measured
against a 1 ms reference.

| dt (s) | pressure error (Pa) | temperature error (K) | cumulative-removal error (m) |
|---:|---:|---:|---:|
| 0.0400 | 25.8847 | 2.84038e-4 | 1.91408e-11 |
| 0.0200 | 13.5017 | 1.38008e-4 | 9.30209e-12 |
| 0.0100 | 6.60095 | 6.52796e-5 | 4.40054e-12 |
| 0.0050 | 2.97872 | 2.89921e-5 | 1.95449e-12 |
| 0.0025 | 1.12539 | 1.08681e-5 | 7.32688e-13 |

All three error measures decrease monotonically under refinement. The default
10 ms step is within the component's explicit-update bound; later coupled and
controller studies must repeat convergence under their final topology and
parameter ensemble.

## Contract and provenance checks

- CMP implements immutable `DynamicSubsystem` 2.0.0 state transitions.
- Canonical schema 2.3.0 adds explicit mode, exposure, health, interface,
  cumulative, and average-MRR signals; signed angular speed records direction.
- Interface registry 3.1.0 adds `CmpBoundaryConditions` without changing the
  DynamicSubsystem method signature.
- Frozen R3 and R4 canonical configuration hashes remain reproducible.
- Every CMP configuration parameter except its registry ID has one of the
  required provenance classes; no value is marked data-calibrated.
- Unknown action and boundary keys, nonfinite values, invalid transitions, and
  out-of-envelope values are rejected.
- The CMP boundary accepts no raw voltage, VFD, pump, UPW, or sensor-corruption
  key and contains no generic MRR multiplier.
- Fixed input history replays exactly.

## Acceptance matrix

| Acceptance item | Result |
|---|---|
| generalized-Preston units/exposure/reference | PASS |
| mode-gated material removal | PASS |
| signed dual-axis kinematics | PASS |
| deterministic quadrature convergence | PASS |
| bounded consumable/slurry/thermal/cumulative states | PASS |
| fully synthetic neutral-boundary mode | PASS |
| finite nonnegative true MRR | PASS |
| exact spatial-proxy label | PASS |
| energy residual audit | PASS |
| timestep refinement | PASS |
| deterministic replay | PASS |
| pre-existing regression suite | PASS |

## Remaining scientific boundary

WP08 does not demonstrate electrical-to-CMP propagation. WP10 must separately
freeze, implement, and test each dressing-water, thermal-loop, explicitly
synthetic slurry-support, and no-connection topology. Every link requires
units, sign, bounds, provenance class, zero-link behavior, sensitivity, and
mismatch evidence. Until then, claims C-002 through C-010 remain unchanged
except for the narrow supported claim that this synthetic CMP subsystem
satisfies its declared equations and invariants.
