# MuJoCo Actuator Targets

| Code     | MUJOCO.DJ.002 |
|----------|---------------|
| Validator| MuJoCoActuatorTargetsChecker |
| Compatibility | {compatibility}`MuJoCo` |
| Tags     | {tag}`essential` |

## Summary

MuJoCo actuator prims must target valid MuJoCo-driven USD physics joints and author valid actuator parameter values.

## Description

MuJoCo-driven articulation control is represented by `MjcActuator` prims, fixed `MjcTendon` transmissions, and `MjcEqualityJointAPI` / `NewtonMimicAPI` joint equality couplings. Every `MjcActuator` prim must:

- target exactly one non-fixed `UsdPhysics.Joint` (that applies `MjcJointAPI`) or one fixed `MjcTendon` (`mjc:type = "fixed"`, whose selected `mjc:path` / `mjc:path:indices` entries target valid 1-DOF `UsdPhysics.Joint` prims with `MjcJointAPI` and non-zero effective `mjc:path:coef` contribution; omitted or empty `[]` `mjc:path:indices` / `mjc:path:coef` resolve to relationship order and unit `1.0` coefficients) via `mjc:target`
- author paired range attributes when ranges are present
- keep `mjc:ctrlRange:min`, `mjc:ctrlRange:max`, `mjc:forceRange:min`, and `mjc:forceRange:max` finite, with min less than or equal to max
- keep authored `mjc:gainPrm` and `mjc:biasPrm` values as non-empty numeric arrays
- author a non-empty `mjc:biasType` value when `mjc:biasType` is present

Every non-fixed MuJoCo articulation joint (`MjcJointAPI`, `physics:excludeFromArticulation = false`) in the feature contract must satisfy one of the following:
- be targeted directly by at least one `MjcActuator`,
- receive a non-zero effective contribution in `mjc:path` (and `mjc:path:indices` / `mjc:path:coef`) of a fixed `MjcTendon` (`mjc:type = "fixed"`) targeted by an `MjcActuator`,
- be a 1-DOF scalar joint (`PhysicsRevoluteJoint` or `PhysicsPrismaticJoint`) coupled via `MjcEqualityJointAPI` / `NewtonMimicAPI` (`rel newton:mimicJoint`, or legacy `rel mjc:target`) to an acyclic chain of 1-DOF `MjcJointAPI` articulation leader joints rooted at an actuated joint, with `newton:mimicEnabled` not `false`, non-zero effective coupling consumed by the applied schema (`newton:mimicCoef1` taking precedence over legacy `mjc:coef1`, and higher-order `mjc:coef2..4` consumed only when `MjcEqualityJointAPI` is applied), finite polynomial coefficients, and numeric `mjc:solimp` / `mjc:solref` arrays when authored, or
- be a 1-DOF scalar passive parallel-branch joint on a closed kinematic loop closed by an enabled joint with `physics:excludeFromArticulation = true` (where at least one joint on that same loop is actuated, holding the loop's actuated joint(s) leaves zero free unactuated motion dimensions in the loop constraint, and at least one endpoint body of the passive joint is a loop-only branch body whose movable joints all belong to the loop). Loop-closing joints (`physics:excludeFromArticulation = true`) omit `MjcJointAPI`.

## Why is it required?

* Ensures MuJoCo actuators resolve to concrete USD joints.
* Prevents orphaned actuators and unactuated MuJoCo-driven joints.
* Catches invalid control, force, gain, and bias values before MuJoCo import.

## Examples

```usd
# Valid: actuator targets a MuJoCo-marked USD joint.
def MjcActuator "shoulder_actuator"
{
    rel mjc:target = </robot/Physics/shoulder>
    float mjc:ctrlRange:min = -3.14
    float mjc:ctrlRange:max = 3.14
    float mjc:forceRange:min = -150.0
    float mjc:forceRange:max = 150.0
    float[] mjc:gainPrm = [100.0, 0.0, 0.0]
    float[] mjc:biasPrm = [0.0, -100.0, -10.0]
    token mjc:biasType = "affine"
}

# Invalid: actuator target is missing.
def MjcActuator "bad_actuator"
{
    float mjc:ctrlRange:min = -1.0
    float mjc:ctrlRange:max = 1.0
}
```

## How to comply

* Author one or more `MjcActuator` prims for independently driven MuJoCo articulation joints.
* Set `rel mjc:target` to either one valid non-fixed `UsdPhysics.Joint` that applies `MjcJointAPI`, or one `MjcTendon` whose `mjc:path` targets valid `MjcJointAPI` joints.
* For mimic / equality-coupled follower joints, apply `["MjcJointAPI", "NewtonMimicAPI", "MjcEqualityJointAPI"]` on the follower joint with `rel newton:mimicJoint` targeting the leader joint (plus `newton:mimicCoef0`, `newton:mimicCoef1`, `newton:mimicEnabled = 1`, and optional `mjc:solimp` / `mjc:solref`), rather than authoring a competing `MjcActuator` on the follower.
* For closed-loop 4-bar / parallel linkages, set `physics:excludeFromArticulation = 1` on the loop-closing joint and omit `MjcJointAPI` from that excluded joint.
* Keep authored control and force ranges finite and ordered.
* Keep authored gain and bias parameters numeric.

## Related requirements

- [mujoco-joint-api](mujoco-joint-api.md)
- [no-articulation-loops](no-articulation-loops.md)

## For More Information

* MuJoCo USD converter output and actuator authoring conventions.
