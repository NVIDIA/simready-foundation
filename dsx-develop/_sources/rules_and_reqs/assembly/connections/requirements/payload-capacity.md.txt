# payload-capacity

| Code     | CN.005 |
|----------|--------|
| Validator| PayloadCapacityChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Socket `simready:mate:mechanical:maxPayload` must be greater than or equal to the plug subtree mass. Incomplete mass on rigid bodies in that subtree warns rather than fails. Only `jointed` connections are checked; a compound has no joint to rate.

## Description

This check applies only to connections with `realization = "jointed"`, where the socket and plug resolve to two distinct mate bodies (`CN.006`) and the authored joint (`CN.009`) carries the load.

Connections with `realization = "compound"` are skipped. There both sites resolve to the same rigid body, so the plug subtree is the compound itself and there is no joint to rate. `CN.011` checks that compound's aggregate mass instead. Cumulative load through a chain of nested assets is not modeled by this requirement.

Sum `physics:mass` from prims with `PhysicsMassAPI` in the plug site's mate-body subtree. Do **not** read `SR.003` `customLayerData` mass: that value lives on an asset's root layer and does not compose across a reference.

Walk down from the mate body and stop at the first prim on each branch that authors `physics:mass`; that value stands for its whole subtree. Stopping is what keeps a compound aggregate from being added to the part masses beneath it. A jointed connection whose plug is itself a compound therefore contributes one aggregate, not the aggregate plus each fused part. This mirrors the `RB.007` traversal, which stops descending at a body that owns its own mass, and it is the same walk `CN.011` uses.

If every branch in the subtree yields an explicit mass, compare the sum to `maxPayload` and fail when the sum is greater. If any branch yields none, warn and skip the fail.

`maxPayload` and `physics:mass` are kilograms.

## Why is it required?

- A legal swap is interface match plus mass within the socket rating.
- Using composed `PhysicsMassAPI` is the only mass that is visible on the assembly stage.

## Examples

```usd
# Fail: socket maxPayload 5 kg, plug subtree mass 8 kg

# Warn: socket maxPayload 10 kg, one plug branch has no physics:mass

# Pass: socket maxPayload 10 kg, plug subtree mass 2.5 kg

# Pass: socket maxPayload 100 kg, plug is a compound body authoring 85.5 kg
# over three 28.5 kg pallets. The sum stops at the aggregate and is 85.5, not
# 85.5 + 3 x 28.5.

# Skipped: realization = "compound", both sites share one mate body
```

## How to comply

1. Author positive `maxPayload` on the socket (`MC.006`).
2. Author `PhysicsMassAPI` / `physics:mass` on plug rigid bodies so the assembly can sum them.
3. When the plug is a compound, make sure its compound body authors the aggregate (`CN.011`); that one value is what this check reads.

## Related Requirements

- [socket-max-payload](../../mates/requirements/socket-max-payload.md)
- [mate-realization](mate-realization.md)
- [connection-joint](connection-joint.md)
- [compound-body](compound-body.md)
