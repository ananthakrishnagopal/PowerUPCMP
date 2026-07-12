# R3 plant-physics validation

Date: 2026-07-11  
Gate: T-PHASE12-REMEDIATION / R3  
Environment: conda `devkki`  
Decision basis: `orchestration/decisions/r3_plant_physics.md`

## Outcome

R3 is **VALIDATED for the synthetic PoC**. The pump, hydraulic, thermal,
water-quality-proxy, and UPS corrections satisfy the declared implementation,
conservation, limiting-case, and numerical-convergence acceptance tests.
Canonical schema 2.1.0 adds the required diagnostic signals while retaining
the deprecated physical-unit conductivity proxy only for serialized backward
compatibility. `DynamicSubsystem` remains version 2.0.0.

This gate validates a reduced synthetic plant and its numerical invariants. It
does not validate real-fab equipment, vendor parameters, utility-to-CMP
connection topology, MRR response, defects, yield, production control, or
controller efficacy.

## Implemented equations

The speed-scaled pump curve is

\[
H_p(Q,n,d)=dH_{shut}n^2-k_QQ^2,
\qquad
k_Q=\frac{H_{shut}-H_{ref}}{Q_{ref}^2}.
\]

At a supplied system differential pressure, the pump solves the non-negative
operating flow or closes its check valve. The nominal synthetic parameters are
\(H_{shut}=400\,000\) Pa, \(H_{ref}=200\,000\) Pa,
\(Q_{ref}=2.0\times10^{-4}\) m³/s, and \(\eta_p=0.70\). The resulting nominal
shaft-power approximation is 57.142857 W. These are engineering/synthetic
values, not manufacturer data.

The supply compliance uses the unique backward-Euler root of

\[
\frac{C_h(P_s^{k+1}-P_s^k)}{\Delta t}
=Q_p^k-Q_t(P_s^{k+1})-Q_r(P_s^{k+1})-Q_{rel}(P_s^{k+1}).
\]

No pressure clip is used. Tool, return, relief, and storage flows are logged at
one consistent time boundary, and the discrete mass residual is checked on
every step. The pump curve is evaluated at beginning-of-step pressure; the
resulting first-order operator split is controlled by a configured maximum
timestep and explicit refinement evidence.

The thermal state now uses pump inflow in the well-mixed supply-volume energy
balance:

\[
C_T\dot T=\rho c_p Q_p(T_{in}-T)+G_a(T_a-T)+\dot Q_{load}.
\]

The former `conductivity_proxy_s_m` state is not emitted. R3 emits only a
dimensionless `water_quality_deviation_proxy` in [0,1], with zero as nominal.
It is not a physical water-quality measurement.

UPS output frequency is a first-order mode-dependent state. Battery energy is
decreased by \(P_L\Delta t/\eta_{inv}\) during transfer/battery operation and
charged at a bounded rate in grid/recovery. Depletion or overload transitions
to bypass and cannot create energy. A forced interruption also sets grid
voltage to the configured minimum.

## Deterministic numerical evidence

The machine-readable report is `reports/plant/r3_validation.json`; the full
healthy-UPS trace is `reports/plant/r3_healthy_ups_reference_chain.csv`.

### Pump curve

- Quadratic coefficient: \(5.0\times10^{12}\)
  Pa·s²/m⁶.
- At homologous speed ratios 0.25, 0.5, 0.75, 1.0, and 1.2, the maximum
  absolute ratio error for \(Q\sim n\), \(H\sim n^2\), and
  \(P\sim n^3\) is \(4.45\times10^{-16}\).
- Maximum open-valve operating-point residual in the generated evidence:
  \(1.17\times10^{-10}\) Pa.
- At 1.0 speed ratio, flow decreases from
  \(2.8284\times10^{-4}\) m³/s at zero differential pressure to
  \(1.4142\times10^{-4}\) m³/s at 300 kPa; at 400.001 kPa the check valve is
  closed and reverse flow is zero.

### Hydraulic conservation and limiting cases

- Nominal supply/return pressures 300/100 kPa, tool/return flows each
  \(1.0\times10^{-4}\) m³/s, and pump inflow
  \(2.0\times10^{-4}\) m³/s form an equilibrium.
- A pump trip moves supply pressure from 300 kPa to 290.243902 kPa on the
  first 10 ms step and then monotonically to 100.167976 kPa after 1 s. It does
  not collapse to return pressure in one step.
- With the tool valve closed and 0.3 L/s-equivalent scaled inflow
  (\(3.0\times10^{-4}\) m³/s), the explicit relief case converges to
  539.9999997 kPa with return flow \(2.20\times10^{-4}\) m³/s and relief flow
  \(8.00\times10^{-5}\) m³/s.
- Maximum generated mass-balance residual is below
  \(1.0\times10^{-12}\) m³/s.

