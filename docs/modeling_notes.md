# Phase 3 modeling notes and decision ledger

Status: living technical ledger; corrective gates R1--R4, standalone WP08 CMP physics, and WP10 declared-topology coupling are validated.  
Last updated: 2026-07-11

## Purpose

This document records what is being modelled, why each state exists, its units, provenance, invariants, validation evidence, and unresolved choices. It is updated alongside code and the running paper. A parameter or equation is not treated as literature-supported merely because it appears here.

## Retrospective scientific-audit disposition

The detailed audit in
[`phase_1_2_scientific_audit.md`](../orchestration/reports/phase_1_2_scientific_audit.md)
found that the previously passing component tests do not cover frozen-interface
conformance, PHM phase/timing semantics, pump/network duty-point consistency,
hydraulic conservation, observation-arrival causality, or executable scenario
edge cases. The component sections below therefore document **as-built
behavior**, not accepted integrated physics.

The former Phase 3 scalar Preston/direct-UPW-multiplier decision is withdrawn.
The only design candidate for future T-WP08/T-WP10 work is
[`phase_3_cmp_model_redesign.md`](../orchestration/reports/phase_3_cmp_model_redesign.md),
which remains proposed until user approval and controlled schema/interface
impact analysis. Where an older equation below conflicts with that report, the
report governs future design and the older equation is historical evidence
only.

Four remediation gates are mandatory before CMP implementation:

- R1: native/unknown public units, frozen subsystem contracts, and complete
  default configuration;
- R2: phase-aware time-weighted PHM features, label-anomaly policy, and
  official/wafer/time/machine splits;
- R3: pump-curve/system interaction, conserved relief/bypass flow,
  compliance-governed transients, and UPS/frequency consistency; and
- R4: causal source/reported/arrival timing plus target- and overlap-aware
  scenario validation.

### R1 validated contract baseline

R1 passed on 2026-07-11. Canonical schema 2.0.0 preserves a public source
value independently from optional SI conversion. An available PHM MRR value
with an undeclared source unit is stored with `UNIT_UNRESOLVED`, null canonical
fields, and no `MISSING` flag. Supported conversion requires a declared source
unit, the signal-catalog canonical unit, and an auditable conversion ID.

DynamicSubsystem 2.0.0 uses immutable configuration at construction plus
`reset(initial_state=None)` and `step(state, action, disturbance, dt_s)`.
Sensing is excluded from physical subsystems and remains exclusively in
`SensorModel.sample`, which owns source/arrival timing and corruption state.
Electrical, drive, pump, and UPW implementations conform to this base and
carry component provenance IDs.

The complete explicit baseline is `configs/default.yaml`. Its canonical hash
is
`4cc229eff2635bc64f8b84815317d6070ce3ba89b27f46af5c64b6fb56e4f3f8`,
and its run provenance map contains four plant plus three sensor IDs. R1 passed
21 focused tests and the 70-test full suite. These results validate contracts
and configuration only.

### R2 validated PHM semantic baseline

R2 passed on 2026-07-11. PHM rows remain in source order with an immutable
source-row index. A continuity segment ends at a trace boundary, a non-positive
timestamp increment, or a gap above 10 s. Centered time support within a
segment is

\[
w_i = \frac{1}{2}\Delta t_{i-1}^{+}
    + \frac{1}{2}\Delta t_{i+1}^{+},
\]

where invalid or cross-segment neighbours contribute zero. Consequently a
duplicate timestamp adds no artificial duration, and no feature weight bridges
a reversal or long gap.

Process modes are input-only operational proxies, never measured phases. The
active-polish candidate requires nonzero pressure, slurry, wafer-or-stage
rotation, and head rotation; transition, preparation, ending/cleaning, and
unresolved states remain separately summarized. All complete-trace summaries
are marked offline-only. Targets are joined after feature construction and
remain in separate files.

The official training/test/validation hierarchy is frozen as fit-and-tune,
offline holdout, and final public holdout. Inner splits hold out whole wafers
and chronological blocks; fitted transformations carry a fit-scope audit. A
physical-machine holdout is infeasible because only machine ID 2 exists.
`MACHINE_DATA` varies within nearly every wafer/stage group and is retained
only as descriptive metadata/input, not machine or regime identity.

