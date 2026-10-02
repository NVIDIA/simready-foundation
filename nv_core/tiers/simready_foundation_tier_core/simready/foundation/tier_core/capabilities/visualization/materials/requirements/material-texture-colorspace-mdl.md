# material-texture-colorspace-mdl

| Code     | VM.TEX.005 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

MDL materials and textures must use correct color space conventions

## Description

A texture holds either a color or data, and the two need opposite treatment. A base color is
sRGB-encoded and has to be decoded before it is used; a roughness, metalness or normal map holds
values that have to be read as authored.

An MDL shader names its texture inputs for what they hold: `diffuse_texture` is a color,
`normalmap_texture` is not. MDL has no separate texture node, so the `colorSpace` metadata
stating which of the two a texture holds sits on the shader's own `asset inputs:*` attribute.
Those texture inputs, meaning an `inputs:` attribute of type `asset` on a shader prim, are what
this requirement reads. Color-space metadata elsewhere, such as on a `primvars:displayColor` on
a `Mesh`, states the encoding of a value outside this scope.

A normal map holds a direction, so it declares `raw` and no sRGB transform is applied to it.
Tangent space and the 8-bit scale-and-bias convention belong to the `UsdUVTexture` reader and
are not checked here.

Three values are valid: `sRGB`, `raw` and `auto`. An MDL texture input without `colorSpace`
metadata defaults to `auto`.

`auto` resolves against the image file. Where the file holds its own color-space metadata,
that metadata applies. Where it does not, an 8-bit image with three or four channels is decoded
as sRGB, and every other image is read as raw.

A color texture may therefore rely on the default. A data texture may not. Image editors write
8-bit RGB as a matter of course, so a roughness, metalness or occlusion map without `colorSpace`
metadata is decoded as though it held color, and every value is read low. Data textures declare
`raw`.

High bit depths and single-channel files fall outside the sRGB branch of that resolution. A
16-bit PNG, an EXR or a single-channel 8-bit mask reads as raw under `auto`, so `auto` is
accepted on a single-channel data texture.

The [requirements overview](../requirements) states the color-space conventions of all four
appearance formats side by side.

## Why is it required?

- A base color texture read as linear renders washed out; a roughness or occlusion map read
  as sRGB is read low across its range and the surface responds wrongly
- The defect is invisible in the USD text: a well-formed material with a plausible texture path
- `auto` resolves from the file's bit depth and channel count, not from the input it feeds, so
  a data texture left on the default is decoded the way a color texture is
- An 8-bit RGB data texture is the default output of common image editors, so this is the
  ordinary case
- Keeps color handling consistent across the formats a SimReady asset may include, so the same
  asset does not render differently depending on which surface a runtime picks

## Examples

The color space is `colorSpace` metadata on the texture input itself, in parentheses after
the value. The `inputs:sourceColorSpace` attribute states the same thing in a different
vocabulary on `UsdUVTexture`, a shader class this requirement does not cover.

### Valid: each texture input declares the color space its signal needs

```usd
def Material "mtl_bracket"
{
    token outputs:mdl:surface.connect = </mtl_bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"

        asset inputs:diffuse_texture = @./textures/bracket_basecolor.png@ (
            colorSpace = "sRGB"
        )
        asset inputs:emissive_color_texture = @./textures/bracket_emissive.png@ (
            colorSpace = "sRGB"
        )
        asset inputs:reflectionroughness_texture = @./textures/bracket_roughness.png@ (
            colorSpace = "raw"
        )
        asset inputs:metallic_texture = @./textures/bracket_metallic.png@ (
            colorSpace = "raw"
        )
        asset inputs:normalmap_texture = @./textures/bracket_normal.png@ (
            colorSpace = "raw"
        )
        token outputs:out
    }
}
```

### Invalid: a data texture declaring `sRGB`

```usd
def Material "mtl_bracket"
{
    token outputs:mdl:surface.connect = </mtl_bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"

        asset inputs:normalmap_texture = @./textures/bracket_normal.png@ (
            colorSpace = "sRGB"
        )
        token outputs:out
    }
}
```

### Invalid: a color texture declaring `raw`

```usd
def Material "mtl_bracket"
{
    token outputs:mdl:surface.connect = </mtl_bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"

        asset inputs:diffuse_texture = @./textures/bracket_basecolor.png@ (
            colorSpace = "raw"
        )
        token outputs:out
    }
}
```

### Invalid: a color space outside the vocabulary

`linear` is neither a `Gf.ColorSpaceNames` name nor one of the accepted aliases, so it cannot
be interpreted. The value a linear data texture declares is `raw`.

```usd
def Material "mtl_bracket"
{
    token outputs:mdl:surface.connect = </mtl_bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"

        asset inputs:reflectionroughness_texture = @./textures/bracket_roughness.png@ (
            colorSpace = "linear"
        )
        token outputs:out
    }
}
```

## How to comply

A texture input holds a color signal or a data signal, and the color space follows from
which:

| Signal | Color space | Inputs |
|---|---|---|
| Color | `sRGB` | `diffuse_texture`, `emissive_color_texture`, and on OmniGlass `glass_color_texture` and `reflection_color_texture` |
| Data | `raw` | every other texture input, including roughness, metalness, ambient occlusion, ORM, opacity, emissive mask, and normal and detail-normal maps |

Steps to comply:

1. Author `colorSpace` metadata on each `asset inputs:*` texture input of the MDL shader.
2. Use `sRGB` for the color inputs listed and `raw` for every other texture input.
3. Set `raw` on every data texture whose file has three or four channels. `auto` decodes
   those whichever input they feed. On a single-channel file `auto` already resolves to `raw`.
4. Save the texture files in the encoding the declared color space claims: an sRGB-encoded file tagged
   `raw`, or a linear file tagged `sRGB`, is decoded wrongly, and the USD holds no evidence
   of it.

## Accepted values

| Authored | On a color input | On a data input |
|---|---|---|
| `sRGB` | author this | reported |
| `raw` | reported | author this |
| `auto` | accepted | **reported**, unless the file is single channel |
| absent | accepted — resolves as `auto` | **reported**, unless the file is single channel |
| `srgb_rec709_scene` | accepted | reported |
| `srgb_texture` | accepted | reported |
| `none` | reported | accepted |
| any other token | reported | reported |

A color space outside these values cannot be interpreted and is reported.

## Related Requirements
- [Color Space requirements for UsdPreviewSurface](/capabilities/visualization/materials/requirements/material-texture-colorspace-preview)
- [Color Space requirements for OpenPBR](/capabilities/visualization/materials/requirements/material-texture-colorspace-openpbr)
- [Material Shader Inputs](/capabilities/visualization/materials/requirements/material-shader-inputs)
- [Material Texture Max Size](/capabilities/visualization/materials/requirements/material-texture-maxsize)

## For More Information
- [OpenUSD Preview Surface Core Nodes](https://openusd.org/release/spec_usdpreviewsurface.html#core-nodes)
- [OpenUSD Color Space API](https://openusd.org/dev/api/class_usd_color_space_a_p_i.html)