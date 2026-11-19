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

Each example is a complete stage; the first prim is the default prim.

### Valid: the scope is a direct child of the default prim

```usd
def Xform "Generic_CRAH"
{
    def Scope "ConnectionPoints"
    {
        def Mesh "acme_liq_supply_main"
        {
        }

        def Mesh "acme_liq_return_main"
        {
        }

        def Mesh "acme_electrical_nominal_voltage_main"
        {
        }
    }
}
```

### Invalid: the scope sits under a child of the default prim

Every connection point rule starts from the scope this requirement locates. A
scope one level down is never found, so CP.004 and CP.010 to CP.012 walk past
its contents and report nothing.

```usd
def Xform "Generic_CRAH"
{
    def Xform "Geometry"
    {
        def Scope "ConnectionPoints"
        {
            def Mesh "acme_liq_supply_main"
            {
            }
        }
    }
}
```

### Invalid: `ConnectionPoints` is an Xform, not a Scope

```usd
def Xform "Generic_CRAH"
{
    def Xform "ConnectionPoints"
    {
        def Mesh "acme_liq_supply_main"
        {
        }
    }
}
```

### Invalid: the scope is empty

```usd
def Xform "Generic_CRAH"
{
    def Scope "ConnectionPoints"
    {
    }
}
```

### Invalid: there is no `ConnectionPoints` prim

```usd
def Xform "Generic_CRAH"
{
    def Scope "Geometry"
    {
    }
}
```

A stage with no `defaultPrim` fails for the same reason: there is no prim to
look under. It cannot be shown as a fenced example because the example harness
supplies a default prim.

## How to comply

Create a USD Scope prim named exactly `ConnectionPoints` as a direct child of the default prim, then place all connection point geometry prims inside it. In USD Composer, this can be done via right-click in the Stage panel > Create > Scope.

## Related requirements

- CP.004 `connection-point-naming-convention`: naming validation applies to prims inside this scope
- CP.005 `connection-points-composition`: the `*_ConnectionPoints.usd` sublayer must contain this scope
- TC.002 `thermal-cooling-connection-points`: traverses this scope to check for required piping prims
- EL.004 `electrical-connection-points`: traverses this scope to check for required electrical prims

## For More Information

- [UsdGeomScope](https://openusd.org/dev/api/class_usd_geom_scope.html)
