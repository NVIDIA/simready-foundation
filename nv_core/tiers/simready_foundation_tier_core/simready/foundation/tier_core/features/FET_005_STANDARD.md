# Feature: `FET_005_STANDARD`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Feature Name            | `FET_005_STANDARD` |
| Runtime                 | `STANDARD` |
| Proprietary Techs       | `None` |
| Latest Version          | `0.1.0` |

## Description

This feature defines the Standard OpenUSD grasp contract for prop assets. An
asset that satisfies this feature has physics material bindings on colliders and
at least one authored grasp vector line that identifies a plausible robotic
gripper grasp region.

Static validation proves the authored physics material binding and grasp-line
structure. SimReady-quality grasp authoring also requires visual or runtime
review to confirm that the line intersects the intended graspable region and is
not merely an arbitrary validator token.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- Isaac Sim robotic grasp workflows
- MEGA
- Lightwheel SOW1
- SimReady prop profile validation

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics Neutral Profile](../profiles/prop-robotics-neutral.md)** (`v1.0.0`, `v2.0.0`, `v2.0.1`, `v2.1.0`) - Requires grasp vectors and physics material bindings for graspable neutral props.
- **[Prop Robotics PhysX Profile](../profiles/prop-robotics-physx.md)** (`v1.0.0`, `v2.0.0`, `v2.0.1`, `v2.1.0`) - Reuses the Standard grasp contract for PhysX prop workflows.
- **[Prop Robotics Isaac Profile](../profiles/prop-robotics-isaac.md)** (`v1.0.0`, `v1.0.1`, `v1.1.0`) - Reuses the Standard grasp contract for Isaac Sim prop workflows.
- **[Robotics Prop Profile](../profiles/profiles.md)** (`v3.0.0`) - Optional consolidated grasp feature.

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Physics Bodies/Physics Materials](../capabilities/physics_bodies/physics_materials/capability-physics_materials.md)
    * Requirements:
        * [Collider Material Binding](../capabilities/physics_bodies/physics_materials/requirements/collider-material-binding.md)
            * `PMT.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/physics_bodies/physics_materials/validation.py)
* Capability: [Physics Bodies/Physics Graspable](../capabilities/physics_bodies/physics_graspable/capability-physics_graspable.md)
    * Requirements:
        * [Graspable Vector Line](../capabilities/physics_bodies/physics_graspable/requirements/graspable-vector-line.md)
            * `GSP.001` | Version `0.1.0`
            * [Rule | Implementation](../capabilities/physics_bodies/physics_graspable/validation.py)

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author or repair grasp vectors as `UsdGeom.BasisCurves` prims under the default prim.

Validation or runtime pipeline:

- SimReady validation - verifies `PMT.001` and the static `GSP.001` BasisCurves contract.
- FET005 grasp-and-lift benchmark - provides runtime evidence that declared grasp vectors are physically achievable.
- `simready-foundation-conform-fet-005-standard` - vision-guided repair workflow for grasp vector authoring.

## Samples

- [`obs_electricians_large_tool_box_a01`](../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd)

## Benchmarks

- Suite: [FET005 Grasp](../guides/benchmark/tests/fet005-grasp.md)
  - Tests:
    - [grasp_and_lift](../guides/benchmark/tests/fet005/grasp-and-lift.md)

## Adapters

None.
