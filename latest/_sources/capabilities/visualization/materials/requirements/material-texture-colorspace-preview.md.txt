# material-texture-colorspace-preview

| Code     | VM.TEX.003 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

UsdPreviewSurface materials and textures must use correct color space conventions

## Description

A texture holds either a color or data, and the two need opposite treatment: a base color is
sRGB-encoded and must be decoded, a roughness or normal map holds linear values that must be
read as authored.

A `UsdUVTexture` reads its image through `inputs:file`, which is the same attribute for both.
The expectation follows from the surface shader input the texture is connected to, through any
number of intermediate nodes: a normal-map node, a multiply, a node graph interface.

| Surface shader input | Expected `inputs:sourceColorSpace` |
|---|---|
| `diffuseColor`, `emissiveColor`, `specularColor` | `sRGB` |
| every other input, including roughness, metallic, occlusion, opacity, normal and displacement | `raw` |

The color space is `inputs:sourceColorSpace`, a typed shader input on `UsdUVTexture` with
exactly three allowed values, `raw`, `sRGB` and `auto`, which OpenUSD's own reader consults. It
is not `colorSpace` metadata and it does not take `Gf.ColorSpaceNames` tokens, so
`srgb_rec709_scene` is not a legal value here. Where both `inputs:sourceColorSpace` and
`colorSpace` metadata are authored on the same `UsdUVTexture`, the typed attribute is read, and
`sRGB` authored as metadata is accepted as an alias.

A texture connected only to a displacement output, or unconnected in a library graph, is out of
scope.

Whether the image file's encoding matches the declared color space cannot be determined from
the scene description. An sRGB-encoded PNG declaring `raw` is decoded incorrectly, and the USD
holds no evidence of it.

The other three appearance formats declare color space elsewhere, in a different vocabulary,
with a different default. MDL is
[`VM.TEX.002`](/capabilities/visualization/materials/requirements/material-texture-colorspace-mdl)
and OpenPBR is
[`VM.TEX.004`](/capabilities/visualization/materials/requirements/material-texture-colorspace-openpbr);
the [requirements overview](../requirements) states all four side by side.

```{warning}
**A texture reaching a data input MUST declare `raw` when its file has three or four
channels.**

`sourceColorSpace` defaults to `auto`, which OpenUSD defines as: consult the image file's own
gamma or color-space metadata; failing that, treat the texture as `sRGB` if it is 8-bit with
three or four channels, and otherwise not. So an 8-bit RGB or RGBA file is decoded; a 16-bit
PNG, an EXR, or a single-channel 8-bit mask is not.

For a data texture that heuristic is wrong whenever it fires. A roughness map painted in an
image editor and saved as an 8-bit RGB PNG — the ordinary way such a map is produced — is
decoded as though its values were color, and every value is read low:

| Value in the file | Read as, under `auto` | Error |
|---|---|---|
| `0.251` (code 64) | `0.051` | −80% |
| `0.502` (code 128) | `0.216` | −57% |
| `0.878` (code 224) | `0.745` | −15% |

The error differs at each end of the range, so the contrast between rough and smooth areas is
stretched as well as shifted. On a normal map each component is changed by a different amount,
so the vectors no longer point where they were authored and are no longer unit length, which
shows up as lighting that looks like bad geometry.

`auto` is accepted on a data input when the file is single channel, where it already resolves
to `raw`. On a file with three or four channels it decodes, so `raw` has to be declared.
```

`auto` remains acceptable on a color input, where the heuristic agrees with convention: an
8-bit PNG or JPG base color is sRGB-encoded and is decoded, while a 16-bit or float color
texture is usually linear already and is left alone. Declaring `sRGB` still resolves more
predictably, since `auto` resolves per file while `sRGB` and `raw` resolve the same way
everywhere. `auto` also has no counterpart on OpenPBR, where an undeclared color space means no
transform whatever the file is, so an asset with both surfaces declares a color space
explicitly or the same texture is decoded on one and not the other.

## Why is it required?

- A base color texture read as linear renders washed out; a normal map read as sRGB bends
  its directions and the lighting is wrong in a way that looks like bad geometry
- The defect is invisible in the USD text: both cases are a well-formed material with a
  plausible texture path
- A three- or four-channel data texture left to `auto` is the default output of common image
  editors, so it is the ordinary case
- Keeps color handling consistent between the formats a SimReady asset may include, so the
  same asset does not render differently depending on which surface a runtime picks

## Examples

### Valid: a color texture and a data texture each declaring what its signal needs

