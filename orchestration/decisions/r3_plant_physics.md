# Decision: R3 conserved utility-plant model

Date: 2026-07-11  
Status: APPROVED IMPLEMENTATION BASIS  
Gate: T-PHASE12-REMEDIATION / R3  
Owner: sole engineering agent  
User authorization: recorded in the active conversation

## Context

The Phase 1/2 retrospective audit showed that the existing pump independently
imposed flow and head, while the UPW model clipped pressure to a pump-head
ceiling. That combination did not identify a pump/system operating point,
could destroy mass at the pressure clip, collapsed pressure immediately on a
pump trip, and reported flows evaluated at a different time than the stored
pressure. The electrical configuration declared frequency dynamics without an
output-frequency state and described UPS energy limitation without battery
energy, load, or capacity. The thermal node used tool flow rather than pump
inflow for flushing. Finally, a numerical `conductivity_proxy` had unit S/m and
was readily confusable with measured conductivity.

## Decision

### Pump curve and operating point

Use a bounded quadratic rotodynamic-pump curve around a synthetic reference
point:

\[
H_p(Q,n,d)=d H_{shut}n^2-k_Q Q^2,
\qquad
k_Q=\frac{H_{shut}-H_{ref}}{Q_{ref}^2},
\]

where \(n=\omega/\omega_{ref}\), \(d\in[0,1]\) is an explicitly synthetic
head-degradation factor, head is in Pa, and flow is in m³/s. At network
differential pressure \(\Delta P\), the open-check-valve operating flow is

\[
Q_p=\sqrt{\frac{\max(dH_{shut}n^2-\Delta P,0)}{k_Q}}.
\]

If \(\Delta P\) exceeds shutoff head, the check valve is closed and reverse
flow is excluded. Shaft power is approximated by

\[
P_{shaft}=\frac{Q_p\Delta P}{\eta_p}.
\]

The cube law is tested only along homologous points
\((Q,H)=(nQ_{ref},n^2H_{ref})\); it is not imposed independently at arbitrary
network pressures. The Department of Energy pump guides support the use of
pump/system curve intersection and warn that simple affinity scaling can be
misleading when the system curve changes:

- https://www.energy.gov/sites/prod/files/2014/05/f16/variable_speed_pumping.pdf
- https://www.energy.gov/sites/default/files/2014/05/f16/pump.pdf

The curve shape, reference point, constant efficiency, and degradation factor
are engineering approximations/synthetic assumptions, not manufacturer data.

### Conserved hydraulic compliance

For supply pressure \(P_s\), return pressure \(P_r\), compliance \(C_h\), and
one interval's pump inflow \(Q_p\), solve the backward-Euler balance

\[
\frac{C_h(P_s^{k+1}-P_s^k)}{\Delta t}
=Q_p^k-Q_t(P_s^{k+1})-Q_r(P_s^{k+1})-Q_{rel}(P_s^{k+1}),
\]

with

\[
Q_t=\min\left(Q_{demand},
u_v\frac{\max(P_s-P_r,0)}{R_t}\right),
\quad
Q_r=\frac{\max(P_s-P_r,0)}{R_r},
\]

\[
Q_{rel}=\frac{\max(P_s-P_{rel,set},0)}{R_{rel}}.
\]

The scalar balance is continuous and strictly increasing because
\(C_h/\Delta t>0\); deterministic bisection therefore gives a unique bounded
solution when the configured relief capacity is adequate. Pressure is never
silently clipped. Lack of a bracket is an out-of-envelope model error. The
stored flows are evaluated at the new pressure, and the discrete residual

\[
r_m=Q_p-Q_t-Q_r-Q_{rel}
-\frac{C_h(P_s^{k+1}-P_s^k)}{\Delta t}
\]

must remain within the configured numerical tolerance.

The pump is evaluated at the beginning-of-step network pressure and the UPW
balance is implicit in passive outflows. This is a first-order operator split;
its error must be bounded by timestep-convergence tests. No water-hammer,
distributed pipe inertia, NPSH, cavitation, or detailed valve coefficient is
claimed.

### Thermal state

Use pump inflow to flush the well-mixed supply node:

\[
C_T\dot T = \rho c_p Q_p(T_{in}-T)
+G_a(T_a-T)+\dot Q_{load}.
\]

This remains a lumped engineering approximation. It corrects the former use
of tool flow as the inlet energy flux.

### Water-quality proxy semantics

