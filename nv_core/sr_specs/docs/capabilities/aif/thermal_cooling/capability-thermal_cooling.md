# AIF Thermal Cooling

**Capability:** AIF Thermal Cooling (TC)

## Overview

Validates thermal cooling metadata and connection points for AIF cooling equipment. This capability applies to CDUs (Coolant Distribution Units) and CRAHs (Computer Room Air Handlers).

Compute Rack equipment (e.g. GB300) produces heat but has no cooling-specific attributes. Its thermal characteristics are validated via AM.007 (equipment-class template compliance).

## Reference

The single cross-class thermal cooling attribute validated by TC.001 is:

| Attribute | Type | Description | Applies to |
|---|---|---|---|
| `aif:spec:nominalCoolingCapacity` | float | Nominal cooling capacity in kW | CDU, CRAH |

For the full per-class attribute lists (CDU and CRAH thermal/electrical/general spec attributes), see the [AIF Metadata reference tables](../metadata/capability-metadata.md).

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
