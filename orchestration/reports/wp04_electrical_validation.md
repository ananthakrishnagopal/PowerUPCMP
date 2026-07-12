# T-WP04 electrical/UPS validation note

Date: 2026-07-11  
Historical status: original implementation tests passed; scientific validation
is provisional after the 2026-07-11 retrospective audit.

Audit notice: the as-built component does not implement its configured
frequency dynamics or the assumed UPS energy/load limit and does not conform
to the frozen DynamicSubsystem API. Preserve the results below as
implementation evidence only; see `phase_1_2_scientific_audit.md`, Gate R1/R3.

## Modelled states

- Grid voltage, per unit.
- Grid frequency, Hz.
- UPS output voltage, per unit.
- UPS mode: `GRID`, `TRANSFER`, `BATTERY`, `BYPASS`, or `RECOVERY`.
- Transfer and recovery timers, seconds.

## Governing relation

For each mode-dependent UPS voltage target \(V_{u,target}\), the output is a first-order state:

\[
V_u^{k+1}=V_u^k + \frac{\Delta t}{\tau_{ups}}\left(V_{u,target}-V_u^k\right).
\]

The explicit-Euler model requires \(0 < \Delta t \leq \tau_{ups}\). The implementation rejects larger timesteps rather than silently using an unstable update.

## Default synthetic parameters

| Parameter | Value | Units | Provenance |
|---|---:|---|---|
| Nominal voltage | 1.0 | pu | Synthetic assumption |
| Transfer threshold | 0.85 | pu | Engineering approximation |
| Recovery threshold | 0.95 | pu | Engineering approximation |
| Transfer delay | 0.05 | s | Engineering approximation |
| Recovery dwell | 0.25 | s | Engineering approximation |
| UPS output time constant | 0.05 | s | Engineering approximation |
| Transfer target | 0.80 | pu | Synthetic assumption |
| Battery target | 1.00 | pu | Synthetic assumption |

## Deterministic reference trace

Using \(\Delta t=0.01\,s\):

| Condition | UPS mode | UPS output |
|---|---|---:|
| Normal operation after settling | GRID | 1.000000 pu |
| First 0.70 pu sag step | TRANSFER | 0.960000 pu |
| After transfer delay | BATTERY | 0.913943 pu |
| Battery after 200 ms additional settling | BATTERY | 0.999008 pu |
| Grid recovery and dwell complete | GRID | 0.999999 pu |

The intermediate 0.913943 pu value is expected: entering `BATTERY` changes the target but does not instantaneously set output to 1.0 pu.

## Test evidence

- 35/35 project tests passed in `devkki`.
- Unit tests cover normal operation, sag/transfer/battery, recovery dwell, frequency clipping, invalid timestep/mode rejection, and threshold validation.
- Property tests cover bounded voltage/frequency states over configured disturbances and exact deterministic replay.

## Limitations

- No switching waveform, harmonic, battery energy, hardware protection, or real production response is modelled.
- Parameters are not data-calibrated.
- The component cannot establish real-fab electrical causality; it only provides a bounded simulated disturbance state for downstream sensitivity studies.
