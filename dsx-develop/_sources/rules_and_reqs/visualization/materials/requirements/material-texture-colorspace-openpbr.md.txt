# OpenPBR texture color space

| Code     | VM.TEX.004 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

A texture's `colorSpace` must match how its OpenPBR input reads the image.

## Description

A texture holds either a color or data, and the two need opposite treatment. A base color is
sRGB-encoded and needs a color space transform to the working space. A roughness or normal map
holds linear values and needs none.

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

**Where `colorSpace` is authored.** On the `asset` attribute that holds the texture path:
`inputs:file` on the image node, or the Material interface input that `inputs:file` is
connected to.

**Color space names.** OpenUSD and MaterialX name this encoding differently —
`srgb_rec709_scene` and `srgb_texture`. Author `srgb_texture`. MaterialX applies a color space
transform only for a name it defines: `srgb_texture` in every version, `srgb_rec709_scene` from
1.39.4. An earlier MaterialX applies no transform to a texture declaring `srgb_rec709_scene`,
and the shader receives its encoded values as linear.

A color texture with no transform applied renders washed out. The material remains valid and
the asset loads.

Author `none` on a data texture instead of leaving `colorSpace` unauthored. Both leave the
texture untransformed; an unauthored value is indistinguishable from an unfinished material.

This requirement covers textures connected to a surface input. A texture connected only to a
displacement output, or unconnected in a library graph, is out of scope. Whether the file's
encoding matches its declared `colorSpace` cannot be determined from the USD.

## Why is it required?

- A color texture with no transform applied renders washed out; a data texture with an sRGB
  transform applied holds altered values, and a normal map's direction vectors bend so the
  lighting reads as bad geometry
- Neither is visible in the USD: both are a well-formed material with a resolvable texture
  path
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

An absent color space means no transform, so an sRGB-encoded file is sampled as linear.
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
4. Do not author `srgb_rec709_scene`. It names the same encoding, and MaterialX defines it
   from 1.39.4, so an earlier version applies no transform. Reported as a warning: the value
   is right and the fix is a rename.
5. Save each texture file in the encoding its declared `colorSpace` states. A file saved in a
   different encoding than it declares cannot be detected from the USD.

## Accepted spellings

"Accepted" means the material compiles without a color-space error.

| Authored | On a color input | On a data input |
|---|---|---|
| `srgb_texture` | author this | reported |
| `none` | reported | author this |
| absent | reported | accepted |
| `raw` | reported | accepted, read as `none` |
| `srgb_rec709_scene` | **warned** — no transform applied | reported |
| any other token | reported | reported |

`srgb_rec709_scene` on a color input is a warning: the value names the right encoding, and no
transform is applied until it is renamed.

## Related Requirements
- [Material Texture Colorspace](material-texture-colorspace-mdl.md)
- [Material Texture Colorspace Traced](material-texture-colorspace-preview.md)
- [Material Final Surface](material-final-surface.md)
- [Material Texture Max Size](material-texture-maxsize.md)

## For More Information
- [MaterialX v1.39 specification](https://materialx.org/assets/MaterialX.v1.39.Spec.pdf)
- [ASWF Color Interop Forum](https://github.com/AcademySoftwareFoundation/ColorInterop)
- [OpenUSD Color Space API](https://openusd.org/dev/api/class_usd_color_space_a_p_i.html)
