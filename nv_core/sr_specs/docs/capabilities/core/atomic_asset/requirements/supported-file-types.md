# supported-file-types

| Code     | AA.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`aa-002` |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`correctness` |

## Summary

Asset must use only supported file types

## Description

For maximum portability, assets must use only file types that are widely supported across platforms. This includes specific formats for USD files, images, and audio.

## Why is it required?

- Supports loading assets on different platforms
- Prevents compatibility issues with unsupported formats
- Enables direct consumption without conversion

## Examples

```usd
# Valid: Using supported file types
def Material "MyMaterial"
{
    token outputs:surface.connect = </MyMaterial/PBRShader.outputs:surface>
    
    def Shader "PBRShader"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor.connect = </MyMaterial/diffuseTexture.outputs:rgb>
        float inputs:roughness.connect = </MyMaterial/roughnessTexture.outputs:r>

        token outputs:surface
    }
    
    def Shader "diffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/diffuse.png@  # Supported format
        float2 inputs:st.connect = </MyMaterial/stReader.outputs:result>
        token outputs:rgb
    }
    
    def Shader "roughnessTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/roughness.png@  # Supported format
        token outputs:r
    }
}

```

```usd
# Invalid: Using unsupported file types
def Shader "roughnessTexture"
{
    uniform token info:id = "UsdUVTexture"
    asset inputs:file = @./textures/roughness.tga@  # Unsupported format
    token outputs:r
}

```

## How to comply

Use only the following file types:
- USD files: usda, usdc, usd, usdz
- Image files: png, jpeg/jpg, exr
- Audio files: M4A, MP3, WAV

## For More Information

- [USDZ File Format Specification - File Types](https://openusd.org/release/spec_usdz.html#file-types)