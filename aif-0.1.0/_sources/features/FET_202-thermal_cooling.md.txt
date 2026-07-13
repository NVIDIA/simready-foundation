# AIF Thermal Cooling

**Feature:** FET202_AIF_NEUTRAL

Validates thermal cooling metadata and connection points for cooling equipment (CDU, CRAH). Not applicable to UPS or Compute Rack equipment (e.g. GB300).

## Requirements

- TC.001: `aif:spec:nominalCoolingCapacity` present on CDU/CRAH assets
- TC.002: thermal piping connection points match the declared equipment class (FWS/TCS for CDU; liq for CRAH)

## Dependencies

- FET201_AIF_NEUTRAL v0.1.0 (Connection Points)
