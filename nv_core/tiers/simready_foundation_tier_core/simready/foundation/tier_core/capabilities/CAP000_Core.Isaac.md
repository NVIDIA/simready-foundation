# Capability: `CAP000_Core.Isaac`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP000_Core.Isaac` |
| Runtime                 | `Isaac` |
| Proprietary Techs       | `Isaac Sim` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

This capability defines the Isaac packaging and physics-layer Core contract on top
of neutral Core. An asset that satisfies this capability keeps a clean Isaac-style
package folder, provides a representative thumbnail, and authors physics
schemas and attributes in the expected physics source layer.

This is the Isaac packaging companion to the solver Core variants
(`CAP000_Core.PhysX`, `CAP000_Core.Newton`, `CAP000_Core.MuJoCo`). It does not define robot
identity, naming, type, or root-joint policy; those requirements live in
`CAP021_RobotCore.Isaac`.

## Dependency Graph

```{mermaid}
flowchart LR
    FET000I["CAP000_Core.Isaac\n0-1-0"]
    FET000S["CAP000_Core\n0-1-0"]
    FET000I2["CAP000_Core.Isaac\n0-2-0"]
    FET000S2["CAP000_Core\n0-2-0"]

    FET000I --> FET000S
    FET000I2 --> FET000S2

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET000I,FET000I2 current
    class FET000S,FET000S2 other
```

## Use Cases

Products or workflows that consume this capability:

- Robot-Body profile validation for optional Isaac package cleanliness and physics-layer separation.
- Isaac robot packaging workflows that keep physics opinions out of the base layer.
- Combined with `CAP021_RobotCore.Isaac` when both Isaac packaging and robot identity are required.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `2.0.0`, `2.1.0`, `2.2.0`, `2.3.0`, `3.0.0`

#### Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Core](CAP000_Core.md) (`CAP000_Core.0-1-0`) |

#### Requirement List

* Capability: [Isaac Sim/Robot Core](../rules_and_reqs/isaac_sim/robot_core/requirements.md)
    * Requirements:
        * [Clean Folder](../rules_and_reqs/isaac_sim/robot_core/requirements/clean-folder.md)
            * `RC.001` | Version `0.1.0`
        * [Thumbnail Exists](../rules_and_reqs/isaac_sim/robot_core/requirements/thumbnail-exist.md)
            * `RC.004` | Version `0.1.0`
        * [Robot Physics Attribute Source Layer](../rules_and_reqs/isaac_sim/robot_core/requirements/verify-robot-physics-attribute-source-layer.md)
            * `RC.005` | Version `0.1.0`
        * [Robot Physics Schema Source Layer](../rules_and_reqs/isaac_sim/robot_core/requirements/verify-robot-physics-schema-source-layer.md)
            * `RC.006` | Version `0.1.0`

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `4.0.0`

#### Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [Core](CAP000_Core.md) (`CAP000_Core.0-2-0`) |

#### Requirement List

Same as version `0-1-0`: `RC.001`, `RC.004`, `RC.005`, `RC.006`.

#### Changes From Version 0-1-0

Version `0-2-0` depends on `CAP000_Core.0-2-0`, so it no longer brings
in `NP.006` or `SR.001`. Its own requirements are unchanged.

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author or repair Isaac package layout, thumbnails, and physics source-layer placement.
- `.urdf`, `.mjcf`
  - Via Isaac-oriented conversion workflows that split physics opinions into the physics layer.

Validation or runtime pipeline:

- SimReady validation - verifies the selected `CAP000_Core.Isaac` manifest.
- `simready-foundation-conform-fet-000-isaac` - repairs clean-folder, thumbnail, and physics-layer placement on staged Isaac outputs.

## Samples

- [`ur10` Isaac robot](../../../../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usd)

## Evaluates

- None.

## Adapters

None.
