# mujoco-connection-joint

| Code     | CN.MUJOCO.001 |
|----------|---------------|
| Validator| MuJoCoConnectionJointChecker |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

A `jointed` connection joint must remain a standard `UsdPhysicsFixedJoint` with explicit `physics:collisionEnabled = false`, must not apply `MjcJointAPI`, must not be targeted by an `MjcActuator`, and must not author an invented MuJoCo weld or fixed-joint schema.

## Description

The official mjcPhysics schema defines MuJoCo scene, collider, mesh-collider, site, joint, actuator, equality, and tendon schemas. It defines no fixed-joint type, because MuJoCo has no fixed joint: a rigid attachment is expressed by fusing the two bodies or by an equality constraint, both of which the importer derives rather than reads from a dedicated prim type.

A MuJoCo-ready connection therefore authors the same standard joint as every other runtime, and this requirement constrains what must not be layered onto it.

The joint checked here is the target of `simready:mate:joint` on each connection whose `realization` is `jointed`. Connections with `realization = "compound"` have no joint and are skipped; a compound is already the single fused body that MuJoCo would produce.

### Standard joint retained

- the connection joint must be a `UsdPhysicsFixedJoint`
- no prim may apply `MjcWeldAPI`, `MjcFixedJointAPI`, or any other MuJoCo weld or fixed-joint API that is not in the official schema
- no prim may use an `MjcWeld` or `MjcFixedJoint` type

### Not an articulation joint

`MjcJointAPI` marks a joint that participates in the MuJoCo articulation as a degree of freedom, and `MjcActuator` prims drive such joints. A fixed connection joint is neither.

- the connection joint must not apply `MjcJointAPI`
- no `MjcActuator` prim may target the connection joint

This matches how MuJoCo driven-joint validation treats fixed joints elsewhere in the tier: `MjcJointAPI` is required on every non-fixed articulation joint and is not applied to fixed joints.

### Contact between the mate bodies

The joint must author `physics:collisionEnabled = false`. The socket and plug frames are coincident, so the coupling faces overlap. MuJoCo fuses or welds the pair, and contact authored between two bodies that the solver treats as one is both wasteful and a source of instability.

## Why is it required?

- MuJoCo imports standard USD joints; an invented weld schema would not resolve against the official mjcPhysics schema.
- `MjcJointAPI` and `MjcActuator` on a zero-degree-of-freedom joint present a rigid attachment to MuJoCo tooling as a controllable DOF.
- Overlapping coupling faces on a welded pair generate contact that the solver must resolve against its own constraint.

## Examples

```usd
# Valid: standard fixed joint with explicit contact filtering
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = false
}

# Invalid: invented MuJoCo weld API
def PhysicsFixedJoint "arm_to_gripper_joint" (
    prepend apiSchemas = ["MjcWeldAPI"]
)
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
}

# Invalid: connection joint marked as a MuJoCo articulation DOF
def PhysicsFixedJoint "arm_to_gripper_joint" (
    prepend apiSchemas = ["MjcJointAPI"]
)
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = false
}

# Invalid: actuator driving a connection joint
def MjcActuator "arm_to_gripper_actuator"
{
    rel mjc:target = </Assembly/Connections/arm_to_gripper_joint>
}

# Invalid: contact left enabled on the welded pair
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = true
}
```

## How to comply

1. Author the connection joint as a `UsdPhysicsFixedJoint` per `CN.009`.
2. Author `bool physics:collisionEnabled = false` on it.
3. Do not apply `MjcJointAPI` to the connection joint and do not point an `MjcActuator` at it.
4. Do not author MuJoCo weld or fixed-joint schemas that are absent from the official mjcPhysics schema.
5. Where the attachment is permanent, prefer `realization = "compound"`, which expresses the fused body directly.

## Related Requirements

- [connection-joint](connection-joint.md)
- [mate-realization](mate-realization.md)
- [mujoco-standard-articulation-root](../../../physics_bodies/base_articulation/requirements/mujoco-standard-articulation-root.md)

## For More Information

- [MuJoCo OpenUSD mjcPhysics schema](https://github.com/google-deepmind/mujoco/blob/main/src/experimental/usd/mjcPhysics/schema.usda)
- [UsdPhysics Joints](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
