# Feature: `ID:030 - Packaging Core`

## Description

The Packaging Core feature ensures that a package is a valid, self-contained SimReady asset package. It covers the package definition (identity, structure, directory layout), the metadata file framework, the shared hash object format, conformance metadata for portable compliance declaration, and inter-package dependency declarations. Internal references within USD content are covered by the Atomic Asset capability (AA.001, anchored asset paths).

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET030_PACKAGING_CORE`|

#### Used in Profiles

* Package (v1.0.0)

#### Requirements (5)

* Capability: [Packaging/Packaging Core](../capabilities/packaging/packaging_core/capability-packaging_core.md)
    * Requirements
        * [Package Definition](../capabilities/packaging/packaging_core/requirements/package-definition.md)
            * PKG.DEF.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/packaging/packaging_core/validation.py)
        * [Metadata Files](../capabilities/packaging/packaging_core/requirements/metadata-files.md)
            * PKG.META.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/packaging/packaging_core/validation.py)
        * [Hash Object Format and Computation](../capabilities/packaging/packaging_core/requirements/hash-object-format.md)
            * PKG.HASH.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/packaging/packaging_core/validation.py)

* Capability: [Packaging/Conformance Metadata](../capabilities/packaging/conformance_metadata/capability-conformance_metadata.md)
    * Requirements
        * [Conformance Metadata](../capabilities/packaging/conformance_metadata/requirements/conformance-metadata.md)
            * PKG.CONF.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/packaging/conformance_metadata/validation.py)

* Capability: [Core/Atomic Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md)
    * Requirements
        * [Anchored Asset Paths](../capabilities/core/atomic_asset/requirements/anchored-asset-paths.md)
            * AA.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/core/atomic_asset/validation.py)

#### Samples

* `sample_content/packaging/simple_packages/`

#### Test Process

* Run `validate_package.py` from `nv_core/package_sample/` against the package's `com.nvidia.simready.packaging.json`
* Verify the package definition file exists at the package root with required fields
* Verify `.metadata/` folder structure and metadata file naming/format
* Verify hash object format and, when present, content hash and package hash computation
* Verify conformance metadata files follow naming and schema conventions
* Verify dependency declarations (when present) use exact `package_id` values, valid `relative_destination` paths, and acyclic references

</details>
