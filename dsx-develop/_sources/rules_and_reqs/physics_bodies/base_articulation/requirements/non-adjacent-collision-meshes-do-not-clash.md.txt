# Non-Adjacent Collision Meshes Do Not Clash

| Code     | BA.002 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary
Collision meshes on non-adjacent links in the articulation hierarchy must not overlap or intersect.

```{note}
Detection runs a single live PhysX simulation step to collect initial contact pairs, so it
requires the Isaac/Kit physics runtime (`omni.physics`, `omni.physx`, `usdrt`, `carb`). Because
that runtime is unavailable in a standalone USD-only environment (where the check could only ever
be inert), **the checker for this requirement is not shipped in this tier wheel**. It is provided
by the Isaac Sim asset-validation extension (`isaacsim.asset.validation`), which registers it with
the SimReady framework when running inside Kit. The requirement itself remains owned by this tier.
Only colliders under the stage's default prim are considered, and adjacency is evaluated on the
owning rigid body (the nearest ancestor with `UsdPhysicsRigidBodyAPI`), so collision meshes nested
several levels under a link are handled correctly.
```

## Why

When collision meshes on non-adjacent links overlap, it causes:
- Physics simulation instability at startup
- Explosive forces as the solver tries to separate interpenetrating bodies
- Unpredictable behavior that makes the asset unusable in simulation

## How to comply

- Review collision meshes for all links in the articulation.
- Ensure collision geometry has appropriate clearance between non-adjacent links.
- Use simplified collision approximations (convex hulls) that don't interpenetrate.
- Test the asset at the default pose with the selected runtime to verify no
  non-adjacent collision pairs are detected.

## Example

```text
Good: Collision meshes have clearance
┌─────┐     ┌─────┐     ┌─────┐
│Link1│─────│Link2│─────│Link3│
└─────┘     └─────┘     └─────┘
   ↑           ↑           ↑
 No overlap between Link1 and Link3

Bad: Non-adjacent collision meshes overlap
┌──┌─┐─────────────┐
│  │ │  Link1      │
│  └─│─────────┬───┘
│    │    ┌────┴────┐
│    │    │  Link2  │
│    │    └────┬────┘
│    └─────────┴──┐
│     Link3       │  ← Overlaps with Link1!
└─────────────────┘
```

