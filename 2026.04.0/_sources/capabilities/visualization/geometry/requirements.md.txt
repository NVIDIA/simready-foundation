# Requirements

## Summary

- **An Asset needs to include at least one USDGeom primitive with a computed purpose of "render" or "default".**
- **The USDGeom prim must have a valid topology.**
- **The USDGeom primitive should not create performance issues for raytraced rendering and simulation.**

## Schema
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->
Geometry is defined with the [USDGeom schema](https://openusd.org/release/api/usd_geom_page_front.html).

## Requirements & Recommendations
<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- GEOMETRY_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- GEOMETRY_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/at-least-one-imageable-geometry
requirements/geom-shall-be-mesh
requirements/usdgeom-extent
requirements/usdgeom-mesh-tessellation-density
requirements/usdgeom-mesh-empty-spaces
requirements/usdgeom-mesh-internal-geometry
requirements/usdgeom-mesh-primitive-tessellation
requirements/usdgeom-boundable-size
requirements/usdgeom-boundable-size-rtx-limit
requirements/usdgeom-mesh-overlap
requirements/usdgeom-mesh-coincident
requirements/usdgeom-mesh-small
requirements/usdgeom-mesh-primvar-indexing
requirements/usdgeom-mesh-subdivision
requirements/usdgeom-mesh-unused-topology
requirements/usdgeom-mesh-primvar-usage
requirements/usdgeom-mesh-colocated-points
requirements/usdgeom-mesh-zero-area
requirements/usdgeom-mesh-manifold
requirements/usdgeom-mesh-topology
requirements/usdgeom-mesh-triangulation
requirements/usdgeom-mesh-identical-timesamples
requirements/usdgeom-mesh-normals-exist
requirements/usdgeom-mesh-normals-must-be-valid
requirements/usdgeom-mesh-winding-order
requirements/usdgeom-mesh-transparent-is-watertight
requirements/usdgeom-pointbased-points-precision
requirements/asset-origin-positioning
requirements/asset-pivot-placement
requirements/mesh-xform-positioning
requirements/identical-mesh-consistency
```
