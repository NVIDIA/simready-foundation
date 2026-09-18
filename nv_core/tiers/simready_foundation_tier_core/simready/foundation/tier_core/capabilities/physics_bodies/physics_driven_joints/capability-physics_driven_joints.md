# Physics Driven Joints

This capability enables physics-driven joint simulation for articulated bodies and robotic mechanisms.

## Summary

Physics driven joints provide the ability to simulate articulated mechanisms with controlled motion, enabling realistic robot simulation and complex multi-body dynamics.

## Schema / OpenUSD Specification

Driven joints are created using USD Physics joint schemas with additional drive
APIs and, for runtimes that require them, state or solver-specific attributes.
MuJoCo-driven joints keep the topology in standard `UsdPhysics.Joint` prims and
use `MjcJointAPI` plus `MjcActuator` prims for runtime-specific actuation data.

- [Joints](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
- [Joint Drive APIs](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joint_drive)

## Implementation

{doc}`Full Requirements List <requirements>`

```{toctree}
:maxdepth: 1
:hidden:

requirements
```
