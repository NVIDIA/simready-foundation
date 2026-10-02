# material-preview-surface-specification

| Code     | VM.PS.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-ps-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

UsdPreviewSurface inputs must use the types and token values the specification declares.

This requirement is implemented by `usd-validation-nvidia`, which registers it as
`com.nvidia.usd.VM.PS.001` and binds it to `MaterialUsdPreviewSurfaceChecker`. A feature manifest references that
code. The unprefixed code is not bound to a rule in this repository.

## Description

A `UsdPreviewSurface` shader and the nodes feeding it MUST follow the UsdPreviewSurface
specification:

- An input attribute's value type matches the type the specification declares for it
- A token-valued input holds one of the values the specification lists
- Attributes the specification declares `uniform` hold no time samples

## Why is it required?
- A type the specification does not declare is handled inconsistently across renderers
- A token outside the allowed set falls back to a per-renderer default
- A viewer implementing the specification cannot read the material

## Examples

### Invalid: an input outside the specification, and a colour space outside the allowed tokens

```usd
def Material "mtl_cube"
{
    def Shader "PreviewSurfaceTexture"
    {
        uniform token info:id = "UsdPreviewSurface"
        float inputs:specular.connect = </mtl_cube/SpecularTex.outputs:r>
        token outputs:surface
    }

    def Shader "SpecularTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/specular.png@
        uniform token inputs:sourceColorSpace = "bad"
        float outputs:r
    }
}
```

`UsdPreviewSurface` declares no `specular` input, and `sourceColorSpace` takes `raw`, `sRGB`
or `auto`.

### Invalid: an input of the wrong type, and a token carrying time samples

```usd
def Material "mtl_sphere"
{
    def Shader "Shader"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:metallic = (0.5, 0.5, 0.5)
        token outputs:surface
    }

    def Shader "roughnessTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/roughness.png@
        uniform token inputs:wrapT.timeSamples = {
            0: "invalid_wrap",
            1: "another_invalid"
        }
        float outputs:r
    }
}
```

`UsdPreviewSurface` declares `metallic` as a `float`, and `wrapT` is uniform, so it takes a
single value rather than time samples.

### Valid: every input in the specification, with the declared type

```usd
def Material "mtl_cube"
{
    token outputs:surface.connect = </mtl_cube/PreviewSurfaceTexture.outputs:surface>

    def Shader "PreviewSurfaceTexture"
    {
        uniform token info:id = "UsdPreviewSurface"
        float inputs:clearcoat = 0
        float inputs:clearcoatRoughness = 0
        color3f inputs:diffuseColor.connect = </mtl_cube/diffuseColorTex.outputs:rgb>
        float inputs:displacement = 0
        token outputs:surface
    }

    def Shader "diffuseColorTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/color.png@
        uniform token inputs:sourceColorSpace = "auto"
        uniform token inputs:wrapS = "useMetadata"
        uniform token inputs:wrapT = "useMetadata"
        float3 outputs:rgb
    }
}
```

## How to comply
- Only use [core nodes](https://openusd.org/release/spec_usdpreviewsurface.html#core-nodes) as per the UsdPreviewSurface specification
- Only use allowed inputs and outputs as per the [UsdPreviewSurface specification](https://openusd.org/release/spec_usdpreviewsurface.html)

## For More Information
- [UsdPreviewSurface Specification](https://openusd.org/release/spec_usdpreviewsurface.html)
