# material-texture-colorspace-openpbr

| Code     | VM.TEX.004 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

OpenPBR materials and textures must use correct color space conventions

## Description

A texture holds either a color or data, and the two need opposite treatment: a base color is
sRGB-encoded and must be decoded, a roughness or normal map holds linear values that must be
read as authored.

A MaterialX image node reads its image through `inputs:file`, which is the same attribute for
both. The expectation follows from the surface shader input the texture is connected to,
through any number of intermediate nodes: a normal-map node, a multiply, a color correct, a
node graph interface.

| Surface shader input | Expected `colorSpace` |
|---|---|
| `base_color`, `specular_color`, `transmission_color`, `subsurface_color`, `coat_color`, `fuzz_color`, `emission_color` | `srgb_texture` |
| every other input, including roughness, metalness, occlusion, opacity, normal and displacement | `none`, or no `colorSpace` authored |

`none` is MaterialX's token for applying no transform, and an unauthored `colorSpace` has the
same effect. `raw` is accepted as an alias for `none`, though it is not a MaterialX token.

An image node is recognised by having an asset-valued `inputs:file`, which every MaterialX
`ND_image_*` and `ND_tiledimage_*` node has, so image node types outside the standard set are
traced as well.

**Where the color space is authored.** When the image node's `inputs:file` is connected to an
interface input on the Material, the `colorSpace` metadata goes on that interface input, which
is where the file value itself lives. When `inputs:file` holds the asset directly, the metadata
goes on the image node's own attribute. Either is read; the rule is that the metadata sits on
the attribute that holds the file.

**The vocabulary is MaterialX's.** MaterialX resolves a color space by building a node name,
`<source>_to_<working>`, where the working space is `lin_rec709`, and looking it up. The names
it can resolve are the ACES 1.2 set. `srgb_texture` is the sRGB member of that set: the sRGB
transfer function over Rec.709 primaries, gamma 2.4 with a linear bias of 0.055. It is not
`g22_rec709`, which is gamma 2.2 with no bias. The
[requirements overview](../requirements) summarises the other formats' vocabularies.

`Gf.ColorSpaceNames` publishes `srgb_rec709_scene` as OpenUSD's canonical name for that same
encoding, but neither RTX nor hdStorm resolves the OpenUSD spelling on this surface: the
mapping between the two vocabularies arrived in MaterialX 1.39.4, and the MaterialX each of
them ships predates it.

```{warning}
**A color texture tagged `srgb_rec709_scene` renders washed out and the asset still loads.**
The spelling causes a lookup for a transform that does not exist, so no transform is inserted
and the base color is consumed without its sRGB decode. The material is otherwise valid.
```

RTX logs an unsupported-transform error for `none`, and for `raw`, which it rewrites before the
lookup. MaterialX defines `none` for "apply no transform" and its own shader generator skips the
lookup for that token; RTX compiles the OpenPBR graph to MDL through its own translator, which
asks for a transform without that exemption. Neither spelling changes the rendered result: a
failed lookup inserts no transform, which is what a data texture needs, so a roughness map
declaring `none` renders correctly and only the log is affected. hdStorm accepts `none`
silently.

Author `none` instead of leaving `colorSpace` unauthored: an absent value is indistinguishable from an
unfinished material.

This requirement applies to textures that reach a surface input. A texture connected only to a
displacement output, or unconnected in a library graph, is out of scope.
Whether the file's actual encoding matches what the declared color space claims cannot be
determined from the USD: an sRGB-encoded PNG left untagged is consumed undecoded, and the USD holds no
evidence of it.

## Why is it required?

- A base color texture consumed without its sRGB decode renders washed out; a normal map put
  through an sRGB decode bends its directions and the lighting is wrong in a way that looks
  like bad geometry
- The defect is invisible in the USD text: both cases are a well-formed material with a
  plausible texture path
- `srgb_rec709_scene` is OpenUSD's published name for the encoding this surface needs, and it
  is the spelling most likely to be authored in its place
- Keeps color handling consistent between the formats a SimReady asset may include, so the
  same asset does not render differently depending on which surface a runtime picks

## Examples

