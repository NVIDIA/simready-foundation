# Materials Requirements Overview

To fulfill the requirements of this capability, materials must be properly defined using a portable material specification such as OpenPBR.


## Material Implementation within OpenUSD

```{admonition} Requirement
- **Materials must use valid OpenPBR specifications**
- **Material paths and bindings must be properly scoped and resolvable**
- **Material attributes must comply with their respective schemas**
```

## Schema
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->
Materials is defined with the [UsdShade schema](https://openusd.org/release/api/usd_shade_page_front.html), imlementing OpenPBR via [MaterialX](https://developer.nvidia.com/blog/unlock-seamless-material-interchange-for-virtual-worlds-with-openusd-materialx-and-openpbr/).

### NVIDIA MDL

The capability requires OpenPBR because NVIDIA MDL materials are not considered to be portable. It is permitted for for backwards compatibility, but it is not recommended for new assets.

## Requirements

The requirements listed here can be uniquely identified by their respective identifiers. Validators may refer to these ID's to denote compliance.

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- MATERIALS_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- MATERIALS_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/material-mdl-source-asset
requirements/material-mdl-schema
requirements/material-bind-scope
requirements/material-preview-surface
requirements/material-assignment
requirements/material-shader-inputs
requirements/material-texture-colorspace
requirements/material-texture-maxsize
```
