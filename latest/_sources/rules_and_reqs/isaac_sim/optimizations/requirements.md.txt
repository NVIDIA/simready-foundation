# Requirements

## Summary

- **No two dynamic rigid bodies may be joined by an unbreakable fixed joint, unless one of them is a separately simulated endpoint.**
- **No rigid body may own two or more mergeable visual meshes.**
- **Renderable prims with no active collision shape may not retain collision API schemas.**
- **Materials must have no connected MaterialX render-context outputs.**

Checks inspect the composed stage's standard USD physics, geometry, and material
data.

## Schema

Checks read applied API schemas, prim types, collision and mass properties,
purpose, visibility, and `UsdShade` connections. Runtime-specific schema tokens
are inspected without loading their plugins.

## Requirements & Recommendations
<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- OPTIMIZATIONS_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- OPTIMIZATIONS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/fixed-joint-no-mergeable-body-pair
requirements/rigid-body-no-multiple-visual-meshes
requirements/render-only-no-inactive-collision-schemas
requirements/material-no-materialx-render-context
```
