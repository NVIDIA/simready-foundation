# mate-body-rigid-ancestor

| Code     | MC.003 |
|----------|--------|
| Validator| MateBodyChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every mechanical mate site must have an ancestor with an enabled `PhysicsRigidBodyAPI`. That ancestor is the site's **mate body** — the rigid body a jointed connection attaches to, and the actor a compound connection shares.

## Description

Walk from the site toward the stage root and take the nearest prim that has `PhysicsRigidBodyAPI` applied **and** whose composed `physics:rigidBodyEnabled` resolves true. The site itself may be that prim, but typical authoring places the site as a child `Xform` under a link.

A prim with the API applied but `physics:rigidBodyEnabled = false` is transparent to the walk. It is not a mate body, and the walk continues past it. This is how a compound assembly works: each part keeps the rigid body it was authored with, the assembly disables it, and every site inside that part resolves to the enabled compound body above it (`CN.011`).

This requirement depends on rigid-body physics being present on the asset (`FET_003_STANDARD`). A site with no enabled rigid-body ancestor has no mate body, so `CN.006` cannot resolve a realization for any connection that uses it, and `CN.009` cannot check the joint's body targets.

## Why is it required?

- A jointed connection is standard `UsdPhysics` between two bodies, not a custom mate constraint.
- Tool-change runtimes disable or destroy the authored joint on the mate bodies.
- A compound connection needs the shared mate body to identify the single physics actor.
- Reading the enabled state rather than the applied schema means an assembly demotes a part by flipping one attribute instead of stripping physics the asset author supplied.

## Examples

```usd
# Invalid: site has no rigid-body ancestor
def Xform "wrist_3_link"
{
    def Xform "tool_mount_01"
    {
        uniform token simready:mate:domain = "mechanical"
        uniform token simready:mate:role = "Socket"
    }
}

# Valid
def Xform "wrist_3_link" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
    def Xform "tool_mount_01"
    {
        uniform token simready:mate:domain = "mechanical"
        uniform token simready:mate:role = "Socket"
    }
}

# Valid: the part's rigid body is disabled, so the walk passes through it and
# the mate body is </Stack/CompoundBody>.
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
)
{
    float physics:mass = 85.5

    def Xform "Pallet_1" (
        prepend references = @../pallet/simready_usd/pallet.usd@</RootNode>
    )
    {
        bool physics:rigidBodyEnabled = false

        over "stack_plug"
        {
        }
    }
}

# Invalid: the only rigid-body ancestor is disabled and nothing above it is
# enabled, so the site has no mate body.
def Xform "Stack"
{
    def Xform "Pallet_1" (
        prepend references = @../pallet/simready_usd/pallet.usd@</RootNode>
    )
    {
        bool physics:rigidBodyEnabled = false
    }
}
```

## How to comply

1. Apply `PhysicsRigidBodyAPI` to the link or part that owns the coupling face.
2. Keep the mate site under that link (or on it).
3. Leave `physics:rigidBodyEnabled` at its true default, or, when the part is demoted into a compound, make sure an enabled body sits above it.

## Related Requirements

- [mate-realization](../../connections/requirements/mate-realization.md)
- [connection-joint](../../connections/requirements/connection-joint.md)
- [compound-body](../../connections/requirements/compound-body.md)

## For More Information

- [UsdPhysics Rigid Body](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
