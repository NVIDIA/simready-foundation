# Feature: `ID:002 - Posable Bodies - Base`

| **Property**            | **Value**                   |
|-------------------------|-----------------------------|
|Internal ID              | `FET002_BASE_NEUTRAL`       |
| Proprietary Techs       | `None`                      |
| Dependency              | `None`                      |

## Description
This feature describes the minimal requirements necessary to have assets in space that can be posed. This is the basis for animations that have the ability to animate via USD time samples.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Neutral Format
### Version 0.1.0
<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is not currently used in any profiles.

#### Requirements
* Capability [Hierarchy](../capabilities/hierarchy/capability-hierarchy.md)
    * Requirements
        * [Exclusive-Xform-Parent-For-UsdGeom](../capabilities/hierarchy/requirements/exclusive-xform-parent-for-usdgeom.md)
            * HI.002  | Version 0.1.0
            * Description
                * Requirement that a UsdGeomPrim always has a parent xform.
                * Xform parent has at least one xformop:translate and one xformop: orient.  (xformop:scale is optional)
                * Xform parent only has 1 UsdGeomPrim as it's child.
                * If referencePrim has authored reference, then we need to check the heiarchy of the reference to make sure the heiarchy still complies with above requirement.
            * [Rule | Implementation](../capabilities/hierarchy/validation.py)

        * [Hierarchy-Has-Root](../capabilities/hierarchy/requirements/hierarchy-has-root.md)
            * HI.004 | Version 0.1.0
            * Description
                * We don't want scattered referencePrims (xforms)...requirement is to ensure that the reference prim (xforms) all route to a single root or ancestor referencePrim (xform).
            * [Rule | Implementation](../capabilities/hierarchy/validation.py)



* Capability: [Visualization/Geometry](../capabilities/visualization/geometry/capability-geometry.md)
    * Requirements
        * [At-Least-One-Imageable-Geometry](../capabilities/visualization/geometry/requirements/at-least-one-imageable-geometry.md)
        * VG.001 | Version 0.1.0
        * [Rule | Implementation](../capabilities/visualization/geometry/validation.py)

        
#### Test Process

This feature is verified by the `simready-benchmark` benchmark suite. Refer to the
[SimReady Benchmark guide](../guides/benchmark/benchmark.md).

</details>

---
#### Comments
