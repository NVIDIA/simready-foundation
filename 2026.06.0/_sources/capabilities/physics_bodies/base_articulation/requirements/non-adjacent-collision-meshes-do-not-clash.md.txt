# Non-Adjacent Collision Meshes Do Not Clash

| Code     | BA.002 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary
Collision meshes on non-adjacent links in the articulation hierarchy must not overlap or intersect.

## Why

When collision meshes on non-adjacent links overlap, it causes:
- Physics simulation instability at startup
- Explosive forces as the solver tries to separate interpenetrating bodies
- Unpredictable behavior that makes the asset unusable in simulation

## How to comply

- Review collision meshes for all links in the articulation.
- Ensure collision geometry has appropriate clearance between non-adjacent links.
- Use simplified collision approximations (convex hulls) that don't interpenetrate.
- Test the asset at the default pose to verify no collisions are detected.

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

