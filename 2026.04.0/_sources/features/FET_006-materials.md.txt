# Feature: `ID:006 - Materials - Base`

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET006_BASE_USDPREVIEW`|

## Description
The Materials Feature provides support for material definitions in USD assets, enabling consistent material appearance across different rendering engines and viewers. This feature supports both standard USD Preview Surface materials and advanced Material Definition Language (MDL) materials for different use cases and rendering workflows.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products that consume this feature:

- MetroSim
- AI Factory
- IsaacSim
- MEGA
- Lightwheel SOW1

## USDPreviewSurface Format

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics Neutral Profile](../profiles/prop-robotics-neutral.md)** (v0.1.0) - Used as the base material feature for USDPreviewSurface materials

#### Requirements

* Capability: [Visualization/Materials](../capabilities/visualization/materials/capability-materials.md)
    * Requirements
        * [Material-Bind-Scope](../capabilities/visualization/materials/requirements/material-bind-scope.md)
            * VM.BIND.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)
        * [Material-Preview-Surface](../capabilities/visualization/materials/requirements/material-preview-surface.md)
            * VM.PS.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)


* Material Paths:
    * all relative, exist.

Material binding on _all_ meshes, that aren't 'type=guides'.


#### Pipelines Supported for this Feature
Source file type:
* .blend
  * Via Blender SimReady Add-ons
* .mjcf
  * Via Blender SimReady Add-ons + MJCF2USD Tool
* .step
  * Via Blender SimReady Add-ons + CAD Converter

#### Samples

* [sample_content/common_assets/props_general/obs_lamp_revolute_01/simready_usd/obs_lamp_revolute_01.usd](../../../../sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usd)

#### Test Process

* Obtain the usd sdk
  * [usd sdk link](https://developer.nvidia.com/usd?sortBy=developer_learning_library%2Fsort%2Ffeatured_in.usd_resources%3Adesc%2Ctitle%3Aasc&hitsPerPage=6#section-getting-started)
* Confirm your asset in question has passed validation
* In your commandline type:
  * ```path/to/usdsdk/scripts/usdrecord <path to usdfile.usd> <path to output.png>```
* Open up path/to/output.png
* Expected Result:
  * Confirm it is NOT empty or completely black
  * Materials should render with proper USDPreviewSurface appearance
  * Example image: ![image1](./images/obs_revolute_lamp_01.png)

</details>


## MDL Format

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Internal ID             | `FET006_BASE_MDL`|
| Proprietary Techs       | `MDL`             |

#### Used in Profiles

* Material Paths:
    * all relative, exist.
* MDL Paths
    * all relative, exist.
* MDL Compiles?
    * MDL Checker exists already?
* Glass?

Material binding on _all_ meshes, that aren't 'type=guides'.

OmniPBR / SimPBR:
    * Color Space for textures.
    * ORM analysis?  if strength > 0, ensure map is there.
    * Confirm ORM floats are 0 if map is bound.

This version is used in the following profiles:

- **[Prop Robotics Physx Profile](../profiles/prop-robotics-physx.md)** (v0.1.0) - Used as the advanced material feature for MDL materials

#### Requirements

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [ID:006 - Materials - Base - USDPreviewSurface Format - v0.1.0](../features/FET_006-materials.md#version-010) |

* Capability: [Visualization/Materials](../capabilities/visualization/materials/capability-materials.md)
    * Requirements
        * [Material-Bind-Scope](../capabilities/visualization/materials/requirements/material-bind-scope.md)
            * VM.BIND.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)
        * [Material-Shader-Inputs](../capabilities/visualization/materials/requirements/material-shader-inputs.md)
            * VM.BIND.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)
        * [Mesh Material Binding](../capabilities/visualization/materials/requirements/material-assignment.md)
            * VM.MAT.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)
        * [Material-MDL-Schema](../capabilities/visualization/materials/requirements/material-mdl-schema.md)
            * VM.MDL.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)
        * [Material-MDL-Source-Asset](../capabilities/visualization/materials/requirements/material-mdl-source-asset.md)
            * VM.MDL.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)
        * [Material-Texture-Size](../capabilities/visualization/materials/requirements/material-texture-maxsize.md)
            * VM.TEX.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)
        * [Material-Texture-Colorspace](../capabilities/visualization/materials/requirements/material-texture-colorspace.md)
            * VM.TEX.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/visualization/materials/validation.py)

#### Pipelines Supported for this Feature

None; USDPreviewSurface Format is acceptable.

#### Samples

* [sample_content/common_assets/props_general/obs_lamp_revolute_01/simready_usd/obs_lamp_revolute_01.usd](../../../../sample_content/common_assets/props_general/obs_lamp_revolute_a01/simready_usd/sm_obs_lamp_revolute_a01_01.usd)

#### Test Process

* Obtain Isaac Sim or Omniverse Create
  * [Omniverse Create link](https://www.nvidia.com/en-us/omniverse/create/)
* Confirm your asset in question has passed validation
* Open the asset in Omniverse Create
* Expected Result:
  * Materials should render with proper MDL appearance
  * Advanced material features should be functional
  * Material should be compatible with MDL rendering pipeline

</details>
