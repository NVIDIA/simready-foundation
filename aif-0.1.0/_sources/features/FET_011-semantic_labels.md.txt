# Feature: `ID:011 - Semantic Labels - Base`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Proprietary Techs       | `Core USD, Open USD, NVIDIA Omniverse, RTX` |
| Dependency              | `None`                      |
|Internal ID              | `FET011_BASE_NEUTRAL`|

## Description
This feature describes the requirements necessary to have semantic label attributes on geometry prims. These semantics may be used to provide ground truth for ML training by verifying perception system identification and classification of objects.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products that consume this feature:

- NDAS SDG / Stargate
- MEGA
- Lightwheel SOW1

## Neutral Format

### Version 0.2.0
<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is not currently used in any profiles.

#### Requirements
* Capability: [Semantic Labels](../capabilities/semantic_labels/capability-semantic_labels.md)
    * Requirements
        * [Semantic-Label-Capability](../capabilities/semantic_labels/requirements/semantic-label-capability.md)
            * SL.001 | version 0.2.0
            * [Rule | Implementation](../capabilities/semantic_labels/validation.py)
        * [Semantic-Label-QCode-Valid](../capabilities/semantic_labels/requirements/semantic-label-qcode-valid.md)
            * SL.QCODE.001 | version 0.2.0
            * [Rule | Implementation](../capabilities/semantic_labels/validation.py)
        * [Semantic-Label-Schema](../capabilities/semantic_labels/requirements/semantic-label-schema.md)
            * SL.003 | version 0.2.0
            * [Rule | Implementation](../capabilities/semantic_labels/validation.py)
        * [Semantic-Label-Time](../capabilities/semantic_labels/requirements/semantic-label-time.md)
            * SL.NV.002 | version 0.2.0
            * [Rule | Implementation](../capabilities/semantic_labels/validation.py)

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
  * All geometry prims should have semantic labels
  * Semantic labels should use proper schema and not contain time samples

</details>

---

#### Comments

This feature enables ML training ground truth by providing semantic label attributes on geometry prims. The requirements ensure that all geometry is properly labeled using the SemanticsLabelsAPI schema, with support for Wikidata ontology Q-Codes and proper time-invariant labeling for sensor simulation.
