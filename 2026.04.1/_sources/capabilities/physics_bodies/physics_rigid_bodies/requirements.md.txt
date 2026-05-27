# Requirements

## Summary

- **The rigid body schema** must be applied to any xformable prim that represent a rigid physical object
- Colliding Gprims need to have the **Collision API** applied
- Each rigid body or it's descendant colliders, should have the **mass API** applied.

## Granularity

If joints are not present, each rigid body will be simulated as a free body. Only create multiple rigid bodies in an asset if they are either connected by joints or if they are intended to be simulated without being connected to each other.


<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->
## Schema / OpenUSD Specification

Rigid Body Physics are applied using the following two schemas that are part of the core OpenUSD specification.

- [USD Rigid Bodies](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [USD Physics Collision Shapes](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_collision_shapes)

### USDA Sample

```usd
(
    kilogramsPerUnit = 1
)

def Xform "RobotHead" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
    ) {

    physics:mass = 10.0

    def Mesh "Head" (
        prepend apiSchemas = ["PhysicsCollisionAPI"]
    ) {
        # ...
    }

    def Mesh "Jaw" (
        prepend apiSchemas = ["PhysicsCollisionAPI"]
    ) {
        # ...
    }
}

def Mesh "GroundPlane" (
    prepend apiSchemas = ["PhysicsCollisionAPI"]
) {}

```

## Requirements

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- PHYSICS_RIGID_BODIES_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- PHYSICS_RIGID_BODIES_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/collider-capability
requirements/physx-collider-capability
requirements/physx-collider-mesh
requirements/collider-mesh
requirements/collider-non-uniform-scale
requirements/rigid-body-capability
requirements/rigid-body-mass
requirements/rigid-body-multibody-capability
requirements/rigid-body-detailed-mass
requirements/rigid-body-no-nesting
requirements/nested-rigid-body-mass
requirements/rigid-body-no-nesting-without-joint
requirements/rigid-body-no-instancing
requirements/rigid-body-schema-application
requirements/rigid-body-schema-no-skew-matrix
requirements/mesh-collision-api
requirements/invisible-collision-mesh-has-purpose-guide
```
