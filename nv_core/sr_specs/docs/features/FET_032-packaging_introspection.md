# Feature: `ID:032 - Packaging Introspection`

## Description

The Packaging Introspection feature enables consumers to examine a package's contents without downloading the full package. It adds the Bill of Materials (BOM) requirement — a file-level manifest listing every file in the package with its path, size, and optional hash — on top of a valid package (FET_030).

This feature translates the Package Introspection requirements (BOM.2.1–BOM.2.4) from Section 3.2 of the Asset Registry Specification into SimReady Foundation requirements.

### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

| **Property**            | **Value**         |
|-------------------------|-------------------|
|Internal ID              | `FET032_PACKAGING_INTROSPECTION`|

#### Used in Profiles

_No profiles currently include this feature._

#### Requirements (1)

Dependencies:
* [FET_030 Packaging Core](FET_030-packaging_core.md) (v0.1.0) — provides the valid package structure this feature extends

* Capability: [Packaging/Packaging Introspection](../capabilities/packaging/packaging_introspection/capability-packaging_introspection.md)
    * Requirements
        * [BOM Structure](../capabilities/packaging/packaging_introspection/requirements/bom-structure.md)
            * PKG.BOM.001 | version 0.1.0
            * [Rule | Implementation](../capabilities/packaging/packaging_introspection/validation.py)

#### Samples

_No sample packages with BOM available yet._

#### Test Process

* Validate that the BOM lists every file in the package with correct paths
* Verify BOM-level fields (`format_version`, `package_id`) are present and consistent
* Verify item-level fields (`path`, `size`) are present; verify `hash` objects when included
* Verify all paths are unique and use forward-slash-separated relative paths

</details>