The 1,981/424/424 processed rows each use 405 target-free predictor columns.
The original label treatment is primary; excluding the four preregistered
records and hypothetically dividing only those four by 60 are sensitivity
analyses. R2 passed 13 focused tests, 6 real-data integration tests, and the
82-test full suite with zero warnings. This validates preprocessing behavior,
not virtual-metrology accuracy or physical units.

## Causal chain under implementation

```text
scenario event → grid/UPS → VFD/motor → pump → UPW pressure/flow/temperature → CMP state/MRR
```

Online controllers will receive observations only. Latent simulator states and initiating-cause labels remain evaluation-only.

## Time and numerical convention

- Canonical time: integer `step_index`, with `timestamp_s = step_index * dt_s`.
- Candidate state updates are computed before commit; non-finite or invariant-invalid candidates must stop the run.
- Actions proposed at step k become effective no earlier than step k+1.
- Voltage, frequency, motor, thermal, and proxy first-order states use explicit Euler within configured bounds. R3 supply pressure uses a scalar backward-Euler mass balance with deterministic bisection; pump/UPW composition is a first-order operator split. All remain subject to timestep-convergence checks.
- Every stochastic process receives a named child seed; current plant equations are deterministic conditional on events and parameters.

## State taxonomy and units

| State group | Examples | Units | Origin |
|---|---|---|---|
| Electrical/UPS | grid voltage, UPS output voltage, frequency, UPS mode | pu, Hz, enum | simulated physical state |
| Drive/motor | VFD command/derating, motor speed, trip | pu, rad/s, boolean | simulated physical state |
| Pump | speed ratio, flow, head, power | 1, m³/s, Pa, W | simulated physical state |
| UPW | supply/return pressure, tool flow, valve, temperature | Pa, m³/s, 1, K | simulated physical state |
| CMP | contact pressure, relative velocity, slurry flow, MRR | Pa, m/s, m³/s, m/s | simulated physical state |
| Sensor output | any observed plant signal plus quality flags | source signal unit | observed sensor state |

## T-WP04 electrical and UPS model — R3 validated synthetic behavior

Grid voltage and frequency are bounded exogenous profiles. A forced
interruption sets grid voltage to the configured minimum. UPS voltage and
frequency follow mode-dependent first-order targets:

\[
\dot V_u=\frac{V_{target}(m,V_g)-V_u}{\tau_V},
\qquad
\dot f_u=\frac{f_{target}(m,f_g)-f_u}{\tau_f}.
\]

`GRID`, `RECOVERY`, and `BYPASS` frequency targets follow the grid;
`TRANSFER` and `BATTERY` target nominal frequency. The deterministic state
machine is

```text
GRID --fault--> TRANSFER --delay and energy available--> BATTERY
BATTERY --stable grid--> RECOVERY --dwell--> GRID
overload or energy unavailable --> BYPASS
```

Battery energy is explicit. During transfer or battery operation,

\[
E_b^{k+1}=E_b^k-\frac{P_L\Delta t}{\eta_{inv}}.
\]

During grid/recovery it charges by at most the configured charge power. Energy
is bounded between the declared minimum and capacity; a step that cannot be
fully supplied reaches the minimum and changes to BYPASS. The default
simulation values are 3.6 MJ capacity, 2.5 kW nominal load, 3.0 kW rating,
1.2 overload ratio, 0.95 constant inverter efficiency, and 500 W maximum
charge power. They are synthetic engineering parameters, not a vendor UPS.

R3 evidence: a 2.5 kW, 400 ms battery interval consumes 1,052.631579 J; a
deliberately tiny 100 J battery reaches BYPASS by 40 ms; and a one-step 50 to
49 Hz grid change gives 49.9 Hz output for \(\tau_f=0.1\) s and
\(\Delta t=0.01\) s. Voltage/frequency/energy/load remain finite and bounded.
No waveform, harmonic, reactive-power, battery-chemistry, certification, or
sub-cycle response claim is made.

All coefficients are `Synthetic assumption` or `Engineering approximation`.
No electrical parameter is data-calibrated.

## T-WP05 VFD/motor/pump — R3 validated synthetic behavior

