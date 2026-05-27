# Feature: `ID:024 - Base - Articulation`

## Description

Base articulation requirements for assets with articulated physics bodies.

## Dependency Graph

```{mermaid}
flowchart LR
    FET024N["FET024_BASE_ARTICULATION_NEUTRAL\n0.1.0"]
    FET024P["FET024_BASE_ARTICULATION_PHYSX\n0.1.0"]

    FET024P --> FET024N

    classDef current fill:#90EE90,stroke:#333
    class FET024N,FET024P current
```

## Neutral Format

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET024_BASE_ARTICULATION_NEUTRAL`|

#### Used in Profiles

#### Requirements 

* Capability: [BaseArticulation/Core](../capabilities/physics_bodies/base_articulation/requirements.md)
  * Requirements:
    * [HasArticulationRoot](../capabilities/physics_bodies/base_articulation/requirements/has-articulation-root.md)

</details>

## PhysX Format

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET024_BASE_ARTICULATION_PHYSX`|

#### Used in Profiles

#### Requirements 

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [ID:024 - Base - Articulation - Neutral Format - v0.1.0](../features/FET_024-base_articulation.md#version-010) |

* Capability: [BaseArticulation/PhysX_Configuration]
  * Requirements:
    * [NonAdjacentCollisionMeshesDoNotClash](../capabilities/physics_bodies/base_articulation/requirements/non-adjacent-collision-meshes-do-not-clash.md)

</details>

