# fixed-joint-no-mergeable-body-pair

| Code     | OPT.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The asset must contain no two dynamic rigid bodies joined by an unbreakable fixed joint, unless one of them carries `PhysxContactReportAPI`, or contains an `IsaacContactSensor`, `IsaacImuSensor`, `IsaacLightBeamSensor` or `IsaacRaycastSensor` prim, or a prim carrying `IsaacRtxLidarSensorAPI` or `IsaacRtxRadarSensorAPI`.

## Description

A fixed joint removes every relative degree of freedom between two bodies. The
physics engine still receives two bodies and a constraint to solve. This check
identifies redundant body pairs from one composed asset, without a source model
or conversion history. It does not measure solver performance or prove that an
automatic merge can preserve every authored property.

### Eligibility

Two rigid bodies are eligible for merging when:

1. They are distinct, enabled, non-kinematic rigid bodies on the composed stage.
2. They are joined by an active, enabled `PhysicsFixedJoint`.
3. That joint is unbreakable: `physics:breakForce` and `physics:breakTorque`
   are unauthored or infinite. A finite value is authored behaviour, and merging
   would silently delete it.
4. Both ends resolve to a rigid body. A joint with one end unattached anchors to
   the world and is excluded.
5. Neither body needs separate simulation under the exclusions below.

Automatic repair has additional preconditions. The adapter must resolve mass
and inertia and support the required transform and namespace edits. A failed
precondition blocks repair; it does not turn an `OPT.001` failure into a pass.

### When a body must stay separate

A body is **not** eligible, and the assembly is left alone, when it is a
separately simulated endpoint. That is decided by an explicit list, not by
pattern-matching a name:

| Where | Schema |
|---|---|
| applied to the body | `PhysxContactReportAPI` |
| a descendant prim's type | `IsaacContactSensor`, `IsaacImuSensor`, `IsaacLightBeamSensor`, `IsaacRaycastSensor` |
| applied to a descendant | `IsaacRtxLidarSensorAPI`, `IsaacRtxRadarSensorAPI` |

The typed sensors all derive from `IsaacBaseSensor`, but that inheritance is only
queryable where the Isaac schema plugin is registered, and a validator has to
work where it is not. So the types are named rather than resolved.

That holds for the whole requirement: the PhysX and Isaac schemas above are read
as applied-schema tokens and type names, never resolved through their plugins.
An asset satisfying this requirement is consumable by any OpenUSD runtime, which
is what the compatibility tag records; naming PhysX and Isaac schemas here only
identifies the geometry that must be left alone.

Relationships that merely *list* a body are not on this list. A robot's
`isaac:physics:robotLinks` names every link it has, which is membership rather
than a requirement to simulate each one separately; treating it as one would
make every robot ineligible.

These are the supported exclusions. Other reasons to retain separate bodies
need review; do not add a sensor or change joint behavior merely to pass.

## Examples

```usd
# Fails: two dynamic bodies welded by an unbreakable fixed joint.
def PhysicsFixedJoint "cap_joint"
{
    rel physics:body0 = </Asset/Geometry/base>
    rel physics:body1 = </Asset/Geometry/cap>
}
```

```usd
# Passes: the joint is breakable, so it carries authored behaviour a merge
# would destroy.
def PhysicsFixedJoint "cap_joint"
{
    float physics:breakForce = 250.0
    rel physics:body0 = </Asset/Geometry/base>
    rel physics:body1 = </Asset/Geometry/cap>
}
```

```usd
# Passes: the joint anchors to the world, so there is no second body.
def PhysicsFixedJoint "root_anchor"
{
    rel physics:body0 = </Asset/Geometry/base>
}
```

```usd
# Passes: a contact sensor needs the mount as its own simulated body.
over "sensor_mount" (
    prepend apiSchemas = ["PhysxContactReportAPI"]
)
{
}
```

## Why is it required?

- A fixed joint costs a solver constraint per assembly per environment while removing no degree of freedom
- Reading it from the composed stage means the answer does not depend on how the asset was authored, processed, or exported
- Requiring the reason for keeping a body to be authored as data makes it inspectable, rather than resting on a marker that says only "do not touch"

## How to comply

- Run `fixed_joint_rigid_body_merge` on a staged copy, then reopen and validate it.
- Resolve adapter precondition failures before retrying. Mass and inertia
  preservation are checked by adapter tests, not by requiring a second asset
  from the validation user.
- Preserve genuinely breakable joints and separately simulated sensor bodies.