VFD available output is a bounded function of the UPS output voltage and the
requested VFD command. With \(V_{trip}=0.50\,pu\), \(V_{derate}=0.90\,pu\), and
the default exponent \(d=1\), the implemented availability is:

\[
a_{vfd}=\begin{cases}
0, & V_u\leq V_{trip}\\
u\,\operatorname{clip}\!\left(\frac{V_u-V_{trip}}{V_{derate}-V_{trip}},0,1\right)^d,
& V_u>V_{trip},
\end{cases}
\]

where \(u\in[0,1]\) is the requested command and \(a_{vfd}\in[0,1]\) is the
available output. A low-voltage or forced trip sets availability to zero. A
restart request must be continuously valid above the trip threshold for the
configured restart dwell time before release.

Motor speed is a first-order state subject to command, available output, ramp, trip, and restart constraints:

\[
\frac{d\omega}{dt}=\operatorname{clip}\left(\frac{\omega_{target}-\omega}{\tau_m},-r_{down},r_{up}\right).
\]

The explicit-Euler update is accepted only for \(0<\Delta t\leq\tau_m\). Default
values are \(\omega_0=188.5\,rad\,s^{-1}\), \(\tau_m=0.20\,s\),
\(r_{up}=500\,rad\,s^{-2}\), \(r_{down}=1000\,rad\,s^{-2}\), and restart dwell
\(=0.25\,s\). These are bounded synthetic/engineering values, not measurements
from a specific VFD or pump train.

The R3 pump uses the speed-scaled quadratic curve

\[
H_p(Q,n,d)=dH_{shut}n^2-k_QQ^2,
\qquad
k_Q=\frac{H_{shut}-H_{ref}}{Q_{ref}^2},
\]

where \(n=\omega/\omega_{ref}\) and \(d\in[0,1]\) is a synthetic
head-degradation factor. At network differential pressure \(\Delta P\),

\[
Q_p=\sqrt{\frac{\max(dH_{shut}n^2-\Delta P,0)}{k_Q}}.
\]

If backpressure exceeds speed-scaled shutoff head, a check valve prevents
reverse flow. The constant-efficiency shaft-power approximation is

\[
P_{shaft}=Q_p\Delta P/\eta_p.
\]

At homologous pressure \(\Delta P=n^2H_{ref}\), the familiar checks
\(Q=nQ_{ref}\), \(H=n^2H_{ref}\), and \(P=n^3P_{ref}\) hold. They are not
independent constraints at arbitrary network state.

### T-WP05 deterministic reference and invariants

The default pump reference is \(Q_{ref}=2.0\times10^{-4}\) m³/s,
\(H_{ref}=200\) kPa, \(H_{shut}=400\) kPa, and \(\eta_p=0.70\), yielding
57.142857 W at the reference point. Homologous ratios through 1.2 pu have
maximum numerical ratio error \(4.45\times10^{-16}\). At fixed 1.0 pu speed,
flow decreases from \(2.8284\times10^{-4}\) m³/s at zero differential
pressure to \(1.4142\times10^{-4}\) m³/s at 300 kPa; the check valve closes
above 400 kPa. Open-point residuals are below \(1.2\times10^{-10}\) Pa in the
generated audit.

These values define a self-consistent synthetic operating range. The model has
no manufacturer curve, efficiency map, BEP, NPSH, cavitation, or zero-head
shaft-loss representation.

## T-WP06 UPW hydraulics/thermal/proxy — R3 validated synthetic behavior

The bounded outflow relations are

\[
Q_r=\frac{\max(P_s-P_r,0)}{R_r},\qquad
Q_t=\min\left(Q_{demand},v\frac{\max(P_s-P_r,0)}{R_t}\right),
\]

with explicit relief

\[
Q_{rel}=\frac{\max(P_s-P_{rel,set},0)}{R_{rel}}.
\]

R3 solves the backward-Euler storage balance

\[
\frac{C_h(P_s^{k+1}-P_s^k)}{\Delta t}
=Q_p^k-Q_t(P_s^{k+1})-Q_r(P_s^{k+1})-Q_{rel}(P_s^{k+1}).
\]

