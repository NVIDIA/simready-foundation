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
<!-- HIERARCHY_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- HIERARCHY_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/hierarchy-has-root
requirements/exclusive-xform-parent-for-usdgeom
requirements/root-is-xformable
requirements/stage-has-default-prim
requirements/logical-geometry-grouping
requirements/xform-common-api-usage
requirements/placeable-posable-are-xformable
requirements/dummy-requirement
requirements/kinematic-chain-hierarchy
requirements/undefined-prims
```
