# T-WP07 sensor and communication validation note

Date: 2026-07-11  
Historical status: original implementation tests passed; scientific validation
is provisional after the 2026-07-11 retrospective audit.

Audit notice: negative timestamp jitter can make arrival precede source-state
generation. The timing equations below describe the as-built defect and must
not govern online evaluation; see `phase_1_2_scientific_audit.md`, Gate R4.

## Scope

The sensor layer turns immutable simulated latent-state records into canonical
observation records. It supports noise, bias, drift, quantisation, sampling
rate mismatch, delay, packet loss, stuck sensors, and timestamp jitter. It
never changes latent simulator state.

## Observation and timing equations

\[
y(t)=\mathcal{Q}\left[x(t)+b+d\,t+\epsilon\right],
\qquad \epsilon\sim\mathcal{N}(0,\sigma^2).
\]

\[
t_{obs}=\max(0,t+\epsilon_j),\qquad
t_{arrival}=t_{obs}+\delta.
\]

Loss creates an observation with null value and both missing and dropped
quality flags. Stuck behavior retains a prior observed value and carries a
stuck flag. The observation record includes source-step index, observed time,
arrival time, sensor ID, signal ID, quality flags, uncertainty standard
deviation, and synthetic data origin.

## Deterministic reference

For 100,000 Pa at \(t=1\,s\), with 10 Pa bias, 2 Pa/s drift, and 1 Pa
quantisation, the observed pressure is 100,012 Pa. With 0.02 s delay, arrival
time is observation time plus 0.02 s, including when the observation timestamp
has deterministic seeded jitter.

At a 0.10 s sensor period, samples at 0.00 s and 0.10 s are emitted while a
0.05 s plant step creates no observation. The 0.10 s output retains source
step index 10 and observed timestamp 0.10 s.

## Validation evidence

- Focused sensor unit/property suite: 6 passed.
- Entire project suite: 56 passed in the devkki environment.
- Tests cover corruption flags, loss/missing records, stuck values,
  sampling-rate mismatch, delay, jitter, deterministic replay, and latent
  state non-mutation.
- One existing pandas FutureWarning remains in PHM empty-frame concatenation;
  it does not concern this component.

## Limitations

- Distributions and probabilities are synthetic and not calibrated to fab
  instrumentation or communications.
- The model does not simulate clock protocols, queues, network topology,
  cybersecurity, or correlated multi-sensor failures.
- Observation corruption is simulation evidence only and must not be described
  as measured sensor reliability.
