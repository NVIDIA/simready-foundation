# Requirements

## Summary

A **UsdPhysicsMaterial** is a schema in OpenUSD used to define the physical properties of a material, such as density, friction, and restitution. These properties affect how objects interact during simulation, including how they collide, slide, and bounce.  Physics materials are typically authored as USD Material prims with the PhysicsMaterialAPI applied. They are then bound to collision shapes (prims with PhysicsCollisionAPI) using the material:binding:physics relationship.  The main attributes of a physics material are: 
- physics:density: The mass per unit volume of the material.
- physics:staticFriction: The friction coefficient when objects are at rest.
- physics:dynamicFriction: The friction coefficient when objects are moving.
- physics:restitution: The bounciness of the material (0 = inelastic, 1 = perfectly elastic).


## Schema / OpenUSD Specification
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->

Joints are created using the following schemas that are part of the core OpenUSD specification.

- [UsdPhysicsMaterialAPI Documentation](https://openusd.org/dev/api/class_usd_physics_material_a_p_i.html)
- [OpenUSD Physics Materials](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_materials)



## Requirements

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- PHYSICS_MATERIALS_REQUIREMENTS_LIST_START -->
<!-- PHYSICS_MATERIALS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/collider-material-binding
```
