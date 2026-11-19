# connection-joint

| Code     | CN.009 |
|----------|--------|
| Validator| ConnectionJointChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every connection with `realization = "jointed"` must author `simready:mate:joint` targeting exactly one `UsdPhysicsFixedJoint` whose `physics:body0` and `physics:body1` resolve to the connection's two mate bodies, whose local poses place the socket and plug frames coincident, and which authors explicit `physics:breakForce` and `physics:breakTorque`.

## Description

A jointed connection names two mate sites on two distinct rigid bodies (`CN.006`). This requirement specifies the joint that holds them.

The joint prim must exist on the composed assembly stage. It is authored data, not a value a runtime infers from the mate sites.

### The relationship

The connection prim authors `rel simready:mate:joint` with exactly one target. Zero targets, multiple targets, or a dangling path fails. The relationship resolves following the same pattern as `JT.002`.

The relationship lives on the connection prim, not on either mate site. The pairing owns the joint in the same way it owns the socket and plug relationships (`CN.001`).

Without the relationship, a consumer must search the stage for a joint whose body pair matches the two mate bodies. That search is ambiguous whenever two connections join the same pair of bodies at different sites, which `CN.007` permits: it constrains site occupancy, not joint topology.

### The joint prim

The target must be a `UsdPhysicsFixedJoint`. A connection is a rigid attachment; a joint with degrees of freedom does not express it. Persistent DOF joints inside an asset (revolute wrist joints, gripper finger joints) are not connection joints and are not covered here.

`physics:body0` and `physics:body1` must resolve to the two mate bodies obtained by walking each site to its nearest enabled `PhysicsRigidBodyAPI` ancestor (`MC.003`). Body order is not significant. A joint whose bodies resolve to any other pair fails, including the case where one target is correct and the other points at a parent or child of the intended body, or at a part whose rigid body the assembly disabled.

### The local poses

`physics:localPos0` and `physics:localRot0` must place the joint frame at the socket site expressed in `body0`. `physics:localPos1` and `physics:localRot1` must do the same for the plug site in `body1`. Together these hold the two mate frames coincident, which is the geometric contract the mate convention establishes: coincident origins, `+Z` as the mate axis, `+X` as the rotational reference.

Comparison is to within floating-point tolerance. Authored poses that disagree with the site transforms fail, because the joint would pull the assembly out of its authored configuration on the first simulation step.

### Attach strength

The joint must author both `physics:breakForce` and `physics:breakTorque`. A finite value declares the load at which the attachment separates. `inf` declares an attachment that never breaks.

Both are `UsdPhysicsJoint` attributes, so every `UsdPhysics` runtime reads the same two values and this requirement covers PhysX, Newton, and MuJoCo alike.

Both values must be authored rather than left to the schema fallback. The fallback is `inf`, so an unauthored joint is silently unbreakable, which is indistinguishable from a deliberate choice to make it so. This is a strength statement about the coupling, distinct from `CN.005`: `maxPayload` rates the static mass a socket may carry, while these two values bound the dynamic load the joint transmits before it lets go.

### Layer placement

The joint must be authored where `simready:mate:joint` resolves with runtime payloads unloaded. Author one neutral `UsdPhysicsFixedJoint` in the assembly's physics layer. Runtime variants (`CAP029_ConnectionJoint.PhysX`, `CAP029_ConnectionJoint.Newton`, `CAP029_ConnectionJoint.MuJoCo`) overlay attributes onto that prim rather than defining their own, so the relationship target stays valid regardless of which variant is loaded.

### Runtime ownership

Authoring the joint establishes the engaged state. It does not remove the joint from runtime control. A runtime releases the pairing by following `simready:mate:joint` and setting `physics:jointEnabled = false`, retuning the joint, or deleting the prim. It re-engages by restoring the attribute or re-authoring the prim from the connection data, which remains complete after the joint is gone.

## Why is it required?

- An authored joint holds the assembly in any `UsdPhysics` runtime, including one that does not read the `simready:mate:` namespace.
- The relationship makes the joint verifiable by lookup rather than by an ambiguous search over body pairs.
- Body targets and local poses are the two ways a joint can be present but wrong, and both are statically decidable.
- Break force and break torque are the only authored statement of how strong the attachment is; no runtime can infer them from the interface token.
- `RB.012` requires a `UsdPhysicsJoint` between nested rigid bodies. An authored connection joint satisfies that rule, which permits an assembly to be nested inside another assembly.