Remove the emitted physical-unit `conductivity_proxy_s_m` state. Replace it
with `water_quality_deviation_proxy`, a dimensionless synthetic index in
\([0,1]\): zero is the configured nominal proxy condition and larger values
indicate only a simulated deviation. It is not measured conductivity,
contamination, corrosion, a physical defect, or a yield state. The former
canonical signal remains deprecated for serialized compatibility but is not
emitted by the R3 plant. NIST reports theoretical pure-water conductivity near
25 °C as 0.055 µS/cm, which confirms that the old 0.055 S/m value was not a
defensible physical representation:

- https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication260-142.pdf

### UPS energy and output frequency

Add UPS output frequency \(f_{out}\), battery energy \(E_b\), and real load
\(P_L\). Output frequency follows a mode-dependent first-order target:

\[
\dot f_{out}=\frac{f_{target}(mode)-f_{out}}{\tau_f},
\]

where grid/recovery/bypass follow grid frequency and transfer/battery target
nominal frequency. Battery energy obeys

\[
E_b^{k+1}=E_b^k-\frac{P_L\Delta t}{\eta_{inv}}
\]

during transfer/battery operation and charges at a bounded configured rate in
grid/recovery. Depleted energy or declared overload replaces battery service
with bypass; it does not create energy. All capacities, load limits, transfer
targets, charge rates, and constant efficiency are synthetic engineering
parameters. Manufacturer specifications show that UPS battery efficiency and
runtime depend on load, supporting explicit load/capacity bookkeeping but not
these parameter values:

- https://www.productinfo.schneider-electric.com/easyups3m/viewer?docidentity=TechnicalDataFor208VSystems-DCE5E7D4&extension=xml&lang=en&manualidentity=TechnicalSpecificationsEasyUPS3M601-D5104BCE

No switching waveform, harmonics, reactive power, battery electrochemistry,
protection certification, or sub-cycle production response is represented.

## Reference synthetic operating point

At \(n=1\), \(P_s=300\,000\) Pa, and \(P_r=100\,000\) Pa:

- \(H_{shut}=400\,000\) Pa;
- \(H_{ref}=200\,000\) Pa;
- \(Q_{ref}=2.0\times10^{-4}\) m³/s;
- \(Q_t=1.0\times10^{-4}\) m³/s;
- \(Q_r=1.0\times10^{-4}\) m³/s;
- \(Q_{rel}=0\); and
- \(dP_s/dt=0\).

These values are selected to create a self-consistent simulation equilibrium,
not calibrated to a real fab or vendor pump.

## Interface and schema impact

- `DynamicSubsystem` method version remains 2.0.0; constructor/reset/step
  signatures do not change.
- Component state/config dataclasses change. Callers and tests that construct
  them must be updated together.
- Canonical schema moves additively to 2.1.0 for UPS energy/frequency,
  hydraulic diagnostics, and the dimensionless water-quality signal. The old
  conductivity signal is retained as deprecated, not reinterpreted.
- Interface registry moves to 2.1.0 to reference canonical schema 2.1.0 while
  retaining `DynamicSubsystem` 2.0.0.
- The complete default configuration, deterministic hash, data-schema Python
  catalog, unit tests, property tests, documentation, manifest, and status must
  be updated.

## Acceptance tests

1. The nominal pump/UPW point is an equilibrium and pump-curve residual is
   within tolerance.
2. Homologous flow/head/power follow \(n,n^2,n^3\) at homologous pressure.
3. Flow decreases as network differential pressure rises at fixed speed.
4. Pump trip pressure decays over multiple compliance-governed steps rather
   than collapsing or reporting stale flows.
5. Closed-valve and relief cases preserve the discrete mass balance.
6. Tool flow is monotone with valve position under fixed boundary conditions.
7. UPS frequency dynamics are exercised; battery energy decreases with load,
   never leaves bounds, and depletion/overload cannot remain in battery mode.
8. Thermal and dimensionless proxy states remain bounded and correctly named.
9. Nominal and disturbance traces converge under timestep refinement against
   a preregistered fine-step reference.
10. Full tests, YAML validation, and documentation-link validation pass.

## Claims boundary

Passing R3 validates implementation invariants and numerical behavior of a
synthetic lumped plant. It does not validate real equipment parameters,
physical water quality, fab plumbing, MRR coupling, equipment protection,
defects, yield, production control, or controller efficacy.