The scalar left-minus-right residual is strictly increasing because
\(C_h/\Delta t>0\); deterministic bisection gives the unique bracketed
solution. Pressure is never clipped. If configured relief cannot bracket a
solution, the step fails as out-of-envelope. The logged residual is

\[
r_m=Q_p-Q_t-Q_r-Q_{rel}
-C_h(P_s^{k+1}-P_s^k)/\Delta t.
\]

Temperature is a lumped energy state:

\[
C_T\dot T=\rho c_pQ_p(T_{in}-T)+G_a(T_a-T)+\dot Q_{load}.
\]

Thus pump inflow, not tool outflow, flushes the well-mixed supply node. The
explicit thermal update rejects a step outside the configured 273.15--373.15 K
envelope.

The only emitted water-quality state is a dimensionless synthetic deviation
proxy \(x_q\in[0,1]\):

\[
\dot x_q=\frac{x_{source}-x_q}{\tau_q}+i_q.
\]

Zero is the nominal proxy condition. The prior S/m `conductivity_proxy` remains
deprecated in the canonical catalog for backward compatibility but is not
emitted. The new state is not measured conductivity, contamination, chemistry,
corrosion, particle, defect, or yield evidence.

### T-WP06 default reference and invariants

At the 300/100 kPa nominal point, tool and return flows are each
\(1.0\times10^{-4}\) m³/s, exactly balancing the pump's
\(2.0\times10^{-4}\) m³/s. A pump trip gives 290.243902 kPa after the first
10 ms step and monotonically approaches 100.167976 kPa after 1 s. A 0.3 L/s
closed-tool inflow activates relief and converges to 540 kPa with 0.22 L/s
return plus 0.08 L/s relief. Generated mass residuals remain below
\(1.0\times10^{-12}\) m³/s.

For a 0.70 pu speed boundary over 0.5 s, final-pressure error decreases from
89.33 Pa at 20 ms to 36.19 Pa at 10 ms, 16.16 Pa at 5 ms, 7.09 Pa at 2.5 ms,
and 2.00 Pa at 1 ms against a 0.5 ms reference. The default 10 ms error is
0.0121% of nominal pressure. This supports numerical use at PoC resolution,
not a real-time or water-hammer claim.

## T-WP07 sensor and communication model — R4 validated synthetic behavior

For a numeric latent signal \(x(t)\), the observed value before optional
clipping is:

\[
y(t)=\mathcal{Q}\left[x(t)+b+d\,t+\epsilon\right],
\qquad \epsilon\sim\mathcal{N}(0,\sigma^2),
\]

where \(b\) is static bias, \(d\) is linear drift (signal unit/s), and
\(\mathcal{Q}\) is optional quantisation. Configured lower and upper bounds
clip invalid synthetic observations and record an out-of-range flag.

R4 separates physical source generation, the reported sensor clock, and
communication arrival:

\[
t_{source}=t_k,\qquad
t_{reported}=\max(0,t_{source}+\epsilon_j),\qquad
t_{arrival}=t_{source}+\delta,quad\delta\ge0.
\]

The compatibility field `observed_timestamp_s` stores \(t_{reported}\), while
R4 records also carry `source_timestamp_s`. Reported clock jitter never changes
generation or delivery. The canonical record rejects
\(t_{arrival}<t_{source}\).

Generated records enter a private queue. A decision cutoff \(t_d\) sees only

\[
\mathcal O(t_d)=\{o:t_{arrival}(o)\le t_d\}.
\]

`sample` generates due observations and releases only those already arrived at
the current source boundary. `release_arrived` advances a monotone decision
cutoff without requiring a new latent state. Release removes the record and is
ordered by arrival, source step, sensor ID, and sample index. Thus a timestamped
future arrival cannot be returned early.

Packet loss produces a canonical missing observation with dropped and missing
flags; it does not silently reuse or impute a value. A stuck sensor records and
reuses its prior observed value, with a stuck flag. Sampling only occurs at
scheduled multiples of the configured sample period, so sampling-rate mismatch
is represented by absent observation records rather than altered latent
timestamps.

Every source batch must match the sensor model's run ID, source step, and source
timestamp, and calls must be strictly monotone. The model uses a seeded
pseudorandom generator and deterministic sensor-ID ordering. Given seed,
configuration, and latent history, both generation and delivery are identical.
Latent records remain immutable.

