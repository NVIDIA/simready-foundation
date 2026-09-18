# material-shader-inputs

| Code     | VM.BIND.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-bind-002` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

Shader inputs must have correct types matching their shader specification to ensure proper material behavior and prevent runtime errors.

## Description

All shader inputs must conform to their specification-defined types. This requirement validates that:

- **MDL Shader Inputs**: Input types match the MDL module parameter definitions
- **Built-in Shader Inputs**: Input types match the Shader Definition Registry (SDR) specifications
- **Float Values**: No invalid values (NaN or Infinity) are present

Type mismatches can cause:
- Rendering failures or incorrect visual output
- Runtime errors in simulation environments
- Data corruption when materials are processed
- Unpredictable shader behavior

The validator checks both MDL-based shaders (using `info:mdl:sourceAsset`) and built-in shaders (using `info:id`) against their respective specifications.

## Why is it required?
- Prevents runtime errors from type mismatches
- Ensures predictable shader behavior
- Maintains data integrity throughout the pipeline
- Enables reliable material interchange between tools
- Catches authoring errors early in the asset creation process
- Prevents invalid numerical values that can break rendering

## Examples

```usd
# Invalid: Type mismatch in shader input
def Material "InvalidMaterial"
{
    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # Incorrect: diffuse_texture expects asset type, not string
        string inputs:diffuse_texture = "./textures/albedo.png"
        
        # Incorrect: metallic expects float, not int
        int inputs:metallic = 1
    }
}

# Invalid: NaN or Inf values in float inputs
def Material "InvalidFloatMaterial"
{
    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # Incorrect: Invalid float value
        float inputs:roughness = nan
    }
}

# Valid: Correct types matching specification
def Material "ValidMaterial"
{
    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # Correct: asset type for texture
        asset inputs:diffuse_texture = @./textures/albedo.png@
        
        # Correct: float type for metallic
        float inputs:metallic = 1.0
        
        # Correct: float type for roughness with valid value
        float inputs:roughness = 0.5
    }
}

# Valid: Built-in UsdPreviewSurface shader
def Material "PreviewMaterial"
{
    def Shader "Surface"
    {
        uniform token info:id = "UsdPreviewSurface"
        
        # Correct types according to UsdPreviewSurface spec
        color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
        float inputs:metallic = 0.0
        float inputs:roughness = 0.5
    }
}
```

## How to comply

### For MDL Shaders:
- Verify input types against the MDL module specification
- Use the correct USD/Sdf type for each parameter (e.g., `asset`, `float`, `color3f`)
- Ensure `info:mdl:sourceAsset` points to a valid MDL file
- Include the `info:mdl:sourceAsset:subIdentifier` attribute

### For Built-in Shaders:
- Follow the shader's specification (e.g., UsdPreviewSurface specification)
- Use correct attribute types as defined in the shader registry
- Reference official USD documentation for built-in shader types

### General:
- Avoid NaN or Infinity values in float inputs
- Use appropriate numeric ranges for parameters
- Test materials in the target rendering environment
- Validate assets using the asset validator tool

## For More Information
- [USD Shader Documentation](https://openusd.org/release/api/class_usd_shade_shader.html)
- [UsdPreviewSurface Specification](https://openusd.org/release/spec_usdpreviewsurface.html)
- [MDL Specification](https://www.nvidia.com/en-us/design-visualization/technologies/material-definition-language/)
- [USD Value Types](https://openusd.org/release/api/sdf_page_front.html#sdf_value_types)
