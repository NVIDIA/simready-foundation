# connectionpoints-scope-structure

| Code     | CP.001 |
|----------|--------|
| Validator| {oav-validator-latest-link}`cp-001` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

Connection point prims must be organized under a `ConnectionPoints` Scope prim that is a direct child of the default prim.

## Description

All thermal, electrical, and airflow connection point geometry must live under a single `ConnectionPoints` scope. This creates a predictable traversal path for simulation runtimes and tooling to find connection points without scanning the entire stage.

## Why is it required?

- Provides a single, discoverable location for all interface geometry
- Enables CP.004 (naming validation) and CP.005 (composition check) to function correctly
- Required by TC.002 and EL.004 cross-domain validators

## Examples

```text
def Xform "CW375" {                    # default prim
    def Scope "ConnectionPoints" {     # required scope
        def Mesh "vertiv_fws_supply_piping_connection_main" { ... }
        def Mesh "vertiv_tcs_supply_piping_connection_main" { ... }
        def Mesh "vertiv_electrical_nominal_voltage_main" { ... }
    }
}
```

## How to comply

Create a USD Scope prim named exactly `ConnectionPoints` as a direct child of the default prim, then place all connection point geometry prims inside it. In USD Composer, this can be done via right-click in the Stage panel > Create > Scope.

## Related requirements

- CP.004 `connection-point-naming-convention`: naming validation applies to prims inside this scope
- CP.005 `connection-points-composition`: the `*_ConnectionPoints.usd` sublayer must contain this scope
- TC.002 `thermal-cooling-connection-points`: traverses this scope to check for required piping prims
- EL.004 `electrical-connection-points`: traverses this scope to check for required electrical prims

## For More Information

- [UsdGeomScope](https://openusd.org/dev/api/class_usd_geom_scope.html)
