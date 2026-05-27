# Feature: `ID:021 - Robot - Core`
## Description

Robot Core defines the robot metadata and asset structure requirements for use in Isaac Sim: folder layout, naming, thumbnails, physics and schema authoring, and robot schema and type.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Runnable Format
### Version 0.2.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET021_ROBOT_CORE_RUNNABLE`|
| Proprietary Techs       | (None)            |

#### Used in Profiles

This version is used in the following profiles:

- (None documented.)

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | None.             |

* Capability: [Isaac Sim / Robot Core](../capabilities/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [robot-naming](../capabilities/isaac_sim/robot_core/requirements/robot-naming.md)
            * RC.003 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [robot-schema](../capabilities/isaac_sim/robot_core/requirements/robot-schema.md)
            * RC.007 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [robot-type](../capabilities/isaac_sim/robot_core/requirements/robot-type.md)
            * RC.008 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [root-joint-pinned](../capabilities/isaac_sim/robot_core/requirements/root-joint-pinned.md)
            * RC.009 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)

#### Pipelines Supported for this Feature

None.

#### Test Process

None.

</details>

## Isaac Format
### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET021_ROBOT_CORE_ISAAC`|
| Proprietary Techs       | `Isaac Sim`       |

#### Used in Profiles

This version is used in the following profiles:

- (None documented.)

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | None.             |

* Capability: [Isaac Sim / Robot Core](../capabilities/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [clean-folder](../capabilities/isaac_sim/robot_core/requirements/clean-folder.md)
            * RC.001 | Version 0.1.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [robot-naming](../capabilities/isaac_sim/robot_core/requirements/robot-naming.md)
            * RC.003 | Version 0.1.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [thumbnail-exist](../capabilities/isaac_sim/robot_core/requirements/thumbnail-exist.md)
            * RC.004 | Version 0.1.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [verify-robot-physics-attribute-source-layer](../capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-attribute-source-layer.md)
            * RC.005 | Version 0.1.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [verify-robot-physics-schema-source-layer](../capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-schema-source-layer.md)
            * RC.006 | Version 0.1.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [robot-schema](../capabilities/isaac_sim/robot_core/requirements/robot-schema.md)
            * RC.007 | Version 0.1.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)

#### Pipelines Supported for this Feature

None.

#### Test Process

None.

</details>

### Version 0.2.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET021_ROBOT_CORE_ISAAC`|
| Proprietary Techs       | `Isaac Sim`       |

#### Used in Profiles

This version is used in the following profiles:

- (None documented.)

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | None.             |

* Capability: [Isaac Sim / Robot Core](../capabilities/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [clean-folder](../capabilities/isaac_sim/robot_core/requirements/clean-folder.md)
            * RC.001 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [robot-naming](../capabilities/isaac_sim/robot_core/requirements/robot-naming.md)
            * RC.003 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [thumbnail-exist](../capabilities/isaac_sim/robot_core/requirements/thumbnail-exist.md)
            * RC.004 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [verify-robot-physics-attribute-source-layer](../capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-attribute-source-layer.md)
            * RC.005 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [verify-robot-physics-schema-source-layer](../capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-schema-source-layer.md)
            * RC.006 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [robot-schema](../capabilities/isaac_sim/robot_core/requirements/robot-schema.md)
            * RC.007 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [robot-type](../capabilities/isaac_sim/robot_core/requirements/robot-type.md)
            * RC.008 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [root-joint-pinned](../capabilities/isaac_sim/robot_core/requirements/root-joint-pinned.md)
            * RC.009 | Version 0.2.0
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)

#### Pipelines Supported for this Feature

None.

#### Test Process

None.

</details>
