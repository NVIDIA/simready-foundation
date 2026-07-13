# articulation

| Code     | JT.ART.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`high-quality` |

## Summary

For stable and fast simulations of kinematic chains, an asset should define an articulation.

## Description

In physics simulation, reduced coordinate joints provide a more stable and faster simulation. They model only the allowed motion directly (e.g., the bending of a robot arm at its elbow), instead of describing the full 6 degrees of freedom (position + orientation) and then constraining them with forces.

In OpenUSD, *reduced coordinate joint* simulation is enabled by applying the `UsdPhysics.Articulation` schema.

The schema is either applied to:

- **The root body** of the articulated object (free-floating articulations - such as a wheeled robot).
  - Note: It can also be applied to a direct or indirect parent of the root body.

- **The root joint** which is connected to the world (fixed articulations - such as a robot arm bolted to the floor).
  - Note: It can also be applied to a direct or indirect parent of the root joint.

## Why is it required?

* Reduced coordinate joints provide a more stable and faster simulation.

## Examples

```usd
def Xform "Link1" () {
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
}

def Xform "Link2" () {
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
}

def PhysicsRevoluteJoint "L1_L2"
{
    rel physics:body0 = </Link1>
    rel physics:body1 = </Link2>
}

# Inefficient: No articulation capability on root joint of a fixed articulation
def PhysicsFixedJoint "FloorBolt"
{
    rel physics:body0 = </Link1>
}

# Inefficient: No articulation capability on root joint of a fixed articulation
def PhysicsFixedJoint "FloorBolt" (
    prepend apiSchemas = ["PhysicsArticulationRootAPI"]
)
{
    rel physics:body0 = </Link1>
}
```

```usd

def Xform "wheel" () {
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
}

def PhysicsRevoluteJoint "wheel_body1"
{
    rel physics:body0 = </body1>
    rel physics:body1 = </wheel>
}

# Inefficient: No articulation capability on root joint of a fixed articulation
def Xform "body1" () {
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
}

# Efficient: Articulation capability on root body of a floating articulation
def Xform "body1" () {
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsArticulationRootAPI"]
}

```

## How to comply?

- Apply the `UsdPhysics.Articulation` schema to the root body or root joint of the articulated object.

## For More Information

* [Articulations Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_articulations)
* [UsdPhysicsArticulationRootAPI Documentation](https://openusd.org/dev/api/class_usd_physics_articulation_root_a_p_i.html)


