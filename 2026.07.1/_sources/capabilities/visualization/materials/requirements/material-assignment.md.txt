# material-assignment

| Code     | VM.MAT.001 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`essential` |

## Summary

Each renderable GPrim must have a computed material bound to it

## Description

This requirement ensures that all geometry in the scene has proper materials for visualization. Each GPrim must have an explicitly assigned or inherited material to ensure consistent and accurate rendering.

- Every GPrim must have a material assigned either directly or through inheritance
- Default materials are not sufficient - explicit assignment is required

## Why is it required?

- Geometry without material assignments will not render predictably - different renderers have different default behaviors.

## Examples

### ✅ Valid Example
```usd
def "MyAsset" (
    kind = "component"
)
{
    def Scope "Materials" () {
        def Material "DefaultMat"
        {
            token outputs:surface.connect = </MyAsset/Materials/DefaultMat/PBRShader.outputs:surface>
            
            def Shader "PreviewSurface"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0.18, 0.18, 0.18)
            }
        }
    }

    def Scope "Geometry" () {
        def Mesh "Cube" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {
            rel material:binding = </MyAsset/Materials/DefaultMat>
        }
    }
}
```

### ❌ Invalid Example
```usd
def "MyAsset" (
    kind = "component"
)
{
    def Mesh "Cube"  # No material binding
    {
        # Missing material assignment
    }
}
```

## For more information

- [MaterialBindingAPI](https://openusd.org/dev/api/class_usd_shade_material_binding_a_p_i.html)
- [UsdPreviewSurface Specification](https://openusd.org/release/spec_usdpreviewsurface.html)

## How to comply

- Use the MaterialBindingAPI to assign materials to geometry
- Ensure material assignments are valid and resolvable
- Check for material inheritance through ancestor prims
- Verify material computability at all times 