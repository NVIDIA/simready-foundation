# material-mdl-schema

| Code     | VM.MDL.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-mdl-002` |
| Compatibility | {compatibility}`Kit-107.0+`  |
| Tags     | {tag}`correctness` |

## Summary

An MDL shader must use the current schema attributes, not the deprecated `mdlMaterial` form.

This requirement is implemented by `usd-validation-nvidia`, which registers it as
`com.nvidia.usd.VM.MDL.002` and binds it to `MaterialOldMdlSchemaChecker`. A feature manifest references that
code. The unprefixed code is not bound to a rule in this repository.

## Description

Materials must use the current MDL shader schema format. The old schema format where `info:implementationSource = "mdlMaterial"` is used with separate `module` and `name` attributes is deprecated and should not be used.

## Why is it required?
- An application reading the current schema finds no shader source on a prim using the deprecated form


## Examples

### Invalid: the deprecated MDL schema

```usd
def Material "mtl_test"
{
    token outputs:surface.connect = </mtl_test/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "mdlMaterial"
        custom asset module = @./OmniPBR.mdl@
        custom string name = "OmniPBR"
        token outputs:out
    }
}
```

`module` and `name` are custom attributes the deprecated schema used to name the MDL module
and the material inside it.

### Valid: the current MDL schema

```usd
def Material "mtl_test"
{
    token outputs:surface.connect = </mtl_test/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
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