# newton-connection-joint

| Code     | CN.NEWTON.001 |
|----------|---------------|
| Validator| NewtonConnectionJointChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

A `jointed` connection joint must remain a standard `UsdPhysicsFixedJoint` with explicit `physics:collisionEnabled = false`, must not apply `NewtonJointAPI` degree-of-freedom tuning, and when it fuses two articulations exactly one `PhysicsArticulationRootAPI` may survive on the composed assembly.

## Description

Newton imports standard USD physics joints. The Newton delta for a connection is therefore not a replacement schema but a set of constraints on what may and may not be authored alongside the standard joint.

The joint checked here is the target of `simready:mate:joint` on each connection whose `realization` is `jointed`. Connections with `realization = "compound"` have no joint and are skipped.

### Standard joint retained

The official Newton USD schema resolver maps `UsdPhysicsFixedJoint` directly. There is no separate Newton fixed-joint type, so:

- the connection joint must be a `UsdPhysicsFixedJoint`
- no prim may apply an invented `NewtonFixedJointAPI` or use a `NewtonFixedJoint` type

### No degree-of-freedom tuning

`NewtonJointAPI` carries `newton:armature`, `newton:damping`, `newton:friction`, `newton:velocityLimit`, `newton:limitStiffness`, and `newton:limitDamping`. Every one of these describes the behavior of a degree of freedom.

A fixed connection joint has no degree of freedom, so these attributes have no meaning on it. Applying `NewtonJointAPI` to the connection joint fails. Authoring `newton:*` joint-tuning attributes directly on it fails for the same reason.

### Contact between the mate bodies

The joint must author `physics:collisionEnabled = false`. The mate convention places the socket and plug frames coincident, so the coupling faces overlap and contact on that pair works against the joint holding the pose. Authoring the value explicitly keeps the behavior in the asset rather than depending on importer defaults, consistent with how `NEWTON.BA.001` treats `newton:selfCollisionEnabled`.

### Articulation interaction

A connection joint whose two mate bodies — the nearest enabled `PhysicsRigidBodyAPI` ancestor of each site (`MC.003`) — each sit under a `PhysicsArticulationRootAPI` ancestor fuses two articulations into one. The composed assembly must then carry exactly one articulation root, which means the plug asset's own articulation root is deactivated or removed by the assembly.

The surviving articulation root must author `newton:selfCollisionEnabled` per `NEWTON.BA.001`. Because the coupling faces of the two assets are now inside one articulation, that value governs whether Newton generates contact across the joined flange.

## Why is it required?

- Newton consumes standard USD joints, so an invented Newton fixed-joint schema would not import.
- Degree-of-freedom tuning on a zero-degree-of-freedom joint is authored data that no runtime can apply, and it misleads tooling that reads `NewtonJointAPI` as an articulation-DOF marker.
- Coincident coupling faces overlap, and contact on that pair fights the joint rather than supporting it.
- Two surviving articulation roots on one assembly is ambiguous to the Newton importer.

## Examples

```usd
# Valid: standard fixed joint, explicit contact filtering, no DOF tuning
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = false
}

# Valid: the single surviving articulation root authors Newton self-collision
def Xform "Assembly" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
    bool newton:selfCollisionEnabled = false
}

# Invalid: NewtonJointAPI DOF tuning applied to a fixed connection joint
def PhysicsFixedJoint "arm_to_gripper_joint" (
    prepend apiSchemas = ["NewtonJointAPI"]
)
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    float newton:armature = 0.01
    float newton:damping = 0.5
}

# Invalid: contact left to the importer default
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
}

# Invalid: invented Newton fixed-joint schema
def PhysicsFixedJoint "arm_to_gripper_joint" (
    prepend apiSchemas = ["NewtonFixedJointAPI"]
)
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
}
```

## How to comply

1. Author the connection joint as a `UsdPhysicsFixedJoint` per `CN.009`.
2. Author `bool physics:collisionEnabled = false` on it.
3. Do not apply `NewtonJointAPI` and do not author `newton:*` joint-tuning attributes on the connection joint.
4. When the connection fuses two articulations, deactivate the plug asset's articulation root so one root remains, and author `newton:selfCollisionEnabled` on the survivor.

## Related Requirements

- [connection-joint](connection-joint.md)
- [mate-realization](mate-realization.md)
- [newton-articulation-root-config](../../../../../../../../simready_foundation_tier_newton/simready/foundation/tier_newton/rules_and_reqs/physics_bodies/base_articulation/requirements/newton-articulation-root-config.md)

## For More Information

- [Newton USD Parsing and Schema Resolver System](https://github.com/newton-physics/newton/blob/main/docs/concepts/usd_parsing.rst)
- [Newton USD Import Source](https://github.com/newton-physics/newton/blob/main/newton/_src/utils/import_usd.py)