### T-WP07 reference and limitations

With 100,000 Pa latent pressure at \(t=1\) s, 10 Pa bias, 2 Pa/s drift, and
1 Pa quantisation, the corrupted value remains 100,012 Pa. It is generated at
1.0 s and, with 20 ms delay, is invisible until arrival at 1.02 s regardless
of reported timestamp jitter.

The R4 audit generated and released 101/101 unique samples. Forty-nine reported
timestamps were earlier than source and 51 later, yet all arrivals were 25 ms
after source, no record was released early, ten packet losses remained explicit
missing records, and two fixed-seed traces were exactly equal. This is an
in-process causal clock/queue abstraction, not a physical synchronization
system, broker, network, historian, or production latency claim.

## T-WP11 declarative scenario engine — R4 validated synthetic behavior

A scenario is an immutable schema version, identifier, description, seed,
compound-cause policy, and ordered event list. Unknown keys are rejected.
Each target has a declared unit, finite PoC range, binary rule where needed,
and zero-origin-ramp permission. No generic numeric fallback exists.

Profile semantics are:

- STEP: persistent for \(t\ge t_0\) and requires \(D=0\);
- PULSE: constant on \([t_0,t_0+D)\) and requires \(D>0\);
- RAMP: zero-origin linear evolution on \([t_0,t_0+D)\), allowed only for
  compatible targets and requiring \(D>0\); and
- PIECEWISE_LINEAR: positive duration with points exactly spanning 0 to \(D\),
  strictly increasing point times, bounded values, and final value equal to
  the declared magnitude.

For RAMP,

\[
u(t)=m\frac{t-t_0}{D},\qquad t\in[t_0,t_0+D),
\]

where \(m\) is the endpoint magnitude. Dynamic zero-duration profiles are
rejected before replay. Active events are sorted by ascending priority, then
declaration order, then event ID.

Two finite half-open intervals overlap when

\[
\max(t_{0,i},t_{0,j})<\min(t_{end,i},t_{end,j});
\]

a STEP has infinite end time. Same-target overlaps are forbidden because an
implicit last-write rule would be ambiguous. Overlapping distinct initiating
causes require `MULTI_LABEL_ORDERED`, even if start times differ.

The schema-2.0 library contains fourteen required scenario families: normal operation;
mild and severe voltage sag; UPS transfer; pump trip; valve restriction; tool
demand spike; temperature excursion; pressure-sensor bias; sensor dropout;
recoverable disturbance; hold-required disturbance; compound disturbance; and
slow drift. It has 13 PULSE events, one RAMP, and no persistent STEP. The only
overlap is the declared ordered sag plus demand compound event; it uses
different targets and two ordered causes.

Initiating disturbance labels are target-compatible. A short grid interruption
is `GRID_INTERRUPTION`; a later UPS TRANSFER is a propagation state.
`UPS_TRANSFER` and `VFD_DERATING` remain in the attribution vocabulary but are
forbidden as declarative initiating causes. Voltage sign must match sag versus
swell. The fixed audit replay SHA-256 is
`ef7c6393a77283d6542e64c493a53da25c6019bfc1ef549781ca080b7f17f518`.

All scenario ranges and causes are simulated definitions. A scenario event does
not itself establish a CMP defect, yield outcome, real fault frequency, or
real-fab causal mechanism.

## T-WP08 reduced-order CMP physics — validated synthetic behavior

The frozen and implemented simulator distinguishes process mode, local contact exposure,
dynamic consumables, slurry availability, interface temperature, cumulative
removal, and a typed neutral utility boundary. For platen and wafer angular speeds
\(\omega_p,\omega_w\), center offset \(r_{cc}\), and wafer coordinates
\((r,\theta)\):

\[
v_R(r,\theta)=\sqrt{\omega_p^2r_{cc}^2
+(\omega_p-\omega_w)^2r^2
+2\omega_p(\omega_p-\omega_w)r_{cc}r\cos\theta}.
\]

The dimensionless contact exposure is

\[
\Phi_{PV}=A^{-1}\int_A
(p/P_0)^\alpha(v_R/V_0)^\beta\,dA.
\]

