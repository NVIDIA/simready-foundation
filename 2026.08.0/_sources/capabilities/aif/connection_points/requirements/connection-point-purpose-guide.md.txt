# connection-point-purpose-guide

| Code     | CP.003 |
|----------|--------|
| Validator|  |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`normative` |

## Summary

All connection point prims must have their `purpose` attribute set to `"guide"`. The rule carries
across both vocabularies: under v0.2.0 CP.010 applies it to connection point Xforms.

## Description

Setting purpose to `guide` prevents connection point geometry from appearing in final renders while still being visible in design/simulation viewports when "Show By Purpose > Guide" is enabled.

## Why is it required?

- Connection point prims are not part of the visible asset. They are markers for simulation runtimes
- Purpose `guide` is the USD convention for non-render geometry used for rigging and simulation

## Examples

```usda
def Mesh "nvidia_fws_supply_01" {
    uniform token purpose = "guide"
}
```

## How to comply

Set the `purpose` attribute to `"guide"` on each connection point prim. In USD Composer, this can be done by selecting the prim and editing the `purpose` attribute in the Properties panel.

## Related requirements

- CP.001 `connectionpoints-scope-structure`: connection point prims must be inside the `ConnectionPoints` scope
- CP.002 `connection-point-geometry-type`: geometry type (Plane/Disk) must also be set correctly
- CP.010 `connection-point-prim-structure`: carries this rule under v0.2.0

## For More Information

- [UsdGeomImageable](https://openusd.org/release/api/class_usd_geom_imageable.html)
