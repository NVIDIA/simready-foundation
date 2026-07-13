# thermal-cooling-connection-points

| Code     | TC.002 |
|----------|--------|
| Validator| {oav-validator-latest-link}`tc-002` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

Cooling equipment must have connection point prims matching its piping interface types: CDUs require FWS and TCS connection points; CRAHs require liquid supply and return connection points.

## Description

This is a cross-domain check that reads `aif:core:assetClass` from the metadata domain and verifies that the corresponding connection point prims exist in the geometry domain. The check ensures that the piping interfaces declared in equipment metadata are actually represented as locatable geometry.

## Why is it required?

- Ensures piping interfaces documented in metadata are spatially represented
- Simulation runtimes use CP geometry to locate pipe connection points for fluid simulation
- A CDU with metadata but no FWS/TCS CPs cannot be connected in a facility model

## Required Connection Point Types

| Equipment Class | Required CP Type Prefixes |
|----------------|--------------------------|
| CDU | `fws_supply`, `fws_return`, `tcs_supply`, `tcs_return` |
| CRAH | `liq_supply`, `liq_return` |

## Examples

```
# Valid CDU connection points
def Scope "ConnectionPoints" {
    def Mesh "vertiv_fws_supply_piping_connection_main" { ... }
    def Mesh "vertiv_fws_return_piping_connection_main" { ... }
    def Mesh "vertiv_tcs_supply_piping_connection_main" { ... }
    def Mesh "vertiv_tcs_return_piping_connection_main" { ... }
}
```

## How to comply

Ensure your `ConnectionPoints` scope contains at least one prim for each required type prefix. Follow the CP.004 naming convention: `<vendor>_<type_prefix>[_<suffix>]`.

## Related requirements

- AM.002 `asset-class-required`: `aif:core:assetClass` must be set for this validator to determine required CP types
- TC.001 `nominal-cooling-capacity`: cooling capacity metadata must be present alongside connection points
- CP.001 `connectionpoints-scope-structure`: the `ConnectionPoints` scope must exist to be traversed
- CP.004 `connection-point-naming-convention`: connection points must follow the naming pattern to be identified

## For More Information

- [UsdGeomScope](https://openusd.org/dev/api/class_usd_geom_scope.html)
