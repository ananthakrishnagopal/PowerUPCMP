# Real Fab Data Contract

## Purpose
In order to transition the PowerUPCMP predictive models from the simulated PoC into a live factory environment, the following real fab data requirements and limitations must be explicitly satisfied.

## Signal Requirements
The factory environment must expose the following parameters at a minimum of 10 Hz via SECS/GEM or a comparable broker:
- `grid_voltage_pu` [PU]
- `grid_frequency_hz` [Hz]
- `ups_output_voltage_pu` [PU]
- `ups_output_frequency_hz` [Hz]
- `pump_flow_m3_s` [m^3/s]
- `upw_supply_pressure_pa` [Pa]
- `cmp_mode` [String: DRESS, POLISH, HOLD]
- `cmp_mrr_m_s` [m/s] - *Process truth (often delayed, may require virtual metrology estimation)*

## Limitations & Integration Constraints
- **Latency Budget**: Predictive and attribution models must execute in < 10 ms. The entire loop (sensor acquisition to command issuance) must execute in < 50 ms.
- **Safety Overrides**: An independent hard-coded safety filter must be present downstream of the predictive controller to reject any commands that violate tool operation safety constraints (e.g., stopping the pump while polishing).
- **Missing Data**: The PoC model imputation strategies will fail if missing data exceeds 2 seconds. The real system must trigger a `SAFE_HOLD` automatically under prolonged signal loss.
