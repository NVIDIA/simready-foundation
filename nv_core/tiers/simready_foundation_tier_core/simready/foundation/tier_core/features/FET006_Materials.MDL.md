# Feature: `FET006_Materials.MDL`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET006_Materials.MDL` |
| Runtime                 | `MDL` |
| Proprietary Techs       | `MDL` |
| Versions                | `0-1-0`, `0-2-0`, `0-3-0` |

## Description

Defines the MDL runtime material contract.

Whether renderable geometry resolves a material (`VM.MAT.001`) is
[`FET009_MaterialCoverage`](FET009_MaterialCoverage.md)'s
requirement from version `0-3-0` of this feature. An asset with geometry selects both; a
material published on its own selects this feature without it.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly. Each version
names a `FET006_Materials` version as its `source_feature`: `0-1-0` names
`FET006_Materials.0-1-0`, `0-2-0` names `FET006_Materials.0-2-0`, and
`0-3-0` names `FET006_Materials.0-3-0`. The link classifies this feature as a runtime
variant of that source; it does not make the source feature validate.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies MDL binding, schema, source asset, shader input, texture size, and color-space requirements.
- `simready-foundation-conform-fet-006-mdl` repairs MDL material conformance while preserving visual intent.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robotics-Prop](../profiles/robotics-prop.md): optional in `3.0.0`, `3.1.0`, `3.2.0`, `3.3.0`

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Visualization/Materials](../rules_and_reqs/visualization/materials/capability-materials.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `VM.BIND.002` | [VM.BIND.002](../rules_and_reqs/visualization/materials/requirements/material-shader-inputs.md) | `VisualMaterialsCapabilityChecker` |
| `VM.MAT.001` | [VM.MAT.001](../rules_and_reqs/visualization/materials/requirements/material-assignment.md) | `VisualMaterialsCapabilityChecker` |
| `VM.MDL.001` | [VM.MDL.001](../rules_and_reqs/visualization/materials/requirements/material-mdl-source-asset.md) | `VisualMaterialsCapabilityChecker` |
| `VM.TEX.001` | [VM.TEX.001](../rules_and_reqs/visualization/materials/requirements/material-texture-maxsize.md) | `VisualMaterialsCapabilityChecker` |
| `VM.TEX.002` | [VM.TEX.002](../rules_and_reqs/visualization/materials/requirements/material-texture-colorspace-mdl-deprecated.md) | `VisualMaterialsCapabilityChecker` |

</details>

### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): optional in `3.0.0`, `3.1.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `3.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): optional in `4.0.0`, `5.0.0`

#### Feature Dependencies

None.

#### Changes From Version 0-1-0

`VM.TEX.002` is replaced by `VM.TEX.005`. Both state the color space a texture input
declares; `VM.TEX.005` adds the input that declares nothing, which resolves to `auto` and
decodes an 8-bit three- or four-channel file as sRGB.

`com.nvidia.usd.VM.BIND.001` and `com.nvidia.usd.VM.MDL.002` are added. Both are defined
and enforced by `usd-validation-nvidia`.

`VM.MDL.003` is added: the material a renderable `Gprim` renders with connects an MDL
surface.

#### Requirement List

* Capability: [Visualization/Materials](../rules_and_reqs/visualization/materials/capability-materials.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `com.nvidia.usd.VM.BIND.001` | [VM.BIND.001](../rules_and_reqs/visualization/materials/requirements/material-bind-scope.md) | `MaterialOutOfScopeChecker` |
| `VM.BIND.002` | [VM.BIND.002](../rules_and_reqs/visualization/materials/requirements/material-shader-inputs.md) | `VisualMaterialsCapabilityChecker` |
| `VM.MAT.001` | [VM.MAT.001](../rules_and_reqs/visualization/materials/requirements/material-assignment.md) | `VisualMaterialsCapabilityChecker` |
| `VM.MDL.001` | [VM.MDL.001](../rules_and_reqs/visualization/materials/requirements/material-mdl-source-asset.md) | `VisualMaterialsCapabilityChecker` |
| `com.nvidia.usd.VM.MDL.002` | [VM.MDL.002](../rules_and_reqs/visualization/materials/requirements/material-mdl-schema.md) | `MaterialOldMdlSchemaChecker` |
| `VM.MDL.003` | [VM.MDL.003](../rules_and_reqs/visualization/materials/requirements/material-mdl-surface-present.md) | `VisualMaterialsCapabilityChecker` |
| `VM.TEX.001` | [VM.TEX.001](../rules_and_reqs/visualization/materials/requirements/material-texture-maxsize.md) | `VisualMaterialsCapabilityChecker` |
| `VM.TEX.005` | [VM.TEX.005](../rules_and_reqs/visualization/materials/requirements/material-texture-colorspace-mdl.md) | `VisualMaterialsCapabilityChecker` |

</details>

### Version 0-3-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Material](../profiles/material.md): optional in `1.0.0`
- [Robot-Body](../profiles/robot-body.md): optional in `4.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): optional in `4.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): optional in `5.0.0`

#### Feature Dependencies

None.

#### Changes From Version 0-2-0

`VM.MAT.001` moves to [`FET009_MaterialCoverage`](FET009_MaterialCoverage.md).
The other requirements are those of `0-2-0`.
On an asset with geometry, the runtime tests measure rendered coverage, and a coverage failure
is a `VM.MAT.001` repair through `FET009_MaterialCoverage`. A material published on its
own has no geometry to cover, so the tests render each of its materials on a test sphere.

#### Requirement List

* Capability: [Visualization/Materials](../rules_and_reqs/visualization/materials/capability-materials.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `com.nvidia.usd.VM.BIND.001` | [VM.BIND.001](../rules_and_reqs/visualization/materials/requirements/material-bind-scope.md) | `MaterialOutOfScopeChecker` |
| `VM.BIND.002` | [VM.BIND.002](../rules_and_reqs/visualization/materials/requirements/material-shader-inputs.md) | `VisualMaterialsCapabilityChecker` |
| `VM.MDL.001` | [VM.MDL.001](../rules_and_reqs/visualization/materials/requirements/material-mdl-source-asset.md) | `VisualMaterialsCapabilityChecker` |
| `com.nvidia.usd.VM.MDL.002` | [VM.MDL.002](../rules_and_reqs/visualization/materials/requirements/material-mdl-schema.md) | `MaterialOldMdlSchemaChecker` |
| `VM.MDL.003` | [VM.MDL.003](../rules_and_reqs/visualization/materials/requirements/material-mdl-surface-present.md) | `VisualMaterialsCapabilityChecker` |
| `VM.TEX.001` | [VM.TEX.001](../rules_and_reqs/visualization/materials/requirements/material-texture-maxsize.md) | `VisualMaterialsCapabilityChecker` |
| `VM.TEX.005` | [VM.TEX.005](../rules_and_reqs/visualization/materials/requirements/material-texture-colorspace-mdl.md) | `VisualMaterialsCapabilityChecker` |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies MDL binding, schema, source asset, shader input, texture size, and color-space requirements.
- `simready-foundation-conform-fet-006-mdl` repairs MDL material conformance while preserving visual intent.

## Samples

- [`obs_electricians_large_tool_box_a01`](../../../../../../../sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd)
- [`obs_orange_a02`](../../../../../../../sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd)

## Evaluates

- Suite: [FET006 Materials](../runtime_tests/docs/fet006-materials.md)
  - Tests:
    - [mdl_renders](../runtime_tests/docs/fet006/mdl-renders.md)

## Adapters

None.
