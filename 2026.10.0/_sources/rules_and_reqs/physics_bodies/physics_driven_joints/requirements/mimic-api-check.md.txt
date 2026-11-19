# mimic-api-check

| Code     | DJ.007 |
|----------|--------|
| Validator| CheckPrim |
| Compatibility | {compatibility}`PhysX` |
| Tags     | {tag}`essential` |

## Summary

Mimic API configuration must be properly validated for coordinated joint motion.

## Description

When using mimic joints, the mimic relationship, multiplier, and offset values must be properly configured and validated. The mimic joint must reference a valid master joint and the relationship must not create circular dependencies.

Additional checks:

- The `PhysxMimicJointAPI` instance name must be a known mimic axis: `rotX`/`rotY`/`rotZ` (revolute), `transX`/`transY`/`transZ` (prismatic), or the short `X`/`Y`/`Z` spelling
- Exactly one resolved reference joint target must be set. USD relationship
  forwarding is supported; empty, cyclic, or unresolved forwarding chains do
  not establish a valid reference, and multiple resolved joints are invalid.
- A prismatic/revolute joint cannot reference its own joint DOF
- Gearing must be finite and non-zero; offset must be finite (the schema default is zero). A blocked offset is unavailable, not zero.
- `naturalFrequency` and `dampingRatio` must resolve to finite numeric values; their schema defaults of zero are valid. `naturalFrequency <= 0` selects a rigid constraint without compliance. Positive natural frequency and damping ratio select a compliant spring-damper; `dampingRatio <= 0` also selects a rigid constraint (zero damping is reported as info). Blocked or malformed values are invalid.
- Both self and reference joints must have ordered, non-NaN limits. Unlimited lower/upper endpoints may use negative/positive infinity respectively; a range must still permit a finite joint position.
- PhysX uses `follower + gearing * reference + offset = 0`. Map both reference endpoints with `follower = -gearing * reference - offset` and sort them. The complete mapped interval must fit within the follower's limits; equality at either boundary is valid.
- Neither the mimic joint nor the reference joint may be excluded from articulation (`physics:excludeFromArticulation` must not be true on either)

Boundary comparisons account only for USD float-precision arithmetic roundoff,
including gearing/offset cancellation; no physical travel margin is added.
The checker detects single-DOF self-reference. Review general graph acyclicity
separately; an acyclic chain is not invalid merely because the reference joint
also has a mimic API.

## Why is it required?

* To ensure proper coordinated motion between joints
* To prevent circular dependencies in mimic relationships
* To validate mimic parameters are within acceptable ranges
* To ensure mimic and reference joints participate in the articulation (neither excluded)

## Examples

```usd
# Valid: Revolute mimic joint configuration
def PhysicsRevoluteJoint "ref_joint"
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    uniform token physics:axis = "Y"
}

def PhysicsRevoluteJoint "mimic_joint" (
    prepend apiSchemas = ["PhysxMimicJointAPI:rotZ"]
)
{
    uniform token physics:axis = "Z"
    rel physics:body0 = </link_2>
    rel physics:body1 = </link_3>
    
    # Valid mimic relationship
    float physxMimicJoint:rotZ:dampingRatio = 0 # must exist
    float physxMimicJoint:rotZ:gearing = -1 # has to be a non zero real number
    float physxMimicJoint:rotZ:naturalFrequency = 0 # rigid coupling; also the schema default
    rel physxMimicJoint:rotZ:referenceJoint = </ref_joint> # valid joint target; review graph acyclicity separately
}

# Valid: Prismatic mimic (parallel-jaw / rack coupling).
# Instance name may be transX/transY/transZ or the short X/Y/Z spelling.
def PhysicsPrismaticJoint "finger_left"
{
    rel physics:body0 = </base>
    rel physics:body1 = </left>
    uniform token physics:axis = "Z"
    float physics:lowerLimit = 0
    float physics:upperLimit = 0.05
}

def PhysicsPrismaticJoint "finger_right" (
    prepend apiSchemas = ["PhysxMimicJointAPI:Z"]
)
{
    rel physics:body0 = </base>
    rel physics:body1 = </right>
    uniform token physics:axis = "Z"
    float physics:lowerLimit = 0
    float physics:upperLimit = 0.05
    float physxMimicJoint:Z:dampingRatio = 0
    float physxMimicJoint:Z:gearing = -1
    float physxMimicJoint:Z:naturalFrequency = 0 # rigid coupling; may be omitted to use the schema default
    rel physxMimicJoint:Z:referenceJoint = </finger_left>
}

# Invalid: Reference or mimic excluded from articulation
# Neither the mimic joint nor its reference joint may have physics:excludeFromArticulation = true

def PhysicsRevoluteJoint "ref_joint"
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    bool physics:excludeFromArticulation = 1  # invalid: reference joint excluded
}

def PhysicsRevoluteJoint "mimic_joint" (
    prepend apiSchemas = ["PhysxMimicJointAPI:rotZ"]
)
{
    rel physics:body0 = </link_2>
    rel physics:body1 = </link_3>
    rel physxMimicJoint:rotZ:referenceJoint = </ref_joint>
    # Invalid: if mimic_joint had physics:excludeFromArticulation = 1, that would also fail
}

# Invalid: Circular dependency
# ref_joint cannot mimic mimic_joint if mimic_joint mimics ref_joint

def PhysicsRevoluteJoint "ref_joint" (
    prepend apiSchemas = ["PhysxMimicJointAPI:rotZ"]
)
{
    rel physics:body0 = </link_0>
    rel physics:body1 = </link_1>
    rel physxMimicJoint:rotZ:referenceJoint = </mimic_joint> # invalid: completes the circular dependency shown above; review manually
}

```

## How to comply

* Apply `PhysxMimicJointAPI` with a known axis instance: `rotX`/`rotY`/`rotZ`, `transX`/`transY`/`transZ`, or short `X`/`Y`/`Z`
* Ensure mimic joint references exist and are valid
* Verify no circular dependencies in mimic relationships  
* Set reasonable multiplier and offset values
* Preserve zero/default or negative natural frequency for rigid coupling. For compliant coupling, use positive finite natural frequency and damping ratio appropriate to the mechanism.
* Validate mimic joint hierarchy is acyclic
* Do not set `physics:excludeFromArticulation` on the mimic joint or its reference joint

## Related requirements

- [physics-joint-has-drive-or-mimic-api](physics-joint-has-drive-or-mimic-api.md)
- [drive-joint-value-reasonable](drive-joint-value-reasonable.md)

## For More Information

* [PhysX Mimic Joint Documentation](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_physx_mimic_joint_a_p_i.html)
* [PhysX Mimic Joint Compliance](https://nvidia-omniverse.github.io/PhysX/physx/latest/_api_build/classPxArticulationReducedCoordinate.html#class_px_articulation_reduced_coordinate)
* [USD Physics Joint Relationships](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
