# AIF Electrical

**Capability:** AIF Electrical (EL)

## Overview

Validates electrical metadata and connection points for AIF AC-powered equipment. This capability applies to CDUs, CRAHs, and UPS units.

Compute Rack equipment (e.g. GB300) uses DC power profiles (not AC parameters) and is excluded from this capability. Its electrical characteristics are validated via AM.007 (equipment-class template compliance).

**Note on attribute naming:** Electrical attribute names are not yet harmonized across equipment classes. EL.001–EL.003 validators maintain per-class attribute name mappings until the upstream CSV templates are updated to a single naming convention.

## Reference Table

The three core electrical attributes (nominal voltage, power rating, frequency) appear under different `aif:spec:*` names depending on the equipment class. The full per-class attribute lists are in the [AIF Metadata reference tables](../metadata/capability-metadata.md).

| Concept | CDU | CRAH | UPS |
|---|---|---|---|
| Nominal Voltage | `aif:spec:nominalVoltage` | `aif:spec:electricalNominalVoltage` | `aif:spec:electricalInputVoltage` |
| Power Rating | `aif:spec:powerRating` | `aif:spec:electricalPowerRating` | `aif:spec:upsRating` |
| Frequency | `aif:spec:frequency` | `aif:spec:electricalFrequency` | `aif:spec:electricalInputFrequency` |

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
