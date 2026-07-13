# Requirements

## Summary

**Collider Approximations** are optimized geometric representations used to improve collision detection performance in physics simulations. Complex mesh geometries are converted into simplified representations such as Signed Distance Fields (SDF), convex hulls, bounding boxes, or simplified meshes that maintain sufficient accuracy while dramatically reducing computational overhead.

Collider approximations are typically authored as separate USD prims with PhysicsCollisionAPI applied and are referenced by mesh colliders using the physics:approximation relationship. The main types of approximations include:
- **SDF (Signed Distance Fields)**: 3D distance field representations for complex geometries
- **Convex Hulls**: Simplified convex representations of concave meshes
- **Bounding Boxes**: Axis-aligned or oriented bounding box approximations
- **Simplified Meshes**: Reduced polygon count versions of original meshes

## Schema / OpenUSD Specification
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->

Collider approximations are created using the following schemas that are part of the core OpenUSD specification.

- [UsdPhysicsCollisionAPI Documentation](https://openusd.org/dev/api/class_usd_physics_collision_a_p_i.html)
- [UsdPhysicsApproximationAPI Documentation](https://openusd.org/release/api/class_usd_physics_approximation_a_p_i.html)
- [OpenUSD Physics Collision](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)

## Requirements

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- COLLIDER_APPROXIMATIONS_REQUIREMENTS_LIST_START -->
<!-- COLLIDER_APPROXIMATIONS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/collider-approximation-sdf
```