# newton-mimic-api

| Code     | NEWTON.DJ.003 |
|----------|---------------|
| Validator| NewtonMimicAPIChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

When `NewtonMimicAPI` is applied, it must be on a `UsdPhysics.Joint`, target a valid leader joint,
and author valid mimic coefficients.

## Description

`NewtonMimicAPI` couples one joint (the follower) to another (the leader) so the follower's DOF
tracks the leader according to `joint0 = coef0 + coef1 * joint1`. It is the Newton analog of the
PhysX mimic-joint API and is typically used for coupled mechanisms such as parallel-jaw grippers.

When `NewtonMimicAPI` is applied:

- the prim must be a `UsdPhysics.Joint`
- `newton:mimicJoint` must be authored and target exactly one valid `UsdPhysics.Joint` (the
  leader), and must not target the follower itself
- `newton:mimicCoef0` and `newton:mimicCoef1`, when authored, must be finite
- `newton:mimicEnabled`, when authored, must be a boolean

The schema notes that behavior on multi-DOF joints is undefined because the coefficients are
shared across DOFs; author `NewtonMimicAPI` only on single-DOF joints (revolute or prismatic).

## Why is it required?

A mimic constraint with no leader, a self-referencing leader, a non-joint target, or non-finite
coefficients cannot form a valid coupling and will be rejected or produce undefined motion. Keeping
the follower and leader as single-DOF joints ensures the shared coefficients have consistent units.

## Examples

```usd
# Valid: follower mimics a leader revolute joint 1:1.
def PhysicsRevoluteJoint "leader_joint"
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "Z"
}

def PhysicsRevoluteJoint "follower_joint" (
    prepend apiSchemas = ["NewtonMimicAPI"]
)
{
    rel physics:body0 = </link_2>
    rel physics:body1 = </link_3>
    uniform token physics:axis = "Z"
    rel newton:mimicJoint = </leader_joint>
    float newton:mimicCoef0 = 0.0
    float newton:mimicCoef1 = 1.0
}

# Invalid: NewtonMimicAPI with no leader target.
def PhysicsRevoluteJoint "orphan_follower" (
    prepend apiSchemas = ["NewtonMimicAPI"]
)
{
    float newton:mimicCoef1 = 1.0
}
```

## How to comply

- Apply `NewtonMimicAPI` only on single-DOF `UsdPhysics.Joint` prims.
- Author `newton:mimicJoint` pointing at one valid leader joint that is not the follower itself.
- Keep `newton:mimicCoef0` / `newton:mimicCoef1` finite.

## Related requirements

- [mimic-api-check](mimic-api-check.md) (PhysX, DJ.007)
- [newton-joint-drive-api](newton-joint-drive-api.md) (Newton, NEWTON.DJ.001)
- [newton-joint-attributes](newton-joint-attributes.md) (Newton, NEWTON.DJ.002)

## For More Information

- [Newton USD Schema Definitions (NewtonMimicAPI)](https://github.com/newton-physics/newton-usd-schemas)
- [USD Physics Joint Relationships](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
