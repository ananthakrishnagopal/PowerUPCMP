# T-WP05 VFD, motor, and pump validation note

Date: 2026-07-11  
Historical status: original implementation tests passed; scientific validation
is provisional after the 2026-07-11 retrospective audit.

Audit notice: the affinity equations below are homologous reference checks,
not a complete pump/network duty-point model. Flow and head must not be imposed
independently in the integrated plant; see `phase_1_2_scientific_audit.md`,
Gate R1/R3.

## Scope

This component models the bounded propagation from simulated UPS output to VFD availability, motor speed, and idealized pump flow/head/power. It is not a model of a certified VFD, motor, pump curve, electrical waveform, or production interlock.

## Governing equations and units

For VFD command \(u\in[0,1]\) and UPS voltage \(V_u\) (per unit), output availability is zero at or below the trip threshold. Otherwise:

\[
a_{vfd}=u\left[\operatorname{clip}\left(\frac{V_u-V_{trip}}{V_{derate}-V_{trip}},0,1\right)\right]^d.
\]

Motor speed uses an explicit first-order, ramp-limited update:

\[
\omega^{k+1}=\operatorname{clip}\left(\omega^k+\Delta t\,\operatorname{clip}\left(\frac{\omega_{target}-\omega^k}{\tau_m},-r_{down},r_{up}\right),0,1.2\omega_0\right).
\]

The idealized pump affinity relations are:

\[
Q=Q_0r,\qquad H=H_0r^2,\qquad P=P_0r^3,\qquad r=\omega/\omega_0.
\]

Here \(\omega\) is rad/s, \(Q\) is m³/s, \(H\) is Pa, and \(P\) is W. The explicit motor update rejects \(\Delta t>\tau_m\).

## Default bounded parameters

| Parameter | Value | Units | Provenance |
|---|---:|---|---|
| Nominal motor speed, \(\omega_0\) | 188.5 | rad/s | Synthetic assumption |
| Motor time constant, \(\tau_m\) | 0.20 | s | Engineering approximation |
| Ramp up / down | 500 / 1000 | rad/s² | Engineering approximation |
| VFD trip / derating start | 0.50 / 0.90 | pu | Synthetic assumption |
| Restart dwell | 0.25 | s | Engineering approximation |
| Reference pump flow | 2.0e-4 | m³/s | Synthetic assumption |
| Reference pump head | 3.0e5 | Pa | Synthetic assumption |
| Reference pump power | 2500 | W | Synthetic assumption |

## Deterministic reference trace

Using \(\Delta t=0.01\,s\):

| Condition | Expected result |
|---|---:|
| 1.0 pu command/UPS voltage after 1.4 s | 188.311324254 rad/s motor speed |
| 1.0 pu command at 0.70 pu UPS output | 0.500000000 pu VFD availability |
| Pump at 0.5 reference speed | \(Q=1.0e-4\) m³/s; \(H=75{,}000\) Pa; \(P=312.5\) W |

## Validation evidence

- Focused VFD/motor/pump tests: 9 passed.
- Entire project suite: 44 passed in `devkki`.
- Unit coverage: command bounds, voltage derating, trip/restart dwell, timestep rejection, reference and stopped pump cases.
- Property coverage: non-decreasing flow/head/power with speed; non-negative pump power; linear/quadratic/cubic reference affinity behavior.

The only full-suite warning is an existing pandas `FutureWarning` in PHM empty-frame concatenation; it does not concern this component.

## Limitations

- The affinity equations are local engineering approximations and omit efficiency maps, cavitation, NPSH, valve/system curves, and degradation.
- Parameters are neither PHM-calibrated nor literature-calibrated at this stage.
- This component supports downstream synthetic sensitivity analysis only; it does not prove electrical-to-UPW or UPW-to-MRR causality in a fab.
