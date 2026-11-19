# Requirements

## Summary

- A **UsdPhysicsJoint prim** or one of its subtypes can be used to constrain two rigid bodies together, or to constrain a single rigid body to the World. This is achieved by setting the joint's Body0 and Body1 relationship targets to either two rigid bodies or one to a rigid body and leaving the other one empty.
- Any prim of the USD scene graph hierarchy may be marked with an **UsdPhysicsArticulationRootAPI**. This informs the simulation that any joints found in the subtree should preferentially be simulated using a reduced coordinate approach. 


## Schema / OpenUSD Specification
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->

Joints are created using the following schemas that are part of the core OpenUSD specification.

- [Joints](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
- [Joint Subtypes](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joint_subtypes)

## Requirements

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- PHYSICS_JOINTS_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- PHYSICS_JOINTS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/joint-capability
requirements/joint-body-target-exists
requirements/joint-no-multiple-body-targets
requirements/articulation
requirements/articulation-no-nesting
requirements/articulation-not-on-kinematic-body
requirements/articulation-not-on-static-body
```
