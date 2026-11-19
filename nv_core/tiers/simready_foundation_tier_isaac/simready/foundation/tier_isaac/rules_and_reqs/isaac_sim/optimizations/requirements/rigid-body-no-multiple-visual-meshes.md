# rigid-body-no-multiple-visual-meshes

| Code     | OPT.002 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

No rigid body may own two or more mergeable visual meshes.

## Description

This check counts eligible visual meshes owned by each rigid body in one
composed asset. Combining them reduces mesh prim count; actual draw-call and
performance changes depend on materials and the renderer. The adapter carries
material bindings into face `GeomSubset`s. Appearance and metadata preservation
need adapter evidence, not a second asset supplied to the validator.

### What is not merged, and why

**Collision geometry, never.** Several colliders on one body is usually a convex
decomposition of a concave shape. Merging two `convexHull` colliders yields the
hull of their union, which fills the concavity: a two-prong gripper becomes a
solid slab, and nothing in USD reports it. Collider simplification has to reason
about `physics:approximation` and convexity, which is a separate problem.

**Meshes owned by a nested rigid body**, which moves independently of its parent.

**Anything outside the `default` and `render` purposes.** Proxy and guide
geometry is shown under different conditions, so combining it with render
geometry would make one visible whenever the other is.

**Invisible meshes**, which an author may be toggling.

**Instance proxies.** Merging de-instances a shared prototype, trading memory
across every instance for render cost on one. That may be the right trade, but
it is not one to make silently.

## Examples

```usd
# Fails: one body, three visual meshes, all drawn together.
over "hand" (prepend apiSchemas = ["PhysicsRigidBodyAPI"])
{
    def Mesh "shell"   { }
    def Mesh "knuckle" { }
    def Mesh "label"   { }
}
```

```usd
# Passes: the second mesh is collision geometry, not render geometry.
over "hand" (prepend apiSchemas = ["PhysicsRigidBodyAPI"])
{
    def Mesh "shell" { }
    def Mesh "collider" (prepend apiSchemas = ["PhysicsCollisionAPI"]) { }
}
```

```usd
# Passes: the meshes belong to different bodies, which move independently.
over "forearm" (prepend apiSchemas = ["PhysicsRigidBodyAPI"])
{
    def Mesh "shell" { }
    over "hand" (prepend apiSchemas = ["PhysicsRigidBodyAPI"])
    {
        def Mesh "hand_shell" { }
    }
}
```

## Why is it required?

- Consolidating eligible geometry reduces the number of mesh prims per body.
- Reading the composed stage makes the check independent of conversion history.

## How to comply

- Run `rigid_body_visual_mesh_merge` on a staged copy, then reopen and validate it
- Leave collision geometry alone; its cost is a different problem
- Keep proxy, guide, and invisible geometry separate from render geometry

```{note}
Merged geometry belongs to every source mesh, so per-mesh metadata cannot always
be carried across. The `isaac_optimization` adapter keeps the surviving mesh's
own metadata and drops any attribute or custom-data key the sources disagree on,
rather than promoting one source's value over faces that never had it. Material
bindings are unaffected: they survive as per-face `GeomSubset`s. If an
annotation has to distinguish parts of a body, keep those parts as separate
meshes and accept the cost, or move the annotation to a `GeomSubset`.
```
