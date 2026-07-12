# Decision record: Phase 3 CMP physics and utility coupling

Date: 2026-07-11  
Status: WITHDRAWN_AFTER_SCIENTIFIC_AUDIT  
Scope: historical record for T-WP08 and T-WP10; MUST NOT be implemented

## Withdrawal notice

This decision was withdrawn on 2026-07-11 after the Phase 1/2 scientific
audit. The scalar kinematics, linear consumable-age treatment, independently
imposed pump flow/head, and direct generic UPW-to-MRR multiplier are not a
defensible basis for the control experiment. The detailed findings are in
[`phase_1_2_scientific_audit.md`](../reports/phase_1_2_scientific_audit.md).
The proposed replacement design is
[`phase_3_cmp_model_redesign.md`](../reports/phase_3_cmp_model_redesign.md).

The replacement remains proposed rather than frozen. Controlled remediation
of the Phase 1/2 contracts and components, explicit impact analysis, updated
tests, and user approval of the replacement architecture are required before
T-WP08 or T-WP10 can resume. The text below is retained solely to preserve the
decision history.

## Decision

The simulator will use a bounded Preston-type average-MRR baseline:

\[
MRR_{\mathrm{physics}} =
K P_c V_{\mathrm{rel}}
m_{\mathrm{slurry}}
m_{\mathrm{pad}}
m_{\mathrm{dresser}}
m_{\mathrm{UPW}}.
\]

In implementation, the modifier terms are multiplied, not added:

\[
MRR_{\mathrm{physics}} =
K P_c V_{\mathrm{rel}}
\left(
m_{\mathrm{slurry}}m_{\mathrm{pad}}m_{\mathrm{dresser}}m_{\mathrm{UPW}}
\right).
\]

Equivalently, the implemented equation is:

\[
MRR_{\mathrm{physics}} =
K P_c V_{\mathrm{rel}}
m_{\mathrm{slurry}}m_{\mathrm{pad}}m_{\mathrm{dresser}}m_{\mathrm{UPW}}.
\]

The ordinary multiplication interpretation is formalized in
docs/mathematical_model.md and in the implementation tests. This decision
record does not authorize a physical-defect, yield, equipment, or production
claim.

## Evidence basis and boundary

The original Preston glass-polishing paper is bibliographically recorded as
F. W. Preston, The Theory and Design of Plate Glass Polishing Machines,
Journal of Glass Technology 11(44), 214 onwards, 1927. The later CMP
experimental study by Tseng and Wang, Re-examination of pressure and speed
dependences of removal rate during chemical-mechanical polishing processes,
Journal of the Electrochemical Society 144(2), 1997,
doi:10.1149/1.1837417, demonstrates that a Preston form is a useful baseline
but not a universal CMP law.

Accordingly, only the baseline form is literature-supported. The reference
operating point, all modifier gains, age effects, UPW effect, limits, and
uncertainty ranges below are explicitly synthetic assumptions or engineering
approximations. No PHM field is interpreted as a paired electrical or UPW
measurement, and PHM results cannot validate this coupling.

## Frozen CMP formulation

The implemented MRR is in m/s:

\[
MRR = K P_c V_{\mathrm{rel}} M,
\qquad
M=m_s m_{pad} m_{dresser} m_{UPW}.
\]

The coefficient unit is Pa^-1 because

\[
[K]=\frac{\mathrm{m/s}}{\mathrm{Pa}\,\mathrm{m/s}}=\mathrm{Pa}^{-1}.
\]

The synthetic nominal operating point is:

| Quantity | Value | Unit | Provenance |
|---|---:|---|---|
| Contact pressure, P0 | 20,000 | Pa | Engineering approximation |
| Relative velocity, V0 | 1.0 | m/s | Engineering approximation |
| Nominal average MRR | 1.0e-7 | m/s | Synthetic assumption |
| Preston coefficient, K | 5.0e-12 | Pa^-1 | Derived synthetic assumption |
| Nominal slurry flow | 5.0e-5 | m^3/s | Synthetic assumption |
| Pad service life | 28,800 | s | Synthetic assumption |
| Dresser service life | 14,400 | s | Synthetic assumption |

The coefficient is derived, rather than fitted:

\[
K=\frac{1.0\mathbin{\times}10^{-7}}{20{,}000\mathbin{\times}1.0}
=5.0\mathbin{\times}10^{-12}\ \mathrm{Pa}^{-1}.
\]

The head and platen speeds enter only through kinematics:

\[
V_{\mathrm{rel}}=r_{\mathrm{eff}}
\left(\omega_{\mathrm{head}}+\omega_{\mathrm{platen}}\right).
\]

The effective spatial-average radius is 6.496 mrad. Nominal head and platen
speeds are 60 and 90 rad/s, yielding 1.0 m/s. There is intentionally no
additional head-speed or platen-speed multiplier: adding one after this
kinematic calculation would count speed twice.

