# Feature: `FET_021_ISAAC`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_021_ISAAC` |
| Runtime                 | `ISAAC` |
| Proprietary Techs       | `Isaac Sim` |
| Latest Version          | `0.3.0` |

## Description

This feature defines the Isaac robot-core identity contract for robot assets. An
asset that satisfies this feature has compliant robot naming, robot schema
metadata and relationships on the default prim, an explicit robot type, and
root-joint pinning behavior that matches that robot type.

Version `0.3.0` is identity-only. Isaac package cleanliness, thumbnails, and
physics-layer source placement live in `FET_000_ISAAC`. Earlier versions bundled
those packaging requirements into this feature.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000I["FET_000_ISAAC\n0.1.0"]
    FET021I1["FET_021_ISAAC\n0.1.0"]
    FET021I2["FET_021_ISAAC\n0.2.0"]
    FET021I3["FET_021_ISAAC\n0.3.0"]

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET021I3 current
    class FET000I,FET021I1,FET021I2 other
```

Version `0.3.0` has no feature dependencies. Pair it with `FET_000_ISAAC@0.1.0`
when Isaac packaging is also required.

## Use Cases

Products or workflows that consume this feature:

- Robot-Body-Isaac profile validation for robot identity and schema.
- Robot-Body-Runnable profile validation for robot naming, schema, type, and root-joint policy.
- Robot conversion workflows that preserve robot link and joint topology.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is not currently used by profile TOML entries. It is retained as
the older Isaac robot-core contract that bundled packaging and schema checks.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Isaac Sim/Robot Core](../capabilities/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [Clean Folder](../capabilities/isaac_sim/robot_core/requirements/clean-folder.md)
            * `RC.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Robot Naming](../capabilities/isaac_sim/robot_core/requirements/robot-naming.md)
            * `RC.003` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Thumbnail Exists](../capabilities/isaac_sim/robot_core/requirements/thumbnail-exist.md)
            * `RC.004` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Robot Physics Attribute Source Layer](../capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-attribute-source-layer.md)
            * `RC.005` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Robot Physics Schema Source Layer](../capabilities/isaac_sim/robot_core/requirements/verify-robot-physics-schema-source-layer.md)
            * `RC.006` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Robot Schema](../capabilities/isaac_sim/robot_core/requirements/robot-schema.md)
            * `RC.007` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version remains pinned by older Robot-Body-Isaac profile versions that have
not yet opted into the packaging/identity split.

- **[Robot Body Isaac Profile](../profiles/robot-body-isaac.md)** (`v1.0.0`, `v1.1.0`)

#### Feature Dependencies

None. Packaging and identity requirements are listed explicitly on this version.

#### Changes From Version 0.1.0

| Change | Requirement | Reason |
|--------|-------------|--------|
| Added | `RC.008` | Robot type is required for robot runtime behavior and root-joint policy. |
| Added | `RC.009` | Root-joint pinning must match the selected robot type. |

#### Requirement List

* Capability: [Isaac Sim/Robot Core](../capabilities/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007`, `RC.008`, `RC.009`

</details>

### Version 0.3.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Robot Body Runnable Profile](../profiles/robot-body-runnable.md)** (`v1.0.0`, `v1.1.0`) - Robot naming, schema, type, and root-joint gate.
- **[Robot Body Profile](../profiles/robot-body.md)** (`v2.0.0`) - Optional robot-core identity gate.

#### Feature Dependencies

None.

#### Changes From Version 0.2.0

Version `0.3.0` keeps only the robot-identity requirements. Packaging
requirements move to `FET_000_ISAAC@0.1.0`:

| Change | Requirement | Reason |
|--------|-------------|--------|
| Removed | `RC.001` | Clean-folder packaging moved to `FET_000_ISAAC`. |
| Removed | `RC.004` | Thumbnail packaging moved to `FET_000_ISAAC`. |
| Removed | `RC.005` | Physics-attribute source-layer packaging moved to `FET_000_ISAAC`. |
| Removed | `RC.006` | Physics-schema source-layer packaging moved to `FET_000_ISAAC`. |

#### Requirement List

* Capability: [Isaac Sim/Robot Core](../capabilities/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [Robot Naming](../capabilities/isaac_sim/robot_core/requirements/robot-naming.md)
            * `RC.003` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Robot Schema](../capabilities/isaac_sim/robot_core/requirements/robot-schema.md)
            * `RC.007` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Robot Type](../capabilities/isaac_sim/robot_core/requirements/robot-type.md)
            * `RC.008` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)
        * [Root Joint Pinned](../capabilities/isaac_sim/robot_core/requirements/root-joint-pinned.md)
            * `RC.009` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/isaac_sim/robot_core/validation.py)

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author or repair robot schema metadata and robot link/joint relationships on the default prim.
- `.urdf`, `.mjcf`
  - Via robot conversion workflows that produce robot link and joint topology.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `FET_021_ISAAC` manifest.
- `simready-foundation-conform-fet-021-isaac` - repairs robot naming, schema relationships, robot type, and root-joint pinning on staged robot outputs.
- For Isaac packaging (`RC.001`, `RC.004`, `RC.005`, `RC.006`), use `simready-foundation-conform-fet-000-isaac`.

## Samples

- [`ur10` Isaac robot](../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Benchmarks

- None.

## Adapters

None.
