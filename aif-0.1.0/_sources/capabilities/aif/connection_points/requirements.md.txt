# Requirements

## Summary

- **Connection point prims must be organized under a `ConnectionPoints` Scope prim.**
- **Connection point prims must be Plane or Disk geometry only.** *(documented; validation deferred)*
- **All connection point prims must have `purpose = "guide"`.** *(documented; validation deferred)*
- **Connection point prims must follow the `<vendor>_<type>_<suffix>` naming convention.**
- **Connection points must be saved as `<AssetName>_ConnectionPoints.usd` and composed as a sublayer.**
- **Connection point geometry must be positioned and sized to match actual openings on equipment.** *(deferred to v0.2.0+)*

## Requirements & Recommendations

<!-- AIF_CONNECTION_POINTS_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- AIF_CONNECTION_POINTS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/connectionpoints-scope-structure
requirements/connection-point-geometry-type
requirements/connection-point-purpose-guide
requirements/connection-point-naming-convention
requirements/connection-points-composition
requirements/connection-point-alignment
```
