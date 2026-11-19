# Collision envelope invariant

| Code | AV.006 |
|---|---|
| Validator | CollisionEnvelopeInvariantChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`physics` |

## Summary

Every option of a variation variant set that carries colliders MUST hold the
asset's collision envelope size invariant within tolerance.

## Description

The collision envelope is the world-aligned bounding box computed over the
collision purposes (`proxy`, `guide`; falling back to `default` colliders) with
`UsdGeom.BBoxCache`. For each variation variant set whose options affect
colliders, the envelope **size** under each option MUST match the size under the
authored default within an absolute tolerance of `1e-3` meters per axis.

A `Collision` variation changes collider *fidelity* (for example convex hull vs
triangle mesh vs primitives) at the same footprint; it never changes the
footprint size. A `visual-only` variation must not change colliders at all, so
its collision envelope is trivially invariant. An option that resizes the
collision envelope is a different asset, not a variation, and fails.

Assets with no authored colliders (for example a `NuRec` visual-only asset) have
no collision envelope and are exempt.

## Why

A runtime places, stacks, and resolves contacts using the collision footprint.
Resizing it on a variant selection would change where the asset can go and how
it interacts, which is exactly what a variation must not do.

## Examples

Content is shown inline for brevity; a production asset isolates each option's
content in its own payload (`AV.004`).

### Valid: both collider options span the same collision envelope

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Collision = {
                    dictionary Collision = {
                        string prim = "/Asset"
                        string variantSetName = "Collision"
                        string category = "Collision"
                        string default = "ConvexHull"
                        string impactClass = "simulation-affecting"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Collision = "ConvexHull"
    }
    prepend variantSets = ["Collision"]
)
{
    variantSet "Collision" = {
        "ConvexHull" {
            def Cube "Collider" (
                prepend apiSchemas = ["PhysicsCollisionAPI"]
            )
            {
                double size = 0.4
                uniform token purpose = "proxy"
            }
        }
        "TriangleMesh" {
            def Cube "Collider" (
                prepend apiSchemas = ["PhysicsCollisionAPI"]
            )
            {
                double size = 0.4
                uniform token purpose = "proxy"
            }
        }
    }
}
```

Both options present a `0.4 x 0.4 x 0.4` m collision box; only the approximation
fidelity differs.

### Invalid: a collider option resizes the collision envelope

```usd
#usda 1.0
(
    defaultPrim = "Asset"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Collision = {
                    dictionary Collision = {
                        string prim = "/Asset"
                        string variantSetName = "Collision"
                        string category = "Collision"
                        string default = "ConvexHull"
                        string impactClass = "simulation-affecting"
                    }
                }
            }
        }
    }
)
def Xform "Asset" (
    variants = {
        string Collision = "ConvexHull"
    }
    prepend variantSets = ["Collision"]
)
{
    variantSet "Collision" = {
        "ConvexHull" {
            def Cube "Collider" (
                prepend apiSchemas = ["PhysicsCollisionAPI"]
            )
            {
                double size = 0.4
                uniform token purpose = "proxy"
            }
        }
        "TriangleMesh" {
            def Cube "Collider" (
                prepend apiSchemas = ["PhysicsCollisionAPI"]
            )
            {
                double size = 0.44
                uniform token purpose = "proxy"
            }
        }
    }
}
```

`TriangleMesh` inflates the footprint to `0.44 x 0.44 x 0.44` m; collider fidelity
may change across options, the footprint may not.

## How to comply

Author each collider option to the same footprint size; change only its
approximation/fidelity. Keep `visual-only` options free of collider edits.

## Related requirements and references

`AV.005` owns the visual envelope; `AV.007` owns impact-class honesty;
`AV.009` owns the authored mass/inertia that must also stay invariant across
collision options. `RB.*` own collider presence and approximation.
