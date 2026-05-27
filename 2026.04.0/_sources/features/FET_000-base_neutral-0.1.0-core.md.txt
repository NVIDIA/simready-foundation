# Feature: `ID:000 - Core - Base`

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET000_CORE`|

## Description
The Core Feature comprises fundamental requirements for USD assets, including naming conventions, path structures, atomic asset properties, and basic units. This feature establishes the foundation for all other features and ensures assets are properly structured and portable across different environments.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Neutral Format

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[Prop Robotics Neutral Profile](../profiles/prop-robotics-neutral.md)** (v0.1.0) - Used as the base core feature
- **[Prop Robotics Physx Profile](../profiles/prop-robotics-physx.md)** (v0.1.0) - Used as the base core feature with PhysX-aware tools

#### Requirements
* Capability: [Core/Naming_Paths](../capabilities/core/naming_paths/capability-naming_paths.md)
    * Requirements
        * [Prim-Naming-Convention](../capabilities/core/naming_paths/requirements/prim-naming-convention.md)
            * NP.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [File-Naming-Convention](../capabilities/core/naming_paths/requirements/file-naming-convention.md)
            * NP.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [Directory-Structure](../capabilities/core/naming_paths/requirements/directory-structure.md)
            * NP.003 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [Path-Length-Limits](../capabilities/core/naming_paths/requirements/path-length-limits.md)
            * NP.004 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [Asset-Folder-Structure](../capabilities/core/naming_paths/requirements/asset-folder-structure.md)
            * NP.005 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [Metadata-Location](../capabilities/core/naming_paths/requirements/metadata-location.md)
            * NP.006 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [Relative-Paths](../capabilities/core/naming_paths/requirements/relative-paths.md)
            * NP.007 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [AssetPath-Validation](../capabilities/core/naming_paths/requirements/assetpath-validation.md)
            * NP.008 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/naming_paths/validation.py)
        * [Metadata-Whitelist](../capabilities/core/sim_ready/requirements/metadata-whitelist.md)
            * SR.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/sim_ready/validation.py)
        * [Undefined-Prims](../capabilities/hierarchy/requirements/undefined-prims.md)
            * HI.011 | version 0.1.0
            * [Rule | Implementation](../capabilities/hierarchy/validation.py)

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
  * Example image: ![image1](./images/obs_revolute_lamp_01.png)

</details>
