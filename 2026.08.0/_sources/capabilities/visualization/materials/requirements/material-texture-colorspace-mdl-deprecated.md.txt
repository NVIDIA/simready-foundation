# material-texture-colorspace-mdl-deprecated

| Code     | VM.TEX.002 |
|----------|---------|
| Validator| {oav-validator-latest-link}`vm-tex-002` |
| Compatibility | {compatibility}`Kit-107.0+`  |
| Tags     | {tag}`correctness` |

## Summary

Deprecated. See VM.TEX.005 for the current requirement.

## Description

`VM.TEX.002` is frozen at the behaviour `FET_006_MDL` 0.1.0 shipped with: a texture input
that authors `colorSpace` must author the value its signal needs, `sRGB` on a color input
and `raw` on a data input. An input that authors no `colorSpace` is not examined.

[`VM.TEX.005`](/capabilities/visualization/materials/requirements/material-texture-colorspace-mdl)
states the current requirement. It covers the same authored values and adds the case this one
leaves out: an input with no `colorSpace` resolves to `auto`, and `auto` decodes an 8-bit
three- or four-channel file as sRGB, which is wrong on a data input.

`FET_006_MDL` 0.1.0 lists `VM.TEX.002`. `FET_006_MDL` 0.2.0 lists `VM.TEX.005`. An asset declaring a profile version that lists 0.1.0 is
subject to this requirement and is unaffected by the addition.

## Why is it required?

- A color texture read as linear renders washed out, and a data texture read as sRGB reports
  values that are too low across the whole map.

## Related Requirements
- [Color Space requirements for MDL](/capabilities/visualization/materials/requirements/material-texture-colorspace-mdl)
- [Color Space requirements for UsdPreviewSurface](/capabilities/visualization/materials/requirements/material-texture-colorspace-preview)
- [Color Space requirements for OpenPBR](/capabilities/visualization/materials/requirements/material-texture-colorspace-openpbr)
