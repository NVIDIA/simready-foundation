# Feature: `ID:031 - Self-contained Package Source`

## Description

The Self-contained Package Source feature validates that a source folder is structured so it can be wrapped into a standard SimReady package without pulling in files from elsewhere. Concretely, every asset reference in every USD file under the source must resolve to a file inside the source folder — i.e. paths are anchored (`./...` or properly-encapsulated `../...`) rather than absolute, search-path, or escape-the-root references. This is the minimal pre-flight check the `Package-Candidate` profile runs before the create phase wraps the source into a package.

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET031_PACKAGE_SELF_CONTAINED`|

#### Used in Profiles

* Package-Candidate (v1.0.0)

#### Requirements (1)

* Capability: [Core/Atomic Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)
    * Requirements
        * [Anchored Asset Paths](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md)
            * AA.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)

#### Samples

* `sample_content/common_assets/props_general/apple_a01/simready_usd/`

#### Test Process

* Run pre-validation (`pre_validate` in `nv_core/package_sample/`) against the source folder
* Verify every USD file's asset references resolve to files inside the source folder
* Verify no reference uses an absolute path, a search path, or escapes the source root via unencapsulated `../`

</details>
