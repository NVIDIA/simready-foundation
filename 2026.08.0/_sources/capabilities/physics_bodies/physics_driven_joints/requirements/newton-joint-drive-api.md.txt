# Newton Joint Drive API

| Code     | NEWTON.DJ.001 |
|----------|---------------|
| Validator| NewtonJointDriveAPIChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

Every actuated Newton articulation joint must be driven by a standard `UsdPhysics.DriveAPI`, by a `NewtonActuator`, or be coupled to a leader joint by `NewtonMimicAPI`, and those actuation values must be valid.

## Description

Newton imports standard `UsdPhysics.Joint` prims and resolves their actuation into Newton
joint degree-of-freedom configuration. Actuation may be authored in any of three ways:

- a standard `PhysicsDriveAPI:<axis>` schema on the joint,
- a `NewtonActuator` prim whose `newton:targets` relationship points at the joint, or
- a `NewtonMimicAPI` coupling that slaves the joint to a leader joint via `newton:mimicJoint`.

For every non-fixed joint that participates in an articulation, unless
`physics:excludeFromArticulation = true`, at least one of those actuation forms must be
present.

A `NewtonMimicAPI` follower is actuated indirectly: the mimic constraint ties its DOF to
its leader joint, so the leader's drive (or actuator) moves the follower without the
follower needing its own drive. This matches the Standard/PhysX "drive or mimic" contract
([physics-joint-has-drive-or-mimic-api](physics-joint-has-drive-or-mimic-api.md), `DJ.004`)
and avoids authoring an inert placeholder drive purely to satisfy the check. The mimic
coupling is only accepted when it is enabled (`newton:mimicEnabled` is on unless explicitly
authored `false`) and authors a `newton:mimicJoint` leader target; the coupling itself is
validated by [newton-mimic-api](newton-mimic-api.md) (`NEWTON.DJ.003`).

For standard drives:

- each applied `PhysicsDriveAPI:<axis>` must author `drive:<axis>:physics:maxForce`
- max force must be finite and greater than zero
- authored drive stiffness and damping values must be finite and non-negative
- authored drive target position and target velocity values must be finite

For a `NewtonActuator`:

- `newton:targets` must be authored and its first target must be a
  `PhysicsRevoluteJoint` or `PhysicsPrismaticJoint`
- exactly one control-law API must be applied
  (`NewtonPDControlAPI`, `NewtonPIDControlAPI`, or `NewtonNeuralControlAPI`)
- authored control gains (`newton:kp`, `newton:kd`, `newton:ki`, `newton:integralMax`)
  and effort clamps (`newton:maxEffort`, `newton:maxMotorEffort`, `newton:saturationEffort`)
  must be finite and non-negative; `newton:constEffort` must be finite
- `newton:delaySteps` must be a non-negative integer when authored

`NewtonActuator` uses radians (diverging from `UsdPhysicsDriveAPI`, which uses degrees).
Newton joint tuning attributes such as `newton:armature` are validated by
[newton-joint-attributes](newton-joint-attributes.md).

## Why is it required?

* Ensures Newton can import each actuated articulation joint with an explicit drive or actuator.
* Supports both the standard-drive authoring path and the published `NewtonActuator` schema family.
* Keeps effort, gain, position, and velocity values bounded for predictable Newton import.

## Examples

```usd
# Valid: Newton revolute joint driven by a standard angular drive.
def PhysicsRevoluteJoint "elbow" (
    prepend apiSchemas = ["PhysicsDriveAPI:angular"]
)
{
    rel physics:body0 = </robot/upper_arm>
    rel physics:body1 = </robot/lower_arm>
    uniform token physics:axis = "Z"
    float drive:angular:physics:maxForce = 25.0
    float drive:angular:physics:stiffness = 100.0
    float drive:angular:physics:damping = 5.0
}

# Valid: the joint is driven by a NewtonActuator with a PD control law.
def PhysicsRevoluteJoint "elbow2" (
)
{
    rel physics:body0 = </robot/upper_arm>
    rel physics:body1 = </robot/lower_arm>
    uniform token physics:axis = "Z"
}
def NewtonActuator "elbow2_actuator" (
    prepend apiSchemas = ["NewtonPDControlAPI", "NewtonMaxEffortClampingAPI"]
)
{
    rel newton:targets = </robot/upper_arm/elbow2>
    float newton:kp = 2000.0
    float newton:kd = 400.0
    float newton:maxEffort = 150.0
}

# Valid: the follower is coupled to its leader by NewtonMimicAPI, so it needs
# no drive of its own -- the leader's actuation moves it through the coupling.
def PhysicsRevoluteJoint "follower" (
    prepend apiSchemas = ["NewtonMimicAPI"]
)
{
    rel physics:body0 = </robot/upper_arm>
    rel physics:body1 = </robot/lower_arm>
    uniform token physics:axis = "Z"
    rel newton:mimicJoint = </robot/upper_arm/elbow>
    float newton:mimicCoef0 = 0
    float newton:mimicCoef1 = 1
    bool newton:mimicEnabled = 1
}

# Invalid: active Newton joint has neither a drive, a NewtonActuator, nor a
# NewtonMimicAPI coupling.
def PhysicsRevoluteJoint "bad_elbow" (
)
{
    rel physics:body0 = </robot/upper_arm>
    rel physics:body1 = </robot/lower_arm>
    uniform token physics:axis = "Z"
}
```

## How to comply

* Drive each non-fixed articulation joint with a `PhysicsDriveAPI:<axis>` schema, a
  `NewtonActuator` that targets it, or a `NewtonMimicAPI` coupling to a leader joint.
* For mimic followers, author `newton:mimicJoint` (leader), keep `newton:mimicEnabled` on,
  and do not add a placeholder drive just to pass this check.
* For standard drives, author finite, positive `drive:<axis>:physics:maxForce` and use
  non-negative finite stiffness and damping.
* For actuators, author `newton:targets`, apply exactly one control-law API, and keep gains,
  clamps, and delay values in the valid ranges above.
* If a joint is not part of the articulation, explicitly set `physics:excludeFromArticulation = true`.

## Related requirements

- [newton-joint-attributes](newton-joint-attributes.md)
- [no-articulation-loops](no-articulation-loops.md)

## For More Information

* [OpenUSD PhysicsDriveAPI Schema](https://openusd.org/dev/api/class_usd_physics_drive_a_p_i.html)
* [Newton USD Parsing and Schema Resolver System](https://github.com/newton-physics/newton/blob/main/docs/concepts/usd_parsing.rst)
* [Newton USD Schema Definitions (NewtonActuator)](https://github.com/newton-physics/newton-usd-schemas)
