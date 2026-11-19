# Feature: `FET028_Gripper`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET028_Gripper` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Defines the Standard gripper-site contract: socket type, forward approach axis, grip-line axis, and maximum opening for a gripper end-effector.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies FET028_Gripper gripper-site requirements.
- FET028 evaluation phases consume the authored gripper-site data.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Physics Bodies/Physics Grippers](../rules_and_reqs/physics_bodies/physics_grippers/capability-physics_grippers.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `GR.001` | [GR.001](../rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-socket-type.md) |
| `GR.002` | [GR.002](../rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-forward-axis.md) |
| `GR.003` | [GR.003](../rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-grip-line.md) |
| `GR.004` | [GR.004](../rules_and_reqs/physics_bodies/physics_grippers/requirements/gripper-max-opening.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies FET028_Gripper gripper-site requirements.
- FET028 evaluation phases consume the authored gripper-site data.

## Samples

- [`Robotiq 2F-85` gripper](../../../../../../../sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/2F-85.usda)

## Evaluates

- FET028 gripper close-and-lift evaluation suite

## Adapters

None.
