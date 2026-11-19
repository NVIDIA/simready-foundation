# Capability: `CAP023_RobotMaterials.Isaac`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP023_RobotMaterials.Isaac` |
| Runtime                 | `Isaac` |
| Proprietary Techs       | `Isaac Sim` |
| Versions                | `0-1-0` |

:::{warning}
`CAP023_RobotMaterials.Isaac` is deprecated. It is retained so assets that conform to it,
and `Robot-Body` `2.0.0` through `3.1.0`, which select it as optional, keep validating
against it. `Robot-Body` `4.0.0` does not select it. Do not add it to new profile versions.
:::

## Description

Defines the Isaac robot-material organization contract. Materials must be direct children of the top-level Looks scope and must not contain nested material hierarchies.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this capability:

- SimReady validation verifies CAP023_RobotMaterials.Isaac robot-material organization.
- `simready-foundation-conform-fet-023-isaac` repairs it for compatibility, and leaves
  materials inside instanced parts where they are.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`, `3.1.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Isaac Sim/Robot Materials](../rules_and_reqs/isaac_sim/robot_materials/capability-robot_materials.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `RM.001` | [RM.001](../rules_and_reqs/isaac_sim/robot_materials/requirements/no-nested-materials.md) |
| `RM.002` | [RM.002](../rules_and_reqs/isaac_sim/robot_materials/requirements/materials-on-top-level-only.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies CAP023_RobotMaterials.Isaac robot-material organization.
- `simready-foundation-conform-fet-023-isaac` repairs it for compatibility, and leaves
  materials inside instanced parts where they are.

## Samples

- None.

## Evaluates

- None.

## Adapters

None.
