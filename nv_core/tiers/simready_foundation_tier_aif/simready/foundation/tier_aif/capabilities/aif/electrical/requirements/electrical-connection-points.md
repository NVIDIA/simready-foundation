# electrical-connection-points

| Code     | EL.004 |
|----------|--------|
| Validator| {oav-validator-latest-link}`el-004` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

AC-powered equipment must have at least one electrical connection point, identified by its name in AIF 0.1.0 or its domain property in AIF 0.2.0.

## Description

This is a cross-domain check that reads `aif:core:assetClass` from the metadata domain and verifies that an electrical connection point prim exists in the geometry domain. CDUs, CRAHs, and UPS units all have AC power connections that must be represented as locatable geometry.

## Why is it required?

- Ensures electrical interfaces declared in metadata are spatially represented
- Simulation runtimes use CP geometry to locate power connection points for electrical simulation
- Complements TC.002 (thermal piping CPs) with the electrical counterpart

## Applies to

Equipment with `aif:core:assetClass` = `CDU`, `CRAH`, or `UPS`.

## Examples

```
def Scope "ConnectionPoints" {
    def Mesh "trane_electrical_nominal_voltage_main" { ... }
}
```

## How to comply

Ensure your `ConnectionPoints` scope contains at least one prim with `electrical_nominal_voltage` in its name, following the CP.004 naming convention: `<vendor>_electrical_nominal_voltage[_<suffix>]`.

That naming convention applies to AIF 0.1.0. For AIF 0.2.0,
`FET203_AIF@0.2.0` instead requires a connection point with
`simready:connectionPoint:domain = "electrical"`; its prim name is arbitrary.
The deprecated `type` alias for `domain` is read consistently with CP.011.
CP.010–CP.012 validate structure and property data separately.

The shared checker selects the property vocabulary when
`aif:core:simreadyVersion` on the Properties-layer default prim is `"0.2.0"`,
as specified by AM.005. Older or unversioned assets retain the legacy name
check. Compute-rack assets remain exempt from EL.004.

## Related requirements

- AM.002 `asset-class-required`: `aif:core:assetClass` must be set for this validator to identify AC-powered equipment
- EL.001 `nominal-voltage-required`: electrical metadata must be present alongside connection points
- CP.001 `connectionpoints-scope-structure`: the `ConnectionPoints` scope must exist to be traversed
- CP.004 `connection-point-naming-convention`: the `electrical_nominal_voltage` type prefix must be used
- TC.002 `thermal-cooling-connection-points`: parallel cross-domain check for thermal piping interfaces

## For More Information

- [UsdGeomScope](https://openusd.org/dev/api/class_usd_geom_scope.html)
