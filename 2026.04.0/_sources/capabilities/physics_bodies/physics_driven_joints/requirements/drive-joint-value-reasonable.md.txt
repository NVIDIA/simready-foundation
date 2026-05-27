# drive-joint-value-reasonable

| Code     | DJ.006 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

Drive joint parameters must be within reasonable ranges for stable simulation. The joint parameters should not be excessively big and should be natural numbers.

## Description

Joint drive parameters including stiffness, damping, target positions, and forces must be configured within reasonable ranges to ensure simulation stability and realistic behavior. Values that are too extreme can cause instability or unrealistic motion.

## Why is it required?

* To ensure simulation stability and convergence
* To provide realistic joint behavior
* To prevent numerical issues and simulation artifacts

## Examples

```usd
# Valid: Reasonable drive parameters
def PhysicsRevoluteJoint "RevoluteJoint" (
    prepend apiSchemas = ["PhysicsDriveAPI"]
)
{
    rel physics:body0 = </Base>
    rel physics:body1 = </Arm>
    uniform token physics:axis = "Y"
    
    float drive:angular:physics:stiffness = 1000.0  # Reasonable stiffness (not too high)
    float drive:angular:physics:damping = 10.0 # Reasonable damping (provides stability)
}

# Invalid: Extreme values that can cause instability
# float drive:angular:physics:stiffness = 1000000.0  # Too high
# float drive:angular:physics:damping = 0.0          # No damping
```

## How to comply

* Use appropriate stiffness values (typically 100-10000)
* Include sufficient damping for stability (typically 1-100)
* Set realistic target positions within joint limits
* Configure reasonable maximum force limits

For mimic joints:

* Enforce drive stiffness == 0.0 and drive damping == 0.0

## Related requirements

- [physics-joint-has-drive-or-mimic-api](physics-joint-has-drive-or-mimic-api.md)
- [physics-joint-max-velocity](physics-joint-max-velocity.md)

## For More Information

* [PhysX Drive Tuning Guide](https://docs.nvidia.com/gameworks/content/gameworkslibrary/physx/guide/Manual/Joints.html)
* [USD Physics Drive Parameters](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joint_drive)
