# electrical-connection-points

| Code     | EL.004 |
|----------|--------|
| Validator| {oav-validator-latest-link}`el-004` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

Equipment with electrical connections must have at least one connection point prim matching the `*_electrical_nominal_voltage_*` pattern.

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

## Related requirements

- AM.002 `asset-class-required`: `aif:core:assetClass` must be set for this validator to identify AC-powered equipment
- EL.001 `nominal-voltage-required`: electrical metadata must be present alongside connection points
- CP.001 `connectionpoints-scope-structure`: the `ConnectionPoints` scope must exist to be traversed
- CP.004 `connection-point-naming-convention`: the `electrical_nominal_voltage` type prefix must be used
- TC.002 `thermal-cooling-connection-points`: parallel cross-domain check for thermal piping interfaces

## For More Information

- [UsdGeomScope](https://openusd.org/dev/api/class_usd_geom_scope.html)
