# Requirements

## Summary

- **Stage must include a `*Properties.usda` sublayer for AIF metadata.**
- **Default prim must have `aif:core:assetClass` identifying the equipment type.**
- **Default prim must have manufacturer, model number, and asset version identification attributes.**
- **Default prim must have physical dimension attributes.**
- **Default prim must have `aif:core:simreadyVersion` for traceability.**
- **Default prim must have asset description and documentation link attributes.**
- **All equipment-class-specific `aif:spec:*` attributes defined in the equipment schema must be present.**

## Requirements & Recommendations

<!-- AIF_METADATA_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- AIF_METADATA_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/properties-sublayer-required
requirements/asset-class-required
requirements/asset-identification-metadata
requirements/physical-dimensions-metadata
requirements/simready-version-tracking
requirements/asset-description-required
requirements/equipment-class-template-compliance
```
