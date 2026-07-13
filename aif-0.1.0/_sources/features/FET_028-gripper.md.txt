# Feature: `ID:028 - Gripper`

## Description

Gripper Site defines the structured interaction point on a gripper end-effector that robot control systems use to plan and execute grasps. Each site prim encodes three mutually orthogonal axes — a forward approach axis, a graspable-tube axis (`grip_line`, perpendicular to finger motion), and the implied grip motion axis — plus the maximum jaw opening in meters.

---

## Neutral Format
### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**                          |
|-------------------------|------------------------------------|
| Internal ID             | `FET028_GRIPPER_NEUTRAL`           |

#### Used in Profiles

This version is used in the following profiles:

- **[Robot Gripper Neutral Profile](../profiles/robot-gripper-neutral.md)** (v0.1.0) - Defines the grasp-site interaction point for neutral-format gripper end-effectors

#### Requirements

* Capability: [Physics Grippers](../capabilities/physics_bodies/physics_grippers/capability-physics_grippers.md)
    * Requirements:
        * [gripper-socket-type](../capabilities/physics_bodies/physics_grippers/requirements/gripper-socket-type.md)
            * GR.001 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_grippers/validation.py)
        * [gripper-forward-axis](../capabilities/physics_bodies/physics_grippers/requirements/gripper-forward-axis.md)
            * GR.002 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_grippers/validation.py)
        * [gripper-grip-line](../capabilities/physics_bodies/physics_grippers/requirements/gripper-grip-line.md)
            * GR.003 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_grippers/validation.py)
        * [gripper-max-opening](../capabilities/physics_bodies/physics_grippers/requirements/gripper-max-opening.md)
            * GR.004 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_grippers/validation.py)

#### Pipelines Supported for this Feature

None.

#### Test Process

None.

</details>

---

## Isaac Format
### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**                        |
|-------------------------|----------------------------------|
| Internal ID             | `FET028_GRIPPER_ISAAC`           |
| Proprietary Techs       | `Isaac Sim`                      |

#### Used in Profiles

This version is used in the following profiles:

- **[Robot Gripper Isaac Profile](../profiles/robot-gripper-isaac.md)** (v0.1.0) - Defines the grasp-site interaction point for Isaac-format gripper end-effectors

#### Requirements

| **Property**            | **Value**                                                                              |
|-------------------------|----------------------------------------------------------------------------------------|
| Dependency              | [ID:028 - Gripper - Neutral Format - v0.1.0](#neutral-format) (FET028_GRIPPER_NEUTRAL) |

All Neutral Format requirements apply, plus:

* Capability: [Physics Grippers](../capabilities/physics_bodies/physics_grippers/capability-physics_grippers.md)
    * Requirements:
        * [gripper-site-api](../capabilities/physics_bodies/physics_grippers/requirements/gripper-site-api.md)
            * GR.ISA.001 | Version 0.1.0
            * [Rule | Implementation](../capabilities/physics_bodies/physics_grippers/validation.py)

#### Pipelines Supported for this Feature

None.

#### Test Process

None.

</details>
