# Capability: `CAP007_NonVisualMaterials`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP007_NonVisualMaterials` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-2-0` |

## Description

This capability defines the Standard OpenUSD contract for non-visual sensor
material attributes. An asset that satisfies this capability has sensor-facing
material classifications authored on bound `UsdShade.Material` prims so radar,
lidar, thermal, and related sensor simulations can reason about surfaces beyond
visible shader appearance.

The feature is a material-semantics contract. Static validation verifies that
bound materials carry the required non-visual attributes, that values come from
the supported value lists, that authored attributes are on bound materials, and
that those attributes are not time-varying. Correct authoring still requires
material evidence or an approved classification policy; these values should not
be guessed only to satisfy validation.

## Dependency Graph

This capability has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this capability:

- AV Sim
- Isaac Sim RTX sensor workflows
- MEGA
- Lightwheel SOW1
- Robotics prop profile validation when non-visual materials are selected

## Requirements

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robotics-Prop](../profiles/robotics-prop.md): optional in `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`, `4.0.0`, `5.0.0`

#### Dependencies

None.

#### Requirement List

* Capability: [Non-Visual Sensors/Non-Visual Materials](../rules_and_reqs/nonvisual_sensors/nonvisual_materials/capability-nonvisual_materials.md)
    * Requirements:
        * [Material Attributes](../rules_and_reqs/nonvisual_sensors/nonvisual_materials/requirements/material-attributes.md)
            * `NVM.001` | Version `0.1.0`
        * [Material Base](../rules_and_reqs/nonvisual_sensors/nonvisual_materials/requirements/material-base.md)
            * `NVM.002` | Version `0.1.0`
        * [Material Coating](../rules_and_reqs/nonvisual_sensors/nonvisual_materials/requirements/material-coating.md)
            * `NVM.003` | Version `0.1.0`
        * [Material Binding](../rules_and_reqs/nonvisual_sensors/nonvisual_materials/requirements/material-binding.md)
            * `NVM.004` | Version `0.1.0`
        * [Material Consistency](../rules_and_reqs/nonvisual_sensors/nonvisual_materials/requirements/material-consistency.md)
            * `NVM.005` | Version `0.1.0`
        * [Material Time](../rules_and_reqs/nonvisual_sensors/nonvisual_materials/requirements/material-time.md)
            * `NVM.006` | Version `0.1.0`

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Author or repair `omni:simready:nonvisual:*` attributes on bound `UsdShade.Material` prims.
- `.blend`
  - Via Blender SimReady Add-ons.
- `.mjcf`
  - Via Blender SimReady Add-ons and MJCF2USD tooling.
- `.step`
  - Via Blender SimReady Add-ons and CAD Converter tooling.

Validation or runtime pipeline:

- SimReady validation - verifies the static `NVM.001` through `NVM.006` non-visual material contract.
- No Evaluate runtime test is currently registered for this capability.
- `simready-foundation-conform-fet-007-standard` - material-semantics repair workflow for bound material classifications.

## Samples

- [`obs_electricians_large_tool_box_a01`](../../../../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd)

## Evaluates

None currently registered.

## Adapters

None.
