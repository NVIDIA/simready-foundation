# Requirements

## Summary

**Robot Materials** ensures that materials are properly organized and structured for robot assets in Isaac Sim environments, following USD best practices for material organization.

This capability ensures:
- **Materials must not contain nested materials**
- **Materials must only be defined in the top-level Looks prim**

## Schema / OpenUSD Specification
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->

Robot Materials utilizes the following USD schemas that are part of the core OpenUSD specification:

- [USD Shade Material Documentation](https://openusd.org/release/api/usd_shade_page_front.html)
- [USD Material Binding](https://openusd.org/release/api/class_usd_shade_material_binding_a_p_i.html)

## Requirements

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- ROBOT_MATERIALS_REQUIREMENTS_LIST_START -->
<!-- ROBOT_MATERIALS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/no-nested-materials
requirements/materials-on-top-level-only
```