Only POLISH mode accumulates removal. The normalized generalized
Preston form and cumulative states are

\[
R_{eq}=\chi_pR_{0,s}\Phi_{PV}m_sm_Tm_{pad}m_{recipe},
\qquad \dot H=R_{true},\qquad \dot t_p=\chi_p.
\]

The velocity scale is the nominal power mean

\[
V_0=\langle v_{R,0}^{\beta}\rangle_A^{1/\beta},
\]

so nominal pressure/speeds yield \(\Phi_{PV}=1\) for any frozen positive
\(\alpha,\beta\). Platen and head angular speeds are signed, slew-limited
first-order states; later supervisory speed actions are therefore not
instantaneous. Dressing restores reversible pad-surface activity but cannot
restore irreversible remaining pad life or dresser effectiveness. UPW
temperature is never equated to interface temperature inside WP08.

The future utility coupler outputs typed boundary conditions under one declared
topology: dressing-water support, thermal loop, explicitly synthetic
slurry-delivery support, or no CMP connection. The no-connection structure and
zero link strength are mandatory uncertainty cases. The SI simulator and PHM
native-unit virtual-metrology plane may share feature structure but not
coefficients without a documented calibration bridge.

The frozen reference uses 30 kPa, 8/6 rad/s platen/head speeds, a 0.20 m
center offset, and \(R_0=1.6666666666667\times10^{-9}\) m/s (100 nm/min).
The 16x64 quadrature gives \(V_0=1.6070416183328249\) m/s and classical
\(K_P=3.4570078908840606\times10^{-14}\) Pa⁻¹. Nominal exposure is one to
floating-point tolerance; zero pressure or zero speed gives exactly zero.

The 7 s reference trace contains 1 s PREPARE, 5 s POLISH, and 1 s HOLD.
Only POLISH accumulates the final 8.276153498157771 nm removal and 5 s active
time. HOLD MRR is exactly zero without changing cumulative removal or active
time. A 10 s dressing check increases activity from 0.5 to
0.5823912561285373 while remaining pad life decreases from 0.8 to
0.7994999999999968 and dresser effectiveness decreases from 0.9 to
0.8998200179088174.

The maximum absolute interface energy residual is
\(1.4188941577231162\times10^{-8}\) W. With the conservative default
\(\beta_T=0\), different coolant temperatures change interface temperature
but produce exactly zero MRR difference. Pressure, thermal, and cumulative
errors decrease monotonically from 40 to 2.5 ms against the 1 ms reference;
the default 10 ms cumulative-removal error is
\(4.400536911722043\times10^{-12}\) m.

The nominal annular exposure coefficient of variation is 0.0025316618572622336,
but it is only a **simulated spatial-uniformity proxy; not experimentally
validated WIWNU**. The trace SHA-256 is
`902fa4283ef8cf2150efef14aa08ca6f478aad55503e6d9b111584c33175626e`.
Focused impacted tests pass 48/48 and the full suite passes 130/130. Detailed
equations and results are in `docs/mathematical_model.md` and
`orchestration/reports/wp08_cmp_validation.md`.

## T-WP10 utility-to-CMP coupling — task-local validation complete

The locally supplied ten-paper review supports water-conditioned pad state,
slurry/rinse interaction, and thermal dynamics as possible CMP pathways. It
does not support numerical facility-header thresholds or PHM-tool plumbing.
The repository therefore defaults to `NO_CONNECTION`; connected structures
are declared synthetic experiments.

For supply pressure (P_s), tool flow (Q_t), and their references,

\[
p=P_s/P_{ref},\qquad q=Q_t/Q_{ref}.
\]

With the bounded ramp (R(x;x_0,x_1)), the coupler uses

\[
a_h=\min\{R(p;p_0,p_1),R(q;q_0,q_1)\},
\qquad a_{eff}=1-\lambda(1-a_h).
\]

The minimum is a bottleneck engineering approximation and avoids multiplying
correlated pressure/flow deficits. Every numerical coefficient is classified
as a synthetic assumption. No coefficient is data-calibrated or
literature-supported.

Four structural cases are executable:

