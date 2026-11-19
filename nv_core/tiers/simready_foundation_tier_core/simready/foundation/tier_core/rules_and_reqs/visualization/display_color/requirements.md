# Display Color Requirements

## Summary

- **Every renderable geometry prim must resolve a display colour, authored on the prim or inherited from an ancestor.**
- **Authored display colour values must lie within the range a consumer can interpret.**
- **Display opacity, where authored, must lie within its valid range.**

## Schema
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->
Display colour is defined with the [UsdGeomGprim schema](https://openusd.org/release/api/class_usd_geom_gprim.html) as the `primvars:displayColor` (`color3f[]`) and `primvars:displayOpacity` (`float[]`) primvars, and resolved through the [UsdGeomPrimvarsAPI](https://openusd.org/release/api/class_usd_geom_primvars_a_p_i.html).

Colour space is resolved through the attribute's `colorSpace` metadata, then [UsdColorSpaceAPI](https://openusd.org/release/api/class_usd_color_space_a_p_i.html) on the prim and its ancestors. Where none is authored, values are in the OpenUSD default, Linear Rec.709 (`lin_rec709_scene`). See DISP.002.

## Requirements

The requirements listed here can be uniquely identified by their respective identifiers. Validators may refer to these ID's to denote compliance.

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- DISPLAY_COLOR_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- DISPLAY_COLOR_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/display-color-coverage
requirements/display-color-values
requirements/display-opacity-values
```
