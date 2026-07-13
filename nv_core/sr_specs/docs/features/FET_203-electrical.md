# AIF Electrical

**Feature:** FET203_AIF_NEUTRAL

Validates electrical metadata and connection points for AC-powered equipment (CDU, CRAH, UPS). Not applicable to Compute Rack equipment (e.g. GB300), which uses DC power profiles only.

## Requirements

- EL.001: nominal input voltage attribute present (per-class attribute name)
- EL.002: power rating attribute present (per-class attribute name)
- EL.003: input frequency attribute present (per-class attribute name)
- EL.004: `*_electrical_nominal_voltage_*` connection point prim present

## Dependencies

- FET201_AIF_NEUTRAL v0.1.0 (Connection Points)
