# Newton Joint Attributes

| Code     | NEWTON.DJ.002 |
|----------|---------------|
| Validator| NewtonJointAttributesChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

Authored Newton joint tuning must use `NewtonJointAPI` (or the equivalent `newton:*` attributes) on `UsdPhysics.Joint` prims with valid values.

## Description

The published Newton USD schemas define `NewtonJointAPI`, which applies on top of a
`UsdPhysics.Joint` and provides solver behavior, passive dynamics, and limit-spring
response. All scalar attributes broadcast uniformly to every degree of freedom of the
joint (angular attributes use degrees). Newton's USD resolver also accepts the same
`newton:*` attributes authored directly on a joint prim without the applied schema, so
both forms are valid.

When Newton joint tuning is authored:

- it must be authored on a prim that is a `UsdPhysics.Joint`
- `NewtonJointAPI` may be applied on that joint (it is the canonical form)
- `newton:armature`, `newton:damping`, and `newton:friction` must be finite and non-negative
- `newton:velocityLimit` must be positive; the value `inf` (no clamping) is allowed
- `newton:limitStiffness` and `newton:limitDamping` must be finite and non-negative when
  authored, except for the sentinel `-inf`, which defers to the engine default;
  `newton:limitStiffness` may also be `inf` to request a hard limit

These are the broadcast `NewtonJointAPI` attribute names. Actuation itself
(a `PhysicsDriveAPI:<axis>` drive or a `NewtonActuator`) is covered by
[newton-joint-drive-api](newton-joint-drive-api.md); this requirement only validates the
Newton joint tuning attributes.

## Why is it required?

* Keeps Newton-specific joint tuning aligned with the published `NewtonJointAPI` schema.
* Ensures Newton joint tuning is authored on real USD physics joints.
* Catches invalid numeric values before Newton import.

## Examples

```usd
# Valid: NewtonJointAPI with broadcast tuning on a standard USD joint.
def PhysicsRevoluteJoint "shoulder" (
    prepend apiSchemas = ["PhysicsDriveAPI:angular", "NewtonJointAPI"]
)
{
    rel physics:body0 = </robot/base>
    rel physics:body1 = </robot/arm>
    float newton:armature = 0.1
    float newton:damping = 0.0
    float newton:friction = 0.0
    float newton:limitStiffness = 1000.0
    float newton:limitDamping = 10.0
}

# Valid: the same tuning authored as bare newton:* resolver attributes (no applied API).
def PhysicsRevoluteJoint "shoulder_alt" (
    prepend apiSchemas = ["PhysicsDriveAPI:angular"]
)
{
    float newton:armature = 0.1
}

# Invalid: negative armature.
def PhysicsRevoluteJoint "bad_shoulder" (
    prepend apiSchemas = ["NewtonJointAPI"]
)
{
    float newton:armature = -0.1
}

# Invalid: Newton joint tuning authored on a non-joint prim.
def Xform "not_a_joint" (
    prepend apiSchemas = ["NewtonJointAPI"]
)
{
    float newton:armature = 0.1
}
```

## How to comply

* Apply `NewtonJointAPI` (or author the documented `newton:*` attributes) only on
  `UsdPhysics.Joint` prims.
* Keep `newton:armature`, `newton:damping`, and `newton:friction` finite and non-negative.
* Keep `newton:velocityLimit` positive (or `inf`).
* Keep `newton:limitStiffness` and `newton:limitDamping` finite and non-negative when
  authored, or leave them at the `-inf` sentinel to use the engine default.

## For More Information

* [Newton USD Parsing and Schema Resolver System](https://github.com/newton-physics/newton/blob/main/docs/concepts/usd_parsing.rst)
* [Newton USD Schema Definitions (NewtonJointAPI)](https://github.com/newton-physics/newton-usd-schemas)
