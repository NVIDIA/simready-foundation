# material-preview-surface-specification

| Code     | VM.PS.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-ps-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

Material attributes must comply with the UsdPreviewSurface specification to ensure consistent rendering and viewer compatibility.

## Description

All material attributes must strictly follow the UsdPreviewSurface specification, including:
- Parameter types must match the specification
- Token values must be from the allowed set
- Certain attributes must not contain time samples

## Why is it required?
- Inconsistent material behavior
- Rendering artifacts
- Incompatibility with USD viewers

## Examples

```usd
# Invalid: Non-compliant attributes
def Material "mtl_cube"
{
    def Shader "PreviewSurfaceTexture"
    {
        # Invalid: 'specular' connection not in specification
        float inputs:specular.connect = </World/Looks/mtl_cube/SpecularTex.outputs:r>
    }

    def Shader "diffuseColorTex"
    {
        # Invalid: 'bad' not in allowed tokens ['raw', 'sRGB', 'auto']
        uniform token inputs:sourceColorSpace = "bad"
    }
}

# Invalid: Wrong type and time-sampled tokens
def Material "mtl_sphere"
{
    def Shader "Shader"
    {
        # Invalid: Wrong type (color3f instead of float)
        color3f inputs:metallic = (0.5, 0.5, 0.5)
    }

    def Shader "roughnessTex"
    {
        # Invalid: Token attribute should not have time samples
        uniform token inputs:wrapT.timeSamples = {
            0: "invalid_wrap",
            1: "another_invalid"
        }
    }
}

# Valid: Compliant attributes
def Material "mtl_cube"
{
    token outputs:surface.connect = </World/Looks/mtl_cube/PreviewSurfaceTexture.outputs:surface>

    def Shader "PreviewSurfaceTexture"
    {
        uniform token info:id = "UsdPreviewSurface"
        float inputs:clearcoat = 0
        float inputs:clearcoatRoughness = 0
        color3f inputs:diffuseColor = (0.18, 0.18, 0.18)
        color3f inputs:diffuseColor.connect = </World/Looks/mtl_cube/diffuseColorTex.outputs:rgb>
        float inputs:displacement = 0
        float inputs:metallic.connect = </World/Looks/mtl_cube/metallicTex.outputs:r>
        normal3f inputs:normal.connect = </World/Looks/mtl_cube/normalTex.outputs:rgb>
        float inputs:roughness.connect = </World/Looks/mtl_cube/roughnessTex.outputs:r>
        token outputs:surface
    }

    def Shader "diffuseColorTex"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/color.jpg@
        string inputs:sourceColorSpace = "auto" (
            allowedTokens = ["auto", "raw", "sRGB"]
        )
        string inputs:wrapS = "useMetadata" (
            allowedTokens = ["black", "clamp", "repeat", "mirror", "useMetadata"]
        )
        string inputs:wrapT = "useMetadata" (
            allowedTokens = ["black", "clamp", "repeat", "mirror", "useMetadata"]
        )
        float2 inputs:st.connect = </World/Looks/mtl_cube/st.outputs:result>
        color3f outputs:rgb
    }
}
```

## How to comply
- Only use [core nodes](https://openusd.org/release/spec_usdpreviewsurface.html#core-nodes) as per the UsdPreviewSurface specification
- Only use allowed inputs and outputs as per the [UsdPreviewSurface specification](https://openusd.org/release/spec_usdpreviewsurface.html)

## For More Information
- [UsdPreviewSurface Specification](https://openusd.org/release/spec_usdpreviewsurface.html)
