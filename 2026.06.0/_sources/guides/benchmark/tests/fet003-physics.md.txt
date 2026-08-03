# FET003 Physics

Rigid-body dynamics: the asset falls, collides, and settles like a solid object.

## Overview

This family drops the asset onto flat and tilted ground, then confirms it falls under gravity, collides with the surface, and comes to rest without sinking, exploding, or jittering. The tests exercise both the collision mesh and the mass and inertia properties of the asset to ensure physically reasonable behavior in a dynamics scene.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the asset has a correctly authored collider and physically reasonable mass properties. The asset will behave as a stable rigid body when placed in any physics-enabled scene: it falls predictably, lands without tunneling through surfaces, and settles without oscillating indefinitely.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [ground_drop](fet003/ground-drop.md)
  - Drops the asset onto a flat floor, confirms ground contact, confirms the asset does not tunnel through the surface, and confirms the asset comes to rest.
  - FET003_BASE_PHYSX
* - [slope_drop](fet003/slope-drop.md)
  - Places the asset on a 45-degree inclined plane and confirms it slides and does not tunnel through the surface.
  - FET003_BASE_PHYSX
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET003 Rigid Body Physics](../../../features/FET_003-rigid_body_physics.md).

```{toctree}
:maxdepth: 1
:hidden:

ground_drop <fet003/ground-drop>
slope_drop <fet003/slope-drop>
```
