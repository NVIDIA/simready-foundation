# collider-material-binding

| Code     | PMT.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every collider (prim with PhysicsCollisionAPI) must have a material:binding:physics relationship to a physics material.

## Description

Physics materials define the surface properties that affect collision behavior, including friction, restitution, and density. For proper physics simulation, every collider must be bound to a physics material through the `material:binding:physics` relationship.

The material:binding:physics relationship connects a collider prim (with PhysicsCollisionAPI) to a physics material prim (with PhysicsMaterialAPI), enabling the simulation engine to apply the correct material properties during collision detection and response.


## Examples

```usd
# Invalid: Collider without physics material binding
def Cube "MyCube" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
   double size = 1.0
   # Missing material:binding:physics relationship
}

# Valid: Collider with physics material binding
def Cube "MyCube" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
   double size = 1.0
   rel material:binding:physics = </Materials/Metal>
}

def Material "Metal" (
   prepend apiSchemas = ["PhysicsMaterialAPI"]
) {
   float physics:density = 2700
   float physics:dynamicFriction = 0.1
   float physics:restitution = 0.1
   float physics:staticFriction = 0.1
}
```

## How to comply

1. Ensure every prim with PhysicsCollisionAPI has a `material:binding:physics` relationship
2. The relationship must target a valid physics material prim (with PhysicsMaterialAPI)
3. Physics materials should have appropriate values for density, friction, and restitution
4. Use meaningful material names that reflect the intended physical properties

## For More Information

- [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
- [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)
- [UsdPhysicsMaterialAPI Documentation](https://openusd.org/dev/api/class_usd_physics_material_a_p_i.html)
- [USD Material Binding](https://openusd.org/release/api/class_usd_shade_material_binding_a_p_i.html) 