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

- Exactly one reference joint target must be set
- gearing and naturalFrequency must be non-zero; dampingRatio may be zero (info)
- Both self and reference joints must have limits defined
- Limits must satisfy inequalities given the gearing sign
- Neither the mimic joint nor the reference joint may be excluded from articulation (`physics:excludeFromArticulation` must not be true on either)

## Why is it required?

* To ensure proper coordinated motion between joints
* To prevent circular dependencies in mimic relationships
* To validate mimic parameters are within acceptable ranges
* To ensure mimic and reference joints participate in the articulation (neither excluded)

## Examples

```usd
# Valid: Proper mimic joint configuration
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
    float physxMimicJoint:rotZ:naturalFrequency = 100 # has to be a natural number
    rel physxMimicJoint:rotZ:referenceJoint = </ref_joint> # has to point to a joint that does not have a mimic api
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
    rel physxMimicJoint:rotZ:referenceJoint = </mimic_joint> # invalid: points to a joint that has a mimic api
}

```

## How to comply

* Ensure mimic joint references exist and are valid
* Verify no circular dependencies in mimic relationships  
* Set reasonable multiplier and offset values
* Validate mimic joint hierarchy is acyclic
* Do not set `physics:excludeFromArticulation` on the mimic joint or its reference joint

## Related requirements

- [physics-joint-has-drive-or-mimic-api](physics-joint-has-drive-or-mimic-api.md)
- [drive-joint-value-reasonable](drive-joint-value-reasonable.md)

## For More Information

* [PhysX Mimic Joint Documentation](https://openusd.org/dev/api/class_usd_physics_mimic_a_p_i.html)
* [USD Physics Joint Relationships](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