### Valid: `srgb_texture` on the color texture, `none` on the data texture

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "BaseColorTex"
    {
        uniform token info:id = "ND_image_color3"
        asset inputs:file = @./textures/bracket_basecolor.png@ (
            colorSpace = "srgb_texture"
        )
        color3f outputs:out
    }

    def Shader "RoughnessTex"
    {
        uniform token info:id = "ND_image_float"
        asset inputs:file = @./textures/bracket_roughness.png@ (
            colorSpace = "none"
        )
        float outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket/BaseColorTex.outputs:out>
        float inputs:specular_roughness.connect = </mtl_bracket/RoughnessTex.outputs:out>
        token outputs:out
    }
}
```

### Valid: a texture in the same material that no surface input reaches

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "UnusedTex"
    {
        uniform token info:id = "ND_image_color3"
        asset inputs:file = @./textures/bracket_spare.png@
        color3f outputs:out
    }

    def Shader "BaseColorTex"
    {
        uniform token info:id = "ND_image_color3"
        asset inputs:file = @./textures/bracket_basecolor.png@ (
            colorSpace = "srgb_texture"
        )
        color3f outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket/BaseColorTex.outputs:out>
        token outputs:out
    }
}
```

### Warned: a color texture declaring `srgb_rec709_scene`, which is not resolved here

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "BaseColorTex"
    {
        uniform token info:id = "ND_image_color3"
        asset inputs:file = @./textures/bracket_basecolor.png@ (
            colorSpace = "srgb_rec709_scene"
        )
        color3f outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket/BaseColorTex.outputs:out>
        token outputs:out
    }
}
```

### Invalid: a color texture declaring no color space, reached through a multiply node

An absent color space means no transform, so an sRGB-encoded file is consumed undecoded.
On a color input that is a defect; on a data input it is what the channel needs.

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "BaseColorTex"
    {
        uniform token info:id = "ND_image_color3"
        asset inputs:file = @./textures/bracket_basecolor.png@
        color3f outputs:out
    }

    def Shader "Tint"
    {
        uniform token info:id = "ND_multiply_color3"
        color3f inputs:in1.connect = </mtl_bracket/BaseColorTex.outputs:out>
        color3f inputs:in2 = (0.9, 0.9, 1)
        color3f outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket/Tint.outputs:out>
        token outputs:out
    }
}
```

### Invalid: a data texture declaring `srgb_texture`

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "RoughnessTex"
    {
        uniform token info:id = "ND_image_float"
        asset inputs:file = @./textures/bracket_roughness.png@ (
            colorSpace = "srgb_texture"
        )
        float outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float inputs:specular_roughness.connect = </mtl_bracket/RoughnessTex.outputs:out>
        token outputs:out
    }
}
```

## How to comply

1. Decide the signal from the surface input the texture drives, not from the texture's file
   name or from the image node's own inputs.
2. Author `colorSpace = "srgb_texture"` on every texture reaching a color input.
3. Author `colorSpace = "none"` on every other texture, or leave it unauthored. `none` states
   the intent, so it is preferred.
4. Do not author `srgb_rec709_scene`. It is OpenUSD's name for the same encoding, but it is not
   resolved on this surface and the decode is skipped, so the texture renders undecoded. It is
   raised as a warning: the intent is right and the fix is a rename.
5. Save the texture files in the encoding the declared color space claims. An sRGB-encoded
   file left untagged is consumed undecoded, and the USD holds no evidence of it.

## Accepted spellings

"Accepted" means the material compiles without a color-space error.

| Authored | On a color input | On a data input |
|---|---|---|
| `srgb_texture` | author this | reported |
| `none` | reported | author this |
| absent | reported | accepted |
| `raw` | reported | accepted, read as `none` |
| `srgb_rec709_scene` | **warned** — renders undecoded | reported |
| any other token | reported | reported |

`srgb_rec709_scene` on a color input is a warning: it names the right encoding, and the texture
renders undecoded until the spelling is changed.

## Related Requirements
- [Material Texture Colorspace](/capabilities/visualization/materials/requirements/material-texture-colorspace-mdl)
- [Material Texture Colorspace Traced](/capabilities/visualization/materials/requirements/material-texture-colorspace-preview)
- [Material Final Surface](/capabilities/visualization/materials/requirements/material-final-surface)
- [Material Texture Max Size](/capabilities/visualization/materials/requirements/material-texture-maxsize)

## For More Information
- [MaterialX v1.39 specification](https://materialx.org/assets/MaterialX.v1.39.Spec.pdf)
- [ASWF Color Interop Forum](https://github.com/AcademySoftwareFoundation/ColorInterop)
- [OpenUSD Color Space API](https://openusd.org/dev/api/class_usd_color_space_a_p_i.html)
