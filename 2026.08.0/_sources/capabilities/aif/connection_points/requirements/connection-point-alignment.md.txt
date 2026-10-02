# connection-point-alignment

| Code     | CP.006 |
|----------|--------|
| Validator|  |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`normative` |

## Summary

Connection point geometry must be positioned and sized to match the actual physical openings on the equipment. The requirement is documented normatively and is listed by neither the v0.1.0 nor the v0.2.0 feature.

## Description

Each connection point prim should be placed at the exact location of the corresponding physical interface on the equipment model, oriented so its normal vector points in the direction of flow or connection. The geometry size should match the actual opening dimensions.

## Why is it required?

- Accurate positioning enables simulation runtimes to automatically connect piping, ducts, and cables
- Misaligned connection points produce incorrect simulation results in facility models

## Examples

Alignment is authored as the connection point's transform. Under v0.2.0 the
connection point is an Xform, so its `xformOp:translate` is the position of the
physical opening in the asset's local frame and its rotation turns the local
+Z axis into the direction of flow. No validator checks alignment against the
geometry; the Valid block below is checked only for being well formed.

### Valid: a liquid supply connection placed at its flange

A CRAH whose supply flange sits on the rear face, 0.42 m from the left edge and
0.31 m above the floor, with flow leaving the unit along -Y.

```usd
def Xform "Generic_CRAH"
{
    def Scope "ConnectionPoints"
    {
        def Xform "acme_liq_supply_main"
        {
            uniform token purpose = "guide"
            double3 xformOp:translate = (0.42, -0.43, 0.31)
            float3 xformOp:rotateXYZ = (90, 0, 0)
            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]

            token simready:connectionPoint:domain = "thermal"
            token simready:connectionPoint:direction = "supply"
            token simready:connectionPoint:system = "FWS"
            token simready:connectionPoint:disconnectType = "flanged"
            float simready:connectionPoint:serviceClearance = 0.3
        }
    }
}
```

The same prim misaligned, as authoring tools commonly leave it: the transform
is identity, so the connection point sits at the asset origin, inside the
cabinet, pointing up. A runtime that auto-connects piping to it connects to
the wrong place. This is not a validator finding, which is why the block is not
captioned Invalid.

```usda
def Xform "acme_liq_supply_main"
{
    uniform token purpose = "guide"
    # No xformOp:translate, no rotation: the point is at (0, 0, 0), normal +Z.
    token simready:connectionPoint:domain = "thermal"
    token simready:connectionPoint:direction = "supply"
    token simready:connectionPoint:system = "FWS"
    token simready:connectionPoint:disconnectType = "flanged"
    float simready:connectionPoint:serviceClearance = 0.3
}
```

## How to comply

Position each connection point prim at the physical opening location on the main geometry. For piping connections, align with the top of the pipe opening. For airflow vents, simplify intricate vent patterns to their aggregate area. Alignment is authored manually.

## Related requirements

- CP.001 `connectionpoints-scope-structure`: connection point prims must be inside the `ConnectionPoints` scope
- CP.002 `connection-point-geometry-type`: under v0.1.0, geometry type must match the opening shape before alignment is meaningful
- CP.004 `connection-point-naming-convention`: under v0.1.0, prims must be correctly named to identify what they represent
- CP.010 `connection-point-prim-structure`: under v0.2.0 a connection point is an Xform, so alignment is its transform and this requirement's geometry sizing does not apply

## For More Information

- [UsdGeomXformable](https://openusd.org/release/api/class_usd_geom_xformable.html)
