# physx-connection-joint

| Code     | CN.PHYSX.001 |
|----------|--------------|
| Validator| PhysxConnectionJointChecker |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

A `jointed` connection joint must remain a standard `UsdPhysicsFixedJoint` with explicit `physics:collisionEnabled = false`, must not apply `PhysxJointAPI` degree-of-freedom tuning, and must leave `physics:excludeFromArticulation` false or unset; when it fuses two articulations, exactly one `PhysicsArticulationRootAPI` may survive on the composed assembly.

## Description

PhysX consumes standard USD physics joints. The PhysX delta for a connection is therefore not a replacement schema but a set of constraints on what may and may not be authored alongside the standard joint.

`CN.009` requires the connection joint to exist with correct bodies and poses and to declare its attach strength. The joint checked here is the target of `simready:mate:joint` on each connection whose `realization` is `jointed`. Connections with `realization = "compound"` have no joint and are skipped.

### Standard joint retained

PhysX maps `UsdPhysicsFixedJoint` directly. There is no separate PhysX fixed-joint type, so the connection joint must stay a `UsdPhysicsFixedJoint`.

Attach strength belongs to `CN.009`. `physics:breakForce` and `physics:breakTorque` are `UsdPhysicsJoint` attributes that PhysX reads directly, so one requirement covers every runtime.

### No degree-of-freedom tuning

`PhysxJointAPI` carries `physxJoint:armature`, `physxJoint:jointFriction`, and `physxJoint:maxJointVelocity`. Every one of these describes the behavior of a degree of freedom.

A fixed connection joint has no degree of freedom, so these attributes have no meaning on it. Applying `PhysxJointAPI` to the connection joint fails. Authoring any attribute in the `physxJoint:` namespace directly on it fails for the same reason.

The rule covers the whole namespace, including a `physxJoint:` name that no PhysX schema defines. Such a name composes as a custom attribute that no runtime reads, so it reports as authored while the property PhysX consumes keeps its fallback value.

### Contact between the mate bodies

The joint must author `physics:collisionEnabled = false`.

The mate convention places the socket and plug frames coincident, so the two coupling faces occupy the same space and their colliders overlap. With contact enabled, PhysX generates contact forces on that overlap and fights the joint that is holding the pose. Authoring the attribute explicitly keeps the intent in the asset rather than relying on the `UsdPhysicsJoint` default.

### Articulation interaction

A connection joint whose two mate bodies — the nearest enabled `PhysicsRigidBodyAPI` ancestor of each site (`MC.003`) — each sit under a `PhysicsArticulationRootAPI` ancestor fuses two articulations into one. This is the common arm-plus-gripper case, where each asset ships its own articulation root from its standalone form.

The joint is part of the articulation it fuses, so `physics:excludeFromArticulation` must be `false` or unset. It carries the load between the two assets, and the reduced-coordinate solver that handles the rest of the assembly is what holds it.

The fused result is one articulation, so the composed assembly must carry exactly one `PhysicsArticulationRootAPI`: the plug asset's own articulation root is deactivated or removed by the assembly. Two surviving roots are ambiguous to the PhysX importer.

Deactivating that root is a separate edit from deactivating the plug's world pin (`CN.009`), and the two are not always the same prim. An asset may carry `PhysicsArticulationRootAPI` on its enclosing prim or on its internal fixed root joint, so the assembly has to remove whichever placement its plug uses. Determining membership uses the same walk as `FET_024_PHYSX`, which looks for both placements.

`physics:excludeFromArticulation = true` belongs to a mechanism that closes a loop inside a single asset, such as a four-bar linkage (`DJ.011`). A connection adds one path between two assets and is not that case.

## Why is it required?

- PhysX consumes standard USD joints, so an invented PhysX fixed-joint schema would not import.
- Degree-of-freedom tuning on a zero-degree-of-freedom joint is authored data no runtime can apply, and an undefined `physxJoint:` name reads as authored intent while the property PhysX consumes keeps its fallback.
- Coincident coupling faces produce overlapping colliders, and contact on that pair works against the joint rather than with it.
- A connection joint excluded from the articulation drops the coupling out of the reduced-coordinate solver that the rest of the assembly uses.
- Two surviving articulation roots on one assembly are ambiguous to the PhysX importer.

## Examples

```usd
# Valid: standard fixed joint, explicit contact filtering, no DOF tuning; the
# arm and gripper fuse into one articulation and the joint is part of it
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = false
}

# Valid: the plug asset's articulation root is removed by the assembly, so
# only the arm's root survives on the composed stage
over "Gripper" (
    delete apiSchemas = ["PhysicsArticulationRootAPI", "PhysxArticulationAPI"]
)
{
}

# Invalid: PhysxJointAPI DOF tuning applied to a fixed connection joint
def PhysicsFixedJoint "arm_to_gripper_joint" (
    prepend apiSchemas = ["PhysxJointAPI"]
)
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    float physxJoint:armature = 0.0001
    float physxJoint:maxJointVelocity = 130
}

# Invalid: undefined physxJoint: names. These compose as custom attributes no
# runtime reads, and physics:breakForce / physics:breakTorque (CN.009) are
# unauthored, so the joint is unbreakable.
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = false
    custom float physxJoint:breakForce = inf
    custom float physxJoint:breakTorque = inf
}

# Invalid: contact left enabled on coincident coupling faces
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = true
}

# Invalid: the joint is excluded from the articulation it fuses
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    bool physics:collisionEnabled = false
    bool physics:excludeFromArticulation = true
}

# Invalid: both assets keep their articulation root, so the fused
# articulation has two roots
def Xform "Assembly"
{
    def Xform "Arm" (
        prepend apiSchemas = ["PhysicsArticulationRootAPI"]
    )
    {
    }

    def Xform "Gripper" (
        prepend apiSchemas = ["PhysicsArticulationRootAPI"]
    )
    {
    }
}
```

## How to comply

1. Author the connection joint as a `UsdPhysicsFixedJoint` per `CN.009`.
2. Author `bool physics:collisionEnabled = false` on it.
3. Do not apply `PhysxJointAPI` and do not author any `physxJoint:` attribute on the connection joint. Attach strength is `physics:breakForce` and `physics:breakTorque` (`CN.009`).
4. Leave `physics:excludeFromArticulation` unset, or author it `false`.
5. Resolve whether each mate body sits under a `PhysicsArticulationRootAPI` ancestor. When both do, deactivate or remove the plug asset's articulation root so exactly one root survives on the composed assembly.

## Related Requirements

- [connection-joint](connection-joint.md)
- [mate-realization](mate-realization.md)
- [has-articulation-root](../../../physics_bodies/base_articulation/requirements/has-articulation-root.md)
- [no-articulation-loops](../../../physics_bodies/physics_driven_joints/requirements/no-articulation-loops.md)

## For More Information

- [UsdPhysics Joints](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
- [PhysX Schema: PhysxJointAPI](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/class_physx_schema_physx_joint_a_p_i.html)