- `NO_CONNECTION`, exact neutral and the runtime default;
- `DRESSING_WATER_SUPPORT`, which changes only DRESS activity;
- `THERMAL_LOOP`, which maps UPW temperature deviation and hydraulic support
  to coolant temperature/conductance;
- `SYNTHETIC_SLURRY_SUPPORT`, an explicitly artificial common-utility case.

The thermal map is

\[
T_c=T_{c,0}+\lambda(T_u-T_{u,ref}),
\]

not (T_c=T_u). This distinction was added after the first freeze review
identified that conflating the CMP neutral reference with an uncertain UPW
reference would violate the zero-link null.

The primary full-chain experiment warms the upstream plant for 3 s, applies a
synthetic degraded-UPS interruption from 1 to 4 s during a 6 s DRESS window,
uses 1 s PREPARE, then begins POLISH at 7 s. Grid interruption, UPS output,
pump flow, motor speed, pressure support, and coupling response first change
at 1.00, 1.03, 1.04, 1.19, 1.24, and 1.24 s respectively. Connected DRESS
availability reaches zero. Pad activity at the DRESS boundary is 0.5216572820
versus 0.5511876609 under no connection. Subsequent mean MRR is
9.8727270376e-10 versus 1.0198314108e-9 m/s. MRR remains zero throughout
DRESS; the later difference is carried only by stored pad state.

The healthy-UPS 25%/400 ms sag retains exact full support and identical CMP
traces. The global parameter analysis uses 4096 base samples and 36,864
seeded Saltelli pick-freeze evaluations. Link strength has the largest
total-order estimate (0.6127), followed by reference pressure (0.2603) and
reference flow (0.1705) for the selected representative state and ranges.
These ranks are conditional synthetic-model sensitivity, not empirical
importance or causal proof.

An exact UPS depletion case exposed a floating-point boundary residue. The
electrical model now projects an accepted energy subtraction to the configured
minimum; the following unsupported step enters BYPASS. The upstream R3 report
was regenerated, and 35/35 adjacent plant tests, 50/50 WP10-impacted tests,
and the final 154/154 complete suite pass.

Machine-readable evidence is
`reports/sensitivity/wp10_coupling_validation.json`; detailed scientific and
claim limits are in
`orchestration/reports/wp10_coupling_validation.md`.

## Coupling ledger

| Coupling | Proposed direction | Current provenance | Validation required |
|---|---|---|---|
| grid voltage → UPS output | lower grid voltage lowers/changes output after transfer dynamics | Engineering approximation | limiting cases, timing, sensitivity |
| UPS output → VFD availability | undervoltage reduces available drive output | Synthetic assumption | bounded monotonicity and mismatch study |
| motor speed → speed-scaled pump curve | homologous affinity scaling | Engineering approximation | operating-point residual, hydraulic power, degradation sensitivity |
| pump curve + network → UPW pressure/flow | conserved hydraulic balance with explicit relief | Engineering approximation | balance residual, pump-trip decay, equilibrium, timestep convergence |
| UPW → CMP boundary state | declared dressing, thermal, synthetic slurry, or no-connection topology | Pathway existence partly literature-supported; functions engineering approximations; every numerical coefficient synthetic | Task-local structural-null, zero-link, local/global/mismatch sensitivity, deterministic chain, and claim-boundary checks pass; real plumbing remains unknown |

Every WP10 coefficient now carries one of the required provenance classes plus
nominal value, units, bounds, sign, uncertainty, and sensitivity evidence.

## Decisions still required before predictive control

1. Safe MRR/utility envelope, persistence rule, and warning horizon.
2. Uncertainty representation, calibration data, and coverage target.
3. Compound-event attribution policy and `UNKNOWN` handling.
4. Predictive action set, horizon, cost function, hold/recovery penalties, and latency budget.
5. Independent safety limits, slew rates, invalid-sensor behavior, high-uncertainty behavior, and restart dwell.

## Evidence protocol

For each model component, record:

- equation and symbol definitions;
- canonical units and conversion boundaries;
- parameter table with provenance and bounds;
- limiting-case and invariant tests;
- timestep/stability evidence;
- sensitivity and mismatch results;
- exact configuration and seed;
- measured versus simulated/proxy classification;
- known limitations and claims affected.
