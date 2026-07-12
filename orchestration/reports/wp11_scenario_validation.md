# T-WP11 deterministic scenario engine validation note

Date: 2026-07-11  
Historical status: original implementation tests passed; scientific validation
is provisional after the 2026-07-11 retrospective audit.

Audit notice: zero-duration ramps, target-specific bounds, interval overlap,
STEP/PULSE semantics, and initiating-versus-propagation causes require
correction. Preserve the replay results below as as-built evidence only; see
`phase_1_2_scientific_audit.md`, Gate R4.

## Scope

The scenario engine validates declarative exogenous events and replays them
deterministically. It provides no CMP physics, controller action, predictive
claim, or real-fab fault-frequency claim.

## Event contract

Each event records scenario ID, event ID, type, start time, duration, priority,
target, profile, magnitude, unit, initiating cause, and declaration order.
Events are active on \([t_0,t_0+D)\), with an exact-time convention for a
zero-duration event. Equal-time active events are sorted by priority,
declaration order, and event ID.

Profiles are STEP, PULSE, RAMP, and PIECEWISE_LINEAR. The RAMP value is:

\[
u(t)=m(t-t_0)/D.
\]

The compound scenario has explicit MULTI_LABEL_ORDERED cause policy. It
contains a grid-voltage sag followed by a tool-demand spike at equal start time
and returns those two initiating labels in declared deterministic order.

## Scenario library

The library file defines exactly fourteen required families:

- normal operation;
- mild voltage sag;
- severe voltage sag;
- UPS transfer;
- pump trip;
- valve restriction;
- tool-demand spike;
- temperature excursion;
- pressure-sensor bias;
- sensor dropout;
- recoverable disturbance;
- hold-required disturbance;
- compound disturbance;
- slow drift.

## Validation evidence

- Scenario unit/regression suite: 4 passed.
- Entire project suite: 60 passed in the devkki environment.
- Tests cover all required families, invalid target/unit/time/magnitude
  rejection, stable equal-time ordering, compound-cause policy, and exact
  deterministic replay.
- One existing pandas FutureWarning remains in PHM empty-frame concatenation;
  it does not concern scenario evaluation.

## Limitations

- Event timings and magnitudes are synthetic test definitions.
- Event profiles do not yet model stochastic fault arrival, repair processes,
  correlated faults, or operational scheduling.
- Initiating-cause labels are simulator truth reserved for offline evaluation;
  they must not be exposed to online predictors or controllers.
