# Requirements

## Summary

### v0.1.0 — geometry prims

- **Connection point prims must be organized under a `ConnectionPoints` Scope prim.**
- **Connection point prims must be Plane or Disk geometry only.**
- **All connection point prims must have `purpose = "guide"`.**
- **Connection point prims must follow the `<vendor>_<type>_<suffix>` naming convention.**
- **Connection points must be saved as `<AssetName>_ConnectionPoints.usd` and composed as a sublayer.**
- **Connection point geometry must be positioned and sized to match actual openings on equipment.**

### v0.2.0 — property vocabulary

- **Connection points must be Xform prims under the `ConnectionPoints` scope with `purpose = "guide"`, carrying at least `domain` and `direction`.**
- **Every connection point must carry all five base namespace properties.**
- **Domain-specific properties must sit in the namespace named by the connection's `domain` value.**

The two vocabularies coexist in the data, and assets migrate incrementally with no cutover date.
They are kept apart in validation by the feature version a profile selects, since several v0.1.0
requirements contradict v0.2.0 directly. CP.004 requires the `<vendor>_<type>_<suffix>` prim-name
pattern that v0.2.0 stops enforcing, and CP.002 requires Plane or Disk geometry where CP.010
requires an Xform. Neither version's requirement set is a superset of the other, so a profile
selects one feature version and gets a coherent set.

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
requirements/connection-point-prim-structure
requirements/connection-point-base-namespace
requirements/connection-point-domain-namespace
```
