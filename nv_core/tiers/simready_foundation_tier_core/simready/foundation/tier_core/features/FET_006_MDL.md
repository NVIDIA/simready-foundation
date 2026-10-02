# Feature: `FET_006_MDL`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET_006_MDL` |
| Runtime | `MDL` |
| Proprietary Techs | `MDL` |
| Latest Version | `0.1.0` |

## Description

Defines the MDL runtime material contract. This is a sibling runtime contract to FET_006_STANDARD, not a dependency on USDPreviewSurface.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies MDL binding, schema, source asset, shader input, texture size, and color-space requirements.
- `simready-foundation-conform-fet-006-mdl` repairs MDL material conformance while preserving visual intent.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

Required:

- Prop Robotics Neutral v1.0.0, v2.0.0, v2.0.1, v2.1.0, v2.2.0
- Prop Robotics PhysX v1.0.0, v2.0.0, v2.0.1, v2.1.0, v2.2.0

Optional MDL material gate:

- Robotics Prop v3.0.0, v3.1.0

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Visualization/Materials](../capabilities/visualization/materials/capability-materials.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `VM.BIND.002` | [VM.BIND.002](../capabilities/visualization/materials/requirements/material-shader-inputs.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.MAT.001` | [VM.MAT.001](../capabilities/visualization/materials/requirements/material-assignment.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.MDL.001` | [VM.MDL.001](../capabilities/visualization/materials/requirements/material-mdl-source-asset.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.TEX.001` | [VM.TEX.001](../capabilities/visualization/materials/requirements/material-texture-maxsize.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.TEX.002` | [VM.TEX.002](../capabilities/visualization/materials/requirements/material-texture-colorspace-mdl.md) | [Implementation](../capabilities/visualization/materials/validation.py) |

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

Optional MDL material gate:

- Robotics Prop v4.0.0, Robot Body v3.0.0, Robot Gripper v3.0.0

#### Feature Dependencies

None.

#### Changes From Version 0.1.0

`VM.TEX.002` is replaced by `VM.TEX.005`. Both state the color space a texture input
declares; `VM.TEX.005` adds the input that declares nothing, which resolves to `auto` and
decodes an 8-bit three- or four-channel file as sRGB. `VM.TEX.002` remains at 0.1.0 so an
asset validated against that version keeps its result.

`com.nvidia.usd.VM.BIND.001` and `com.nvidia.usd.VM.MDL.002` are added. Both are defined
and enforced by `usd-validation-nvidia`.

#### Requirement List

* Capability: [Visualization/Materials](../capabilities/visualization/materials/capability-materials.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `com.nvidia.usd.VM.BIND.001` | Defined by `usd-validation-nvidia` | `MaterialOutOfScopeChecker` |
| `VM.BIND.002` | [VM.BIND.002](../capabilities/visualization/materials/requirements/material-shader-inputs.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.MAT.001` | [VM.MAT.001](../capabilities/visualization/materials/requirements/material-assignment.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.MDL.001` | [VM.MDL.001](../capabilities/visualization/materials/requirements/material-mdl-source-asset.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `com.nvidia.usd.VM.MDL.002` | Defined by `usd-validation-nvidia` | `MaterialOldMdlSchemaChecker` |
| `VM.TEX.001` | [VM.TEX.001](../capabilities/visualization/materials/requirements/material-texture-maxsize.md) | [Implementation](../capabilities/visualization/materials/validation.py) |
| `VM.TEX.005` | [VM.TEX.005](../capabilities/visualization/materials/requirements/material-texture-colorspace-mdl.md) | [Implementation](../capabilities/visualization/materials/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies MDL binding, schema, source asset, shader input, texture size, and color-space requirements.
- `simready-foundation-conform-fet-006-mdl` repairs MDL material conformance while preserving visual intent.

## Samples

- `sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd`
- `sample_content/common_assets/props_general/obs_orange_a02/simready_usd/sm_obs_orange_a02_01.usd`

## Benchmarks

None currently registered.

## Adapters

None.
