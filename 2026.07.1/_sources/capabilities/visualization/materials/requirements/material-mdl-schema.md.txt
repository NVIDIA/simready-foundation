# material-mdl-schema

| Code     | VM.MDL.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-mdl-002` |
| Compatibility | {compatibility}`Kit-107.0+`  |
| Tags     | {tag}`correctness` |

## Summary

MDL Shaders must standard OpenUSD shader source attributes to ensure compatibility.

## Description

Materials must use the current MDL shader schema format. The old schema format where `info:implementationSource = "mdlMaterial"` is used with separate `module` and `name` attributes is deprecated and should not be used.

## Why is it required?
- Compatibility issues in applications that support MDL materials with OpenUSD


## Examples

```usd
# Invalid: Using deprecated MDL schema format
def Material "mtl_test"
{
    token outputs:surface.connect = </mtl_test/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "mdlMaterial"  # Deprecated
        custom asset module = @OmniPBR.mdl@  # Old way of specifying MDL module
        custom string name = "OmniPBR"  # Old way of specifying material name
        token outputs:out
    }
}

# Valid: Using current MDL schema format
def Material "mtl_test"
{
    token outputs:surface.connect = </mtl_test/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./OmniPBR.mdl@
        uniform token info:mdl:materialType = "OmniPBR"
        token outputs:out
    }
}
```

## How to comply
- Use the "Asset Validator" extension in NVIDIA Omniverse to update existing assets. See [Asset Validator](https://docs.omniverse.nvidia.com/kit/docs/asset-validator/latest/source/extensions/omni.asset_validator.core/docs/rules.html#omni.asset_validator.core.ShaderImplementationSourceChecker) for more information.
- Update to use `info:implementationSource = "sourceAsset"`
- Use `info:mdl:sourceAsset` instead of `module`
- Use `info:mdl:materialType` instead of `name`
- Convert any materials using the old schema format

## For More Information
- [MDL Material Documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/materials_release-notes.html)