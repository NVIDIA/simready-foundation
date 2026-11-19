# Capability: `CAP024_BaseArticulation.PhysX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP024_BaseArticulation.PhysX` |
| Runtime                 | `PhysX` |
| Proprietary Techs       | `PhysX` |
| Versions                | `0-1-0` |

## Description

Defines the PhysX base-articulation contract. It depends on Standard articulation root authoring and adds PhysX evidence that non-adjacent collision meshes do not clash.

## Dependency Graph

```{mermaid}
flowchart LR
    FET_024_PHYSX_0_1_0["CAP024_BaseArticulation.PhysX\n0-1-0"]
    FET_024_STANDARD_0_1_0["CAP024_BaseArticulation\n0-1-0"]
    FET_024_PHYSX_0_1_0 --> FET_024_STANDARD_0_1_0

    classDef current fill:#90EE90,stroke:#333
```

## Use Cases

Products or workflows that consume this capability:

- SimReady validation verifies CAP024_BaseArticulation.PhysX requirements.
- `simready-foundation-conform-fet-024-physx` repairs root placement and records PhysX clearance limitations.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`

#### Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | `CAP024_BaseArticulation.0-1-0` |

#### Requirement List

* Capability: [Physics Bodies/Base Articulation](../rules_and_reqs/physics_bodies/base_articulation/capability-base-articulation.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `BA.002` | [BA.002](../rules_and_reqs/physics_bodies/base_articulation/requirements/non-adjacent-collision-meshes-do-not-clash.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies CAP024_BaseArticulation.PhysX requirements.
- `simready-foundation-conform-fet-024-physx` repairs root placement and records PhysX clearance limitations.

## Samples

- [`ur10` PhysX robot](../../../../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Evaluates

- None.

## Adapters

None.
