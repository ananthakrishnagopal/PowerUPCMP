# T-WP06 UPW hydraulic, thermal, and proxy-quality validation note

Date: 2026-07-11  
Historical status: original implementation tests passed; scientific validation
is provisional after the 2026-07-11 retrospective audit.

Audit notice: reviewed closed-valve and pump-trip limits exposed mass-balance
and transient-time inconsistencies, while the conductivity proxy is
dimensionally confusable with physical UPW conductivity. Preserve the results
below as as-built evidence only; see `phase_1_2_scientific_audit.md`, Gate R3.

## Scope

The component supplies a bounded, lumped state between idealized pump output
and later CMP coupling. It tracks supply/return pressure, tool/return flow,
valve position, temperature, and a numerical conductivity proxy. It is not a
plant hydraulic-network model or a water-quality certification model.

## Governing relations

\[
C_h\frac{dP_s}{dt}=Q_p-Q_t-Q_r,\qquad
Q_r=\max\left(0,\frac{P_s-P_r}{R_r}\right),
\]

\[
Q_t=\min\left(Q_{demand},\frac{v\max(0,P_s-P_r)}{R_t}\right).
\]

The pressure update uses explicit Euler and rejects
\(\Delta t>C_h\min(R_r,R_t)\). Supply pressure is bounded below by return
pressure and above by the lesser of the configured maximum and
\(P_r+H_p\), the current idealized pump-head ceiling.

\[
C_T\frac{dT}{dt}=(\rho c_pQ_t+G_a)(T_{in}-T)+W_{thermal}.
\]

\[
\frac{dc_{proxy}}{dt}=\frac{c_{source}-c_{proxy}}{\tau_c}+i_{proxy}.
\]

The conductivity term is explicitly a simulated proxy; it does not represent
measured UPW chemistry, contamination, a physical defect, or yield.

## Default parameters

| Parameter | Value | Units | Provenance |
|---|---:|---|---|
| Supply / return pressure | 300,000 / 100,000 | Pa | Synthetic assumption |
| Hydraulic compliance | 2.0e-10 | m³/Pa | Engineering approximation |
| Return / tool resistance | 2.0e9 / 1.0e9 | Pa s/m³ | Engineering approximation |
| Reference pump flow / head | 2.0e-4 / 3.0e5 | m³/s / Pa | Synthetic assumption |
| Thermal capacity | 5000 | J/K | Engineering approximation |
| Water density / specific heat | 997 / 4180 | kg/m³ / J/(kg K) | Engineering approximation |
| Ambient thermal conductance | 50 | W/K | Synthetic assumption |
| Nominal conductivity proxy | 0.055 | S/m | Synthetic assumption |
| Proxy time constant | 60 | s | Synthetic assumption |

## Deterministic reference trace

Using \(\Delta t=0.01\,s\):

| Condition | Result |
|---|---:|
| Nominal state | \(P_s=300{,}000\) Pa; \(Q_t=Q_r=1.0e-4\) m³/s |
| Valve 0.25, demand 2.0e-4 m³/s | \(Q_t=5.0e-5\) m³/s; next \(P_s=302{,}500\) Pa |
| 300 K inlet, 500 W heat, proxy source 0.10 S/m, 0.001 S/(m s) ingress | next \(T=293.157394420\) K; \(c_{proxy}=0.055017500\) S/m |

## Validation evidence

- Focused UPW unit/property suite: 6 passed.
- Entire project suite: 50 passed in the devkki environment.
- Tests cover nominal equilibrium, valve restriction, demand response,
  thermal/proxy response, timestep rejection, bounded states, and valve-flow
  monotonicity.
- One existing pandas FutureWarning remains in PHM empty-frame concatenation;
  it does not concern this component.

## Limitations

- The model omits pipe networks, transport delay, pump efficiency curves,
  NPSH/cavitation, compressibility detail, water chemistry, and contaminants.
- All parameters are engineering approximations or synthetic assumptions; none
  are PHM-calibrated.
- The component supports later synthetic utility-to-CMP sensitivity studies
  only and does not prove fab causality.
