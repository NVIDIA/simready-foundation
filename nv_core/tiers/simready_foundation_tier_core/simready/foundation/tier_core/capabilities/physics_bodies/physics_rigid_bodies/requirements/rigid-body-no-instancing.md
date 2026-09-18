# rigid-body-no-instancing-f1

| Code     | RB.005 |
|----------|---------|
| Validator| {oav-validator-latest-link}`rb-005` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Rigid bodies cannot be part of a scene graph instance.

## Description

Since UsdPhysicsRigidBodyAPI has to be able to modify the xformOp attributes in simulation, it cannot be part of a scene graph instance (because instanceable prims prohibit changes to their internal prims).

```{note}
The root prim of a rigid body hierarchy can be instanced.
```

## Why is it required?

- Assets with UsdPhysicsRigidBodyAPI define rigid bodies for the simulator. Prims with this API will have their xformOp attributes updated after each simulation step hence they can't be part of a scene graph instance that prohibits changes.

## Examples

```usd
# Invalid: Rigid body part of a scene graph instance
def Xform "Xform"
{
   def Cube "cube" (
      prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
   ) {
   }
}

def Xform "Xform_01" (
   instanceable = true
   references = </World/Xform>
)
{
}

# Valid: Rigid body applied to the scene graph instance, while collision (does not change) is applied to geometry in the scene graph instance
def Xform "Xform"
{
   def Cube "cube" (
      prepend apiSchemas = ["PhysicsCollisionAPI"]
   ) {
   }
}

def Xform "Xform_01" (
   instanceable = true
   references = </World/Xform>
   prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}
```

## How to comply

The UsdPhysicsRigidBodyAPI schema cannot be part of a scene graph instance.

## For More Information

- [UsdPhysics Rigid Body Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [UsdPhysicsRigidBodyAPI Documentation](https://openusd.org/dev/api/class_usd_physics_rigid_body_a_p_i.html)
- [Scene Graph Instancing Documentation](https://openusd.org/dev/api/_usd__page__scenegraph_instancing.html)
