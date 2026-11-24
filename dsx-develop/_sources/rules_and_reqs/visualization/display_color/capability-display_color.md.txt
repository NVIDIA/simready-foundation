# Display Color

**Capability:** Display Color (DC)

## Display Color Overview

This capability covers the display primvars on geometry, `primvars:displayColor` and its companion `primvars:displayOpacity`: where they must resolve, and what values they may carry.

`displayColor` is defined by `UsdGeomGprim` as a colour that a consumer can use "even in the absence of any specified shader for a gprim". It carries no shading network, so it is available to consumers that do not evaluate materials, such as low-fidelity and non-ray-traced render paths. `displayOpacity` is documented as a companion to `displayColor`, "broken out as an independent attribute rather than an rgba color, both so that each can be independently overridden", which is why the two are specified here as separate requirements.

Requirements for shaded appearance belong to the Visual Materials capability.

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
