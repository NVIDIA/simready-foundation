# mate-realization

| Code     | CN.006 |
|----------|--------|
| Validator| MateRealizationChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every connection prim must author `simready:mate:realization` as either `compound` or `jointed`, and the token must agree with how the two mate bodies resolve. `jointed` requires two distinct mate bodies; `compound` requires one shared mate body and must not author `simready:mate:joint`.

## Description

Resolve each site's mate body per `MC.003`: the nearest ancestor with an **enabled** `PhysicsRigidBodyAPI`. Whether those two walks land on the same prim decides which realization is legal.

| Socket vs plug mate body | `realization` | Verdict |
|---|---|---|
| Different prims | `jointed` | Pass. A joint holds the pairing. |
| Same prim | `compound` | Pass. Parenting is the hold. |
| Different prims | `compound` | Fail. Nothing holds the pairing. |
| Same prim | `jointed` | Fail. A body cannot be jointed to itself. |

A missing token fails. Any token other than `compound` or `jointed` fails. There is no default: the author must state which shape the connection is, because that choice selects which feature governs the rest of the contract.

### Scope selector

`realization` is the switch that routes a connection to its owning feature.

- `compound` connections are fully governed by `CAP027_Connections`. Composition is the mechanism, and `CN.011` specifies the shared body that carries the aggregate mass.
- `jointed` connections additionally fall under `CAP029_ConnectionJoint`, which requires the authored joint (`CN.009`) and rates it against the socket capacity (`CN.005`).

An assembly may mix both on one stage. A pallet stack bolted to a jointed lift plate has `compound` connections between the pallets and one `jointed` connection at the plate.

### Two distinct mate bodies: `jointed`

The socket and plug belong to separate rigid bodies, so something must physically hold them together. That something is an authored joint, and `CN.009` specifies it: the connection points at the joint with `simready:mate:joint`, and the joint's body targets are the two mate bodies.

Authoring the joint rather than leaving it to inference means the assembly holds its pose in any `UsdPhysics` runtime, including one that has never read the `simready:mate:` namespace. A SimReady-aware runtime still owns the joint's lifecycle: to release the pairing it follows `simready:mate:joint` and sets `physics:jointEnabled = false`, retunes the joint, or deletes the prim. Authoring establishes the default engaged state; it does not transfer ownership away from the runtime.

### One shared mate body: `compound`

Each part keeps the `PhysicsRigidBodyAPI` its author supplied, and the assembly sets `physics:rigidBodyEnabled = false` on it. Both site walks therefore pass through the parts and land on one enabled body above them — the compound body specified by `CN.011`, which carries the aggregate mass. The assembly is a single physics actor and composition holds the alignment.

Whether the parts sit as siblings under the compound body or nest inside one another does not matter to this requirement. Both shapes resolve to one mate body. Siblings are usually easier to author because each part carries its own absolute pose.

There is no joint, so `simready:mate:joint` must be absent: a rel on a compound connection has no valid target and would mislead a runtime into looking for a joint that cannot exist.

Detaching is a composition edit — re-enable the part's rigid body, reduce the compound body's aggregate mass by that part's share, and reparent it out — not a joint deletion.

## Why is it required?

- The token tells a consumer which of the two assembly shapes it is holding before it inspects any physics data.
- The failure rows are the two ways an assembly silently falls apart: two free bodies with nothing between them, or a self-joint that no runtime can build.
- Requiring the token explicitly, with no default, keeps a forgotten attribute distinguishable from a deliberate choice.

## Examples

```usd
# Valid: two mate bodies, joint authored and pointed at
def Scope "arm_to_gripper"
{
    uniform token simready:mate:realization = "jointed"
    rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
    rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>
    rel simready:mate:joint = </Assembly/Connections/arm_to_gripper_joint>
}

# Valid: compound. Both pallets have physics:rigidBodyEnabled = false, so both
# sites resolve to the enabled mate body </Stack/CompoundBody>.
def Scope "pallet_0_to_pallet_1"
{
    uniform token simready:mate:realization = "compound"
    rel simready:mate:socket = </Stack/CompoundBody/Pallet_0/stack_socket>
    rel simready:mate:plug = </Stack/CompoundBody/Pallet_1/stack_plug>
}

# Invalid: both pallets keep their rigid bodies enabled, so the sites resolve
# to two bodies posed coincident with nothing holding them.
def Scope "pallet_0_to_pallet_1"
{
    uniform token simready:mate:realization = "compound"
    rel simready:mate:socket = </Stack/Pallet_0/stack_socket>
    rel simready:mate:plug = </Stack/Pallet_1/stack_plug>
}

# Invalid: compound connection pointing at a joint
def Scope "pallet_0_to_pallet_1"
{
    uniform token simready:mate:realization = "compound"
    rel simready:mate:socket = </Stack/CompoundBody/Pallet_0/stack_socket>
    rel simready:mate:plug = </Stack/CompoundBody/Pallet_1/stack_plug>
    rel simready:mate:joint = </Stack/Connections/pallet_joint>
}

# Invalid: unrecognized token
def Scope "arm_to_gripper"
{
    uniform token simready:mate:realization = "PhysicsFixedJoint"
}
```

## How to comply

1. Resolve both mate bodies per `MC.003` before choosing a token.
2. Distinct bodies: set `realization = "jointed"`, author the joint, and point `simready:mate:joint` at it per `CN.009`. Deactivate any competing world pin on the plug asset (for example a gripper `root_joint`).
3. Shared body: set `realization = "compound"`, set `physics:rigidBodyEnabled = false` on both parts, put them under a compound body that satisfies `CN.011`, and author no `simready:mate:joint`.
4. Either way, pose the parts so the mate sites coincide. Pose is not the realization.

## Related Requirements

- [mate-body-rigid-ancestor](../../mates/requirements/mate-body-rigid-ancestor.md)
- [connection-joint](connection-joint.md)
- [compound-body](compound-body.md)
- [payload-capacity](payload-capacity.md)
- [assembly-type](assembly-type.md)

## For More Information

- [UsdPhysics Joints](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
