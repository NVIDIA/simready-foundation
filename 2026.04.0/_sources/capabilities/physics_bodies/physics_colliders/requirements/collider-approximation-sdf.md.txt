# collider-approximation-sdf

| Code     | COL.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Every mesh collider (Mesh prim with USDPhysics.CollisionAPI and USDPhysics.MeshCollisionAPI) must have an SDF (Signed Distance Field) approximation for efficient collision detection.

## Description

SDF approximations provide optimized collision detection for complex mesh geometries by converting detailed mesh surfaces into efficient distance field representations. For proper physics simulation performance, every mesh collider must have an SDF approximation that accurately represents the original geometry while enabling fast collision queries.

The SDF approximation allows the physics engine to perform rapid collision detection without the computational overhead of detailed mesh-mesh intersection tests, while maintaining sufficient accuracy for realistic physics behavior.

## Examples

```usd
# Invalid: Mesh collider without SDF approximation
def Mesh "MyMesh" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
   # Missing physics:approximation
   # Collision detection will be inefficient or unavailable
}

# Valid: Mesh collider with SDF approximation
def Mesh "MyMeshSDF" (
   prepend apiSchemas = ["PhysicsCollisionAPI"]
) {
   # SDF approximation properties
   token physics:approximation = "sdf"
   float3[] physics:sdfResolution = [64, 64, 64]
}
```

## How to comply

1. Ensure every mesh prim with PhysicsCollisionAPI has a physics:approximation  attribute
2. The approximation must target a valid SDF collider with appropriate resolution and bounds
3. SDF data should accurately represent the original mesh geometry
4. Use appropriate resolution settings based on mesh complexity and performance requirements
5. Ensure SDF bounds properly encompass the original mesh geometry

## For More Information

- [UsdPhysics Collision Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)
- [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)
- [SDF Collision Detection](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_sdf_collision)
- [USD Physics Approximation](https://openusd.org/release/api/class_usd_physics_approximation_a_p_i.html)