The bounded slurry multiplier is:

\[
d_s=\mathrm{clip}\left(\frac{Q_s}{Q_{s0}}-1,-0.5,0.5\right),
\qquad
m_s=\mathrm{clip}(1+0.20d_s,0.90,1.10).
\]

The age multipliers are:

\[
m_{\mathrm{pad}}=1-0.15\,\mathrm{clip}(a_{\mathrm{pad}}/a_{\mathrm{pad,max}},0,1),
\]

\[
m_{\mathrm{dresser}}=1-0.10\,\mathrm{clip}(a_{\mathrm{dresser}}/a_{\mathrm{dresser,max}},0,1).
\]

They model monotone synthetic degradation only. Pad conditioning, chemistry,
wafer pattern, and tool-specific wear mechanisms are out of scope.

## Frozen utility-to-CMP formulation

Electrical and drive variables have no direct MRR coefficient. The causal
implementation path is:

\[
V_{\mathrm{grid}}\rightarrow V_{\mathrm{UPS}}\rightarrow
\omega_{\mathrm{motor}}\rightarrow(Q_{\mathrm{pump}},H_{\mathrm{pump}})
\rightarrow(P_{\mathrm{UPW}},Q_{\mathrm{UPW}},T_{\mathrm{UPW}})
\rightarrow m_{\mathrm{UPW}}\rightarrow MRR.
\]

The coupling object records every upstream state for traceability, but computes
the MRR modifier only from the realized UPW state. This prevents an artificial
direct voltage-to-MRR shortcut.

\[
d_Q=\mathrm{clip}(Q_{\mathrm{UPW}}/Q_0-1,-0.5,0.5),
\qquad
m_Q=\mathrm{clip}(1+0.25d_Q,0.875,1.125),
\]

\[
d_P=\mathrm{clip}(P_{\mathrm{UPW}}/P_0-1,-0.5,0.5),
\qquad
m_P=\mathrm{clip}(1+0.20d_P,0.90,1.10),
\]

\[
d_T=\mathrm{clip}(T_{\mathrm{UPW}}-T_0,-10,10)\ \mathrm{K},
\qquad
m_T=\mathrm{clip}(\exp(0.01d_T),0.90,1.10),
\]

\[
m_{\mathrm{UPW}}=\mathrm{clip}(m_Qm_Pm_T,0.70,1.30).
\]

The defaults are Q0=1.0e-4 m^3/s, P0=300,000 Pa, and T0=293.15 K. The
positive signs are synthetic scenario definitions, not measured fab
calibration or claims about a particular chemistry.

## Coupling parameter registry

| ID | Nominal | Unit | Bounds | Direction | Provenance | Uncertainty / mismatch |
|---|---:|---|---|---|---|---|
| C-UPW-FLOW-GAIN | 0.25 | 1 | 0.125 to 0.375 | non-decreasing MRR with realized UPW flow | Synthetic assumption | half and 1.5 times nominal |
| C-UPW-PRESSURE-GAIN | 0.20 | 1 | 0.10 to 0.30 | non-decreasing MRR with realized UPW pressure | Synthetic assumption | half and 1.5 times nominal |
| C-UPW-TEMPERATURE-GAIN | 0.01 | K^-1 | 0.005 to 0.015 | non-decreasing MRR with UPW temperature | Synthetic assumption | half and 1.5 times nominal |
| C-UPW-FLOW-DEVIATION-LIMIT | 0.50 | 1 | fixed 0.50 | symmetric saturation | Synthetic assumption | fixed model-domain limit |
| C-UPW-PRESSURE-DEVIATION-LIMIT | 0.50 | 1 | fixed 0.50 | symmetric saturation | Synthetic assumption | fixed model-domain limit |
| C-UPW-TEMPERATURE-DEVIATION-LIMIT | 10 | K | fixed 10 | symmetric saturation | Synthetic assumption | fixed model-domain limit |

## Validation plan and non-goals

Acceptance evidence will include dimensional checks, zero-pressure and
zero-velocity limiting cases, finite/non-negative MRR, bounded monotonic
modifiers, deterministic local finite-difference sensitivity, a deterministic
global corner sweep, and mismatch configurations within the stated bounds.
The coupling test will also show that changing electrical/drive telemetry while
holding the UPW state fixed cannot change the MRR modifier.

This formulation is not a calibrated CMP chemistry, a model of slurry
distribution, validated WIWNU, defect prediction, or an assertion that UPW
temperature, pressure, or flow has these magnitudes in a real fab.

## Follow-on decisions still open

Safe envelope and horizon, warning uncertainty, hybrid residual learner,
compound-event scoring, controller objective, action bounds, safety envelope,
restart rules, and paired-comparison success thresholds remain unfrozen.
