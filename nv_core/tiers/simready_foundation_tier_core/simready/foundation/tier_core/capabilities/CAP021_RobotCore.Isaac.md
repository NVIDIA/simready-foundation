# Capability: `CAP021_RobotCore.Isaac`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP021_RobotCore.Isaac` |
| Runtime                 | `Isaac` |
| Proprietary Techs       | `Isaac Sim` |
| Versions                | `0-1-0`, `0-2-0`, `0-3-0` |

## Description

This capability defines the Isaac robot-core identity contract for robot assets. An
asset that satisfies this capability has compliant robot naming, robot schema
metadata and relationships on the default prim, an explicit robot type, and
root-joint pinning behavior that matches that robot type.

Version `0-3-0` is identity-only. Isaac package cleanliness, thumbnails, and
physics-layer source placement live in `CAP000_Core.Isaac`. Earlier versions bundled
those packaging requirements into this capability.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000I["CAP000_Core.Isaac\n0-1-0"]
    FET021I1["CAP021_RobotCore.Isaac\n0-1-0"]
    FET021I2["CAP021_RobotCore.Isaac\n0-2-0"]
    FET021I3["CAP021_RobotCore.Isaac\n0-3-0"]

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET021I3 current
    class FET000I,FET021I1,FET021I2 other
```

Version `0-3-0` has no feature dependencies. Pair it with `CAP000_Core.Isaac.0-1-0`
when Isaac packaging is also required.

## Use Cases

Products or workflows that consume this capability:

- Robot-Body profile validation for robot identity, naming, schema, type, and root-joint policy.
- Robot conversion workflows that preserve robot link and joint topology.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

No profile selects this version.

#### Dependencies

None.

#### Requirement List

* Capability: [Isaac Sim/Robot Core](../rules_and_reqs/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [Clean Folder](../rules_and_reqs/isaac_sim/robot_core/requirements/clean-folder.md)
            * `RC.001` | Version `0.1.0`
        * [Robot Naming](../rules_and_reqs/isaac_sim/robot_core/requirements/robot-naming.md)
            * `RC.003` | Version `0.1.0`
        * [Thumbnail Exists](../rules_and_reqs/isaac_sim/robot_core/requirements/thumbnail-exist.md)
            * `RC.004` | Version `0.1.0`
        * [Robot Physics Attribute Source Layer](../rules_and_reqs/isaac_sim/robot_core/requirements/verify-robot-physics-attribute-source-layer.md)
            * `RC.005` | Version `0.1.0`
        * [Robot Physics Schema Source Layer](../rules_and_reqs/isaac_sim/robot_core/requirements/verify-robot-physics-schema-source-layer.md)
            * `RC.006` | Version `0.1.0`
        * [Robot Schema](../rules_and_reqs/isaac_sim/robot_core/requirements/robot-schema.md)
            * `RC.007` | Version `0.1.0`

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Gripper](../profiles/robot-gripper.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `3.0.0`

#### Dependencies

None. Packaging and identity requirements are listed explicitly on this version.

#### Changes From Version 0-1-0

| Change | Requirement | Reason |
|--------|-------------|--------|
| Added | `RC.008` | Robot type is required for robot runtime behavior and root-joint policy. |
| Added | `RC.009` | Root-joint pinning must match the selected robot type. |

#### Requirement List

* Capability: [Isaac Sim/Robot Core](../rules_and_reqs/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007`, `RC.008`, `RC.009`

</details>

### Version 0-3-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`

#### Dependencies

None.

#### Changes From Version 0-2-0

Version `0-3-0` keeps only the robot-identity requirements. Packaging
requirements move to `CAP000_Core.Isaac.0-1-0`:

| Change | Requirement | Reason |
|--------|-------------|--------|
| Removed | `RC.001` | Clean-folder packaging moved to `CAP000_Core.Isaac`. |
| Removed | `RC.004` | Thumbnail packaging moved to `CAP000_Core.Isaac`. |
| Removed | `RC.005` | Physics-attribute source-layer packaging moved to `CAP000_Core.Isaac`. |
| Removed | `RC.006` | Physics-schema source-layer packaging moved to `CAP000_Core.Isaac`. |

#### Requirement List

* Capability: [Isaac Sim/Robot Core](../rules_and_reqs/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [Robot Naming](../rules_and_reqs/isaac_sim/robot_core/requirements/robot-naming.md)
            * `RC.003` | Version `0.1.0`
        * [Robot Schema](../rules_and_reqs/isaac_sim/robot_core/requirements/robot-schema.md)
            * `RC.007` | Version `0.1.0`
        * [Robot Type](../rules_and_reqs/isaac_sim/robot_core/requirements/robot-type.md)
            * `RC.008` | Version `0.1.0`
        * [Root Joint Pinned](../rules_and_reqs/isaac_sim/robot_core/requirements/root-joint-pinned.md)
            * `RC.009` | Version `0.1.0`

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author or repair robot schema metadata and robot link/joint relationships on the default prim.
- `.urdf`, `.mjcf`
  - Via robot conversion workflows that produce robot link and joint topology.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `CAP021_RobotCore.Isaac` manifest.
- `simready-foundation-conform-fet-021-isaac` - repairs robot naming, schema relationships, robot type, and root-joint pinning on staged robot outputs.
- For Isaac packaging (`RC.001`, `RC.004`, `RC.005`, `RC.006`), use `simready-foundation-conform-fet-000-isaac`.

## Samples

- [`ur10` Isaac robot](../../../../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Evaluates

- None.

## Adapters

None.
