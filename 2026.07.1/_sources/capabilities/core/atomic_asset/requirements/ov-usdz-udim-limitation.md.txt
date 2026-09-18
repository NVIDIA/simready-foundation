# ov-usdz-udim-limitation

| Code     | AA.OV.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`aa-ov-001` |
| Compatibility | {compatibility}`kit` |
| Tags     | {tag}`limitation` |

## Summary

Texture UDIMs are not supported in USDZ files in NVIDIA Omniverse

## Description

NVIDIA Omniverse currently (kit 107.0.3) does not support texture tiles (UDIMs) in USDZ files.

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

        token outputs:surface
    }
    
    def Shader "diffuseTexture"
    {
        uniform token info:id = "UsdUVTexture"
        asset inputs:file = @./textures/diffuse.<UDIM>.png@  # Not supported in USDZ in Omniverse
        float2 inputs:st.connect = </MyMaterial/stReader.outputs:result>
        token outputs:rgb
    }

}

```

## How to comply

- Do not use UDIMs in your textures.
- Use USDGeomSubset grouping to assign multiple materials to subsets of geometry instead.

## For More Information

- Contact NVIDIA Omniverse support for more information.