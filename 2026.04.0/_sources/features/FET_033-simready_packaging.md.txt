# Feature: `ID:033 - SimReady Packaging`

## Description

The SimReady Packaging feature adds SimReady-specific packaging expectations on top of the universal Packaging Core feature. It is intended for requirements that package consumers need for SimReady workflows. These requirements should not apply to every generic package.

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET033_SIMREADY_PACKAGING`|

#### Used in Profiles

* Package-Candidate (v1.0.0)

#### Requirements (1)

Dependencies:
* [FET_031 Self-contained Package Source](FET_031-package_self_contained.md) (v0.1.0) - provides the valid package structure this feature extends

* Capability: [Core/SimReady](../capabilities/core/sim_ready/capability-sim_ready.md)
    * Requirements
        * [Thumbnail Exist](../capabilities/core/sim_ready/requirements/thumbnail-exist.md)
            * SR.002 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/sim_ready/validation.py)

#### Samples

_No sample packages are dedicated to this feature yet._

#### Test Process

* Validate the package against Self-contained Package Source (FET031)
* Validate each intended SimReady root asset against SR.002
* Verify the thumbnail exists next to the asset under `.thumbs/256x256/`

</details>
