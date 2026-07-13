# material-texture-colorspace

| Code     | VM.TEX.002 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`correctness` |

## Summary

Each PBR texture channel must use the correct color space.

## Description

Different PBR texture channels require specific color spaces and transformations to ensure physically accurate rendering. Using incorrect color spaces or transformations can lead to incorrect material appearance and unrealistic rendering results. 

Normal maps require special attention:
- They must be in tangent space with values in range [-1, -1, -1] to [1, 1, 1]
- For 8-bit textures (the most common case), specific scale and bias values are required
- Must use "raw" color space to prevent unwanted SRGB transformation

## Why is it required?

- Ensures physically accurate material representation
- Prevents incorrect gamma correction
- Maintains consistency across different renderers
- Required for proper PBR workflow
- Ensures correct normal map interpretation from 8-bit textures

## Examples

### ✅ Valid Example - Correct Color Spaces and Normal Map Settings
```usd
def Material "ValidMaterial"
{
    token outputs:surface.connect = </ValidMaterial/PBRShader.outputs:surface>
    
    def Shader "PBRShader"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor.connect = </ValidMaterial/diffuseTexture.outputs:rgb>
        float inputs:metallic.connect = </ValidMaterial/metallicTexture.outputs:r>
        float inputs:roughness.connect = </ValidMaterial/roughnessTexture.outputs:r>
        normal3f inputs:normal.connect = </ValidMaterial/normalTexture.outputs:rgb>
    }
    
    
    def Shader "metallicTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @textures/metallic.png@
        token inputs:sourceColorSpace = "raw"  # Metallic in linear/raw
        float2 inputs:st.connect = </ValidMaterial/PrimvarReader_st.outputs:result>
    }
    
    def Shader "roughnessTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @textures/roughness.png@
        token inputs:sourceColorSpace = "raw"  # Roughness in linear/raw
        float2 inputs:st.connect = </ValidMaterial/PrimvarReader_st.outputs:result>
    }
    
    def Shader "normalTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @textures/normal.png@  # 8-bit normal map texture
        token inputs:sourceColorSpace = "raw"      # Prevent SRGB transformation
        float4 inputs:scale = (2, 2, 2, 1)        # Required for 8-bit textures
        float4 inputs:bias = (-1, -1, -1, 0)      # Required for 8-bit textures
        float2 inputs:st.connect = </ValidMaterial/PrimvarReader_st.outputs:result>
    }
    
    def Shader "PrimvarReader_st"
    {
        uniform token info:id = "UsdPrimvarReader_float2"
        token inputs:varname = "st"
    }
}
```

```

## How to comply

Required color spaces and settings for PBR channels:
- Base Color/Diffuse: sRGB
- Metallic: Raw/Linear
- Roughness: Raw/Linear
- Normal Maps (8-bit textures): 
  - Must use "raw" sourceColorSpace
  - Must set scale to (2, 2, 2, 1)
  - Must set bias to (-1, -1, -1, 0)
  - These settings convert 8-bit [0,1] range to tangent space [-1,1] range
  - Default normal value when no texture: (0, 0, 1)
- Height/Displacement: Raw
- Opacity: Raw/Linear
- Emission: sRGB

Steps to comply:
1. Set appropriate sourceColorSpace on UsdUVTexture nodes
2. For 8-bit normal maps:
   - Always set sourceColorSpace to "raw"
   - Always set scale to (2, 2, 2, 1)
   - Always set bias to (-1, -1, -1, 0)
3. Ensure texture files are saved in correct color spaces
4. Use appropriate image formats that support the required bit depth
5. Verify color space handling in your content creation tools

## Related Requirements
- [Material PBR Textures](/capabilities/visualization/materials/requirements/material-pbr-textures.md)
- [Material PBR Type](/capabilities/visualization/materials/requirements/material-pbr-type.md)

## For More Information
- [OpenUSD Preview Surface Core Nodes](https://openusd.org/release/spec_usdpreviewsurface.html#core-nodes)
- [OpenUSD Color Space API](https://openusd.org/dev/api/class_usd_color_space_a_p_i.html)