```usd
def Material "mtl_bracket"
{
    token outputs:surface.connect = </mtl_bracket/Preview.outputs:surface>

    def Shader "BaseColorTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bracket_basecolor.png@
        token inputs:sourceColorSpace = "sRGB"
        float3 outputs:rgb
    }

    def Shader "RoughnessTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bracket_roughness.png@
        token inputs:sourceColorSpace = "raw"
        float outputs:r
    }

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor.connect = </mtl_bracket/BaseColorTex.outputs:rgb>
        float inputs:roughness.connect = </mtl_bracket/RoughnessTex.outputs:r>
        token outputs:surface
    }
}
```

### Invalid: a texture reaching `normal` and declaring `sRGB`

```usd
def Material "mtl_bracket"
{
    token outputs:surface.connect = </mtl_bracket/Preview.outputs:surface>

    def Shader "NormalTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bracket_normal.png@
        token inputs:sourceColorSpace = "sRGB"
        float3 outputs:rgb
    }

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        normal3f inputs:normal.connect = </mtl_bracket/NormalTex.outputs:rgb>
        token outputs:surface
    }
}
```

### Invalid: a texture reaching `diffuseColor` and declaring `raw`

```usd
def Material "mtl_bracket"
{
    token outputs:surface.connect = </mtl_bracket/Preview.outputs:surface>

    def Shader "BaseColorTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bracket_basecolor.png@
        token inputs:sourceColorSpace = "raw"
        float3 outputs:rgb
    }

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor.connect = </mtl_bracket/BaseColorTex.outputs:rgb>
        token outputs:surface
    }
}
```

### Invalid: a three-channel roughness map left to `auto`

An 8-bit RGB PNG saved out of an image editor. `auto` decodes it as sRGB, and the roughness
values are read low across the range. The same map saved as a single-channel file would be
left alone by `auto` and would pass.

```usd
def Material "mtl_bracket"
{
    token outputs:surface.connect = </mtl_bracket/Preview.outputs:surface>

    def Shader "RoughnessTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bracket_roughness.png@
        token inputs:sourceColorSpace = "auto"
        float outputs:r
    }

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        float inputs:roughness.connect = </mtl_bracket/RoughnessTex.outputs:r>
        token outputs:surface
    }
}
```

### Invalid: a token outside the `UsdUVTexture` vocabulary

`linear` is not one of the three values `inputs:sourceColorSpace` takes, so it cannot be
interpreted. A linear data texture declares `raw`.

```usd
def Material "mtl_bracket"
{
    token outputs:surface.connect = </mtl_bracket/Preview.outputs:surface>

    def Shader "RoughnessTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/bracket_roughness.png@
        token inputs:sourceColorSpace = "linear"
        float outputs:r
    }

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        float inputs:roughness.connect = </mtl_bracket/RoughnessTex.outputs:r>
        token outputs:surface
    }
}
```

## How to comply

1. Decide the signal from the surface input the texture drives, not from the texture's file
   name or from the image node's own inputs.
2. Author `inputs:sourceColorSpace = "sRGB"` on every texture reaching `diffuseColor`,
   `emissiveColor` or `specularColor`.
3. Author `inputs:sourceColorSpace = "raw"` on every other texture, unless the file is single
   channel, where `auto` already resolves to `raw`. On a three- or four-channel file `auto`
   decodes, and every value is read low.
4. Use the `UsdUVTexture` vocabulary. `raw`, `sRGB` and `auto` are the only legal values;
   `Gf.ColorSpaceNames` tokens such as `srgb_rec709_scene` belong to `colorSpace` metadata
   and are not read here.
5. Save the texture files in the encoding the value claims. An sRGB-encoded file declaring
   `raw`, or a linear one declaring `sRGB`, is decoded wrongly, and the USD holds no evidence
   of it.

## Accepted values

| Authored | On a color input | On a data input |
|---|---|---|
| `sRGB` | author this | reported |
| `raw` | reported | author this |
| `auto` | accepted | **reported**, unless the file is single channel |
| absent | accepted — the attribute defaults to `auto` | **reported**, unless the file is single channel |
| any other token | reported | reported |

`auto` is accepted on a color input, where the heuristic agrees with convention. On a data
input it is accepted only for a single-channel file, which the heuristic leaves alone, and
reported for a file with three or four channels, which it decodes.

## Related Requirements
- [Material Texture Colorspace](/capabilities/visualization/materials/requirements/material-texture-colorspace-mdl)
- [Material Texture Colorspace MaterialX](/capabilities/visualization/materials/requirements/material-texture-colorspace-openpbr)
- [Material Shader Inputs](/capabilities/visualization/materials/requirements/material-shader-inputs)
- [Material Texture Max Size](/capabilities/visualization/materials/requirements/material-texture-maxsize)

## For More Information
- [OpenUSD Preview Surface Core Nodes](https://openusd.org/release/spec_usdpreviewsurface.html#core-nodes)
- [OpenUSD Color Space API](https://openusd.org/dev/api/class_usd_color_space_a_p_i.html)