## Examples

```usd
# Valid: joint authored, targeted by the connection, bodies and poses agree,
# permanent attachment declared explicitly
def Scope "Connections"
{
    def Scope "arm_to_gripper"
    {
        uniform token simready:mate:realization = "jointed"
        rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
        rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>
        rel simready:mate:joint = </Assembly/Connections/arm_to_gripper_joint>
    }

    def PhysicsFixedJoint "arm_to_gripper_joint"
    {
        rel physics:body0 = </Assembly/Arm/wrist_3_link>
        rel physics:body1 = </Assembly/Gripper/base_link>
        point3f physics:localPos0 = (0, 0, 0.0922)
        quatf physics:localRot0 = (1, 0, 0, 0)
        point3f physics:localPos1 = (0, 0, 0)
        quatf physics:localRot1 = (1, 0, 0, 0)
        float physics:breakForce = inf
        float physics:breakTorque = inf
    }
}

# Valid: breakable attachment with a stated mechanical rating
def PhysicsFixedJoint "plate_to_fixture_joint"
{
    rel physics:body0 = </Assembly/Fixture/base_link>
    rel physics:body1 = </Assembly/Plate/body>
    float physics:breakForce = 250
    float physics:breakTorque = 80
}

# Invalid: jointed connection with no simready:mate:joint relationship
def Scope "arm_to_gripper"
{
    uniform token simready:mate:realization = "jointed"
    rel simready:mate:socket = </Assembly/Arm/wrist_3_link/tool_mount_01>
    rel simready:mate:plug = </Assembly/Gripper/base_link/tool_plug_01>
}

# Invalid: joint bodies do not resolve to the two mate bodies
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_2_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
}

# Invalid: revolute joint on a connection
def PhysicsRevoluteJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
}

# Invalid: body1 targets a part whose rigid body is disabled, so it is not the
# plug site's mate body
def PhysicsFixedJoint "lift_to_stack_joint"
{
    rel physics:body0 = </Assembly/Lift/plate_link>
    rel physics:body1 = </Assembly/CompoundBody/Pallet_0>
}

# Invalid: local poses do not place the mate frames coincident
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
    point3f physics:localPos0 = (0, 0, 0)
    point3f physics:localPos1 = (0, 0, 0)
}

# Invalid: break thresholds left to the schema fallback, so a deliberately
# unbreakable attachment cannot be told apart from an unauthored one
def PhysicsFixedJoint "arm_to_gripper_joint"
{
    rel physics:body0 = </Assembly/Arm/wrist_3_link>
    rel physics:body1 = </Assembly/Gripper/base_link>
}
```

## How to comply

1. Resolve both mate bodies per `MC.003`, skipping any part whose rigid body is disabled, and confirm they are distinct.
2. Author a `UsdPhysicsFixedJoint` in the assembly physics layer with `physics:body0` set to the socket mate body and `physics:body1` set to the plug mate body.
3. Express each mate site transform in its own mate body and author the result as `localPos0`/`localRot0` and `localPos1`/`localRot1`.
4. Author `rel simready:mate:joint` on the connection prim targeting that joint.
5. Author `float physics:breakForce` and `float physics:breakTorque`. Use `inf` for a permanent attachment, or the rated load when the coupling has one.
6. Deactivate any competing world pin on the plug asset, such as a gripper `root_joint` carried over from its standalone form.

## Related Requirements

- [mate-realization](mate-realization.md)
- [payload-capacity](payload-capacity.md)
- [mate-body-rigid-ancestor](../../mates/requirements/mate-body-rigid-ancestor.md)
- [joint-body-target-exists](../../../physics_bodies/physics_joints/requirements/joint-body-target-exists.md)
- [rigid-body-no-nesting-without-joint](../../../physics_bodies/physics_rigid_bodies/requirements/rigid-body-no-nesting-without-joint.md)

## For More Information

- [UsdPhysics Joints](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
- [UsdPhysicsFixedJoint](https://openusd.org/dev/api/class_usd_physics_fixed_joint.html)
