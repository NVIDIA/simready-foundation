# Feature: `ID:007 - Non-Visual Materials - Base`

| **Property**            | **Value**                   |
|-------------------------|-----------------------------|
|Internal ID              | `FET007_BASE_NEUTRAL`|
| Proprietary Techs       | `RTX`                       |
| Dependency              | `None`                      |


## Description
This feature describes the requirements necessary to have materials with non-visual sensor attributes that enable accurate sensor simulation (such as radar, lidar, thermal imaging). These attributes define material properties that affect sensor response but are not visible to the human eye.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products that consume this feature:

- AV Sim
- IsaacSim
- MEGA
- Lightwheel SOW1

## Neutral Format

### Version 0.2.0
<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is not currently used in any profiles.

#### Requirements
* Capability: [Non-Visual Sensors/Non-Visual Materials](../capabilities/nonvisual_sensors/nonvisual_materials/capability-nonvisual_materials.md)
    * Requirements
        * [Material-Attributes](../capabilities/nonvisual_sensors/nonvisual_materials/requirements/material-attributes.md)
            * NVM.001 | version 0.2.0
            * [Rule | Implementation](../capabilities/nonvisual_sensors/nonvisual_materials/validation.py)
        * [Material-Base](../capabilities/nonvisual_sensors/nonvisual_materials/requirements/material-base.md)
            * NVM.002 | version 0.2.0
            * [Rule | Implementation](../capabilities/nonvisual_sensors/nonvisual_materials/validation.py)
        * [Material-Coating](../capabilities/nonvisual_sensors/nonvisual_materials/requirements/material-coating.md)
            * NVM.003 | version 0.2.0
            * [Rule | Implementation](../capabilities/nonvisual_sensors/nonvisual_materials/validation.py)
        * [Material-Binding](../capabilities/nonvisual_sensors/nonvisual_materials/requirements/material-binding.md)
            * NVM.004 | version 0.2.0
            * [Rule | Implementation](../capabilities/nonvisual_sensors/nonvisual_materials/validation.py)
        * [Material-Consistency](../capabilities/nonvisual_sensors/nonvisual_materials/requirements/material-consistency.md)
            * NVM.005 | version 0.2.0
            * [Rule | Implementation](../capabilities/nonvisual_sensors/nonvisual_materials/validation.py)
        * [Material-Time](../capabilities/nonvisual_sensors/nonvisual_materials/requirements/material-time.md)
            * NVM.006 | version 0.2.0
            * [Rule | Implementation](../capabilities/nonvisual_sensors/nonvisual_materials/validation.py)

#### Used in Profiles

This version is not currently used in any profiles.

#### Pipelines Supported for this Feature
Source file type:
* .blend
  * Via Blender SimReady Add-ons
* .mjcf
  * Via Blender SimReady Add-ons + MJCF2USD Tool
* .step
  * Via Blender SimReady Add-ons + CAD Converter

#### Test Process

* Obtain the usd sdk
  * [usd sdk link](https://developer.nvidia.com/usd?sortBy=developer_learning_library%2Fsort%2Ffeatured_in.usd_resources%3Adesc%2Ctitle%3Aasc&hitsPerPage=6#section-getting-started)
* Confirm your asset in question has passed validation
* In your commandline type:
  * ```path/to/usdsdk/scripts/usdrecord <path to usdfile.usd> <path to output.png>```
* Open up path/to/output.png
* Expected Result:
  * Confirm it is NOT empty or completely black
  * Material attributes should be properly bound and non-time-varying

</details>

---

#### Comments

This feature enables accurate sensor simulation by providing material attributes that affect non-visual sensors like radar, lidar, and thermal imaging systems. The requirements ensure that materials have the necessary properties for realistic sensor response while maintaining consistency with visual materials.
