# Feature: `FET_023_ISAAC`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_023_ISAAC` |
| Runtime | `ISAAC` |
| Proprietary Techs | `Isaac Sim` |
| Latest Version | `0.1.0` |

## Description

Defines the Isaac robot-material organization contract. Materials must be direct children of the top-level Looks scope and must not contain nested material hierarchies.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies FET_023_ISAAC robot-material organization.
- `simready-foundation-conform-fet-023-isaac` repairs material hierarchy organization.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- **[Robot Body Profile](../profiles/robot-body.md)** (`v2.0.0`) - Optional Isaac robot-material organization gate.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Isaac Sim/Robot Materials](../capabilities/isaac_sim/robot_materials/capability-robot_materials.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `RM.001` | [RM.001](../capabilities/isaac_sim/robot_materials/requirements/no-nested-materials.md) | [Implementation](../capabilities/isaac_sim/robot_materials/validation.py) |
| `RM.002` | [RM.002](../capabilities/isaac_sim/robot_materials/requirements/materials-on-top-level-only.md) | [Implementation](../capabilities/isaac_sim/robot_materials/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies FET_023_ISAAC robot-material organization.
- `simready-foundation-conform-fet-023-isaac` repairs material hierarchy organization.

## Samples

- None.

## Benchmarks

- None.

## Adapters

None.
