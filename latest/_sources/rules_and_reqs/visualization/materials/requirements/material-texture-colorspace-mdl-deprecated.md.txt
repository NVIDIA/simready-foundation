# MDL texture color space, deprecated

| Code     | VM.TEX.002 |
|----------|---------|
| Validator| {oav-validator-latest-link}`vm-tex-002` |
| Compatibility | {compatibility}`Kit-107.0+`  |
| Tags     | {tag}`correctness` |

## Summary

Deprecated. See VM.TEX.005 for the current requirement.

## Description

`VM.TEX.002` is frozen at the behaviour `FET006_Materials.MDL.0-1-0` 0.1.0 shipped with: a texture input
that authors `colorSpace` must author the value its signal needs: `sRGB` or `raw`
on albedo (`diffuse_texture`), `sRGB` on other color inputs, and `raw` on data inputs. An input that authors no `colorSpace` is not examined.

[`VM.TEX.005`](material-texture-colorspace-mdl.md)
states the current requirement. It covers the same authored values and adds the case this one
leaves out: an input with no `colorSpace` resolves to `auto`, and `auto` decodes an 8-bit
three- or four-channel file as sRGB, which is wrong on a data input.

`FET006_Materials.MDL.0-1-0` lists `VM.TEX.002`. `FET006_Materials.MDL.0-2-0` lists `VM.TEX.005`. An asset declaring a profile version that selects `0-1-0` is
subject to this requirement and is unaffected by the addition.

## Why is it required?

- A color texture read as linear renders washed out, and a data texture read as sRGB reports
  values that are too low across the whole map.

## Related Requirements
- [Color Space requirements for MDL](material-texture-colorspace-mdl.md)
- [Color Space requirements for UsdPreviewSurface](material-texture-colorspace-preview.md)
- [Color Space requirements for OpenPBR](material-texture-colorspace-openpbr.md)