### Timestep refinement

For an instantaneous boundary-speed change to 0.70 pu over 0.5 s, the 0.5 ms
solution gives final supply pressure 196,187.120878 Pa:

| dt | Absolute error vs 0.5 ms | Error / 300 kPa |
|---:|---:|---:|
| 20 ms | 89.3311 Pa | 2.9777e-4 |
| 10 ms | 36.1927 Pa | 1.2064e-4 |
| 5 ms | 16.1570 Pa | 5.3857e-5 |
| 2.5 ms | 7.08584 Pa | 2.3619e-5 |
| 1 ms | 2.00356 Pa | 6.6785e-6 |

The error decreases monotonically with refinement. The default 10 ms step is
retained for the PoC and has 0.0121% nominal-pressure error in this test. This
is numerical-fidelity evidence, not a production-response claim.

### UPS energy and frequency

- A 2,500 W load over the 400 ms sag consumes 1,052.631579 J at constant
  configured inverter efficiency 0.95, exactly matching the discrete energy
  equation.
- A deliberately tiny 100 J battery reaches zero and enters BYPASS by 40 ms.
- A later WP10 exact-boundary regression exhausts a 500 J battery after
  nineteen equal discrete draws without crossing below zero; the following
  unsupported interval enters BYPASS. Only floating-point residue is projected
  to the configured minimum after the energy decision.
- A one-step grid-frequency change from 50 to 49 Hz produces 49.9 Hz UPS
  output at the configured 0.1 s time constant and 10 ms step.
- Overload and forced-interruption behavior have explicit tests.

### Healthy-UPS reference chain

The deterministic chain uses a 25% voltage sag lasting 400 ms after a 3 s
warmup. It applies no CMP connection and no MRR equation:

- baseline supply pressure: 299,997.674563 Pa;
- minimum UPS output voltage: 0.865536 pu;
- minimum motor speed: 187.165637 rad/s;
- minimum supply pressure: 298,879.164876 Pa;
- maximum absolute pressure deviation: 1,118.509687 Pa (0.373% nominal);
- baseline and minimum tool flow: \(1.0\times10^{-4}\) m³/s;
- maximum pump-curve residual: \(5.82\times10^{-11}\) Pa; and
- maximum hydraulic residual: \(9.98\times10^{-13}\) m³/s.

This supports the preregistered interpretation of the healthy-UPS sag as a
synthetic negative control. It must not be tuned into an MRR excursion. Positive
disturbances require separately declared degraded-UPS, direct hydraulic, or
compound scenarios.

## Tests

- R3-focused contract/unit/property/integration suite: 52/52 passed.
- Complete repository suite: 94/94 passed in 41.91 s with zero reported
  failures.
- Default runtime configuration validates strictly.
- Canonical runtime-configuration SHA-256:
  `6a47eefbefee0fa3084b3f4f2e780d0aa430bf3cad1f3dbb64a988398bbbaf97`.
- Frozen R3 checkpoint YAML (`configs/checkpoints/r3_default.yaml`) SHA-256:
  `ee7772654d670fdadcc7d8c44be5f17d0faaaab76ab6f16fe81460b78fe6abb9`.
- Validation JSON SHA-256:
  `02ba8166715c1022d54685d96ded8b85c196dbd0dbc6b29ea544dd4b085eddb7`.
- Reference trace SHA-256:
  `5191cbdcbf36c8709d92ed0de9662104c3ba6adfdd030ac45a661020ea17fdd0`.
- The R3 validation script was rerun after R4 using the frozen checkpoint; both
  JSON and CSV hashes remained identical.
- The script was rerun again after the WP10 battery-boundary and version-aware
  provenance corrections. The same frozen JSON and CSV hashes were restored
  exactly; no R3 physical trace changed.

## Residual limitations

- No manufacturer pump curve, efficiency map, BEP range, NPSH, cavitation,
  check-valve transient, distributed pipe inertia, or water hammer.
- The return boundary is exogenous and only the supply node has compliance.
- Pump/UPW coupling is a first-order operator split, not a simultaneous
  distributed hydraulic solve.
- Pump shaft losses at zero differential pressure and motor-load feedback to
  the UPS are not represented.
- UPS parameters are synthetic; there are no switching waveforms, harmonics,
  reactive power, battery electrochemistry, or protection claims.
- The dimensionless water-quality state has no measured chemistry mapping.
- R4 observation timing/scenario semantics, WP08 CMP physics, and WP10
  utility-to-CMP coupling are now separately validated. Prediction,
  attribution, safety, and control remain unimplemented.

## Gate disposition

R3 remains closed as VALIDATED. Its frozen schema/interface, configuration
hash, JSON hash, and trace hash remain historical compatibility gates for
later CMP/coupling/runtime work.
