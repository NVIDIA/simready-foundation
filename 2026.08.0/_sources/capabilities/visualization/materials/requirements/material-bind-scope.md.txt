# material-bind-scope

| Code     | VM.BIND.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-bind-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

A material binding inside a payload must target a material inside that payload.

This requirement is implemented by `usd-validation-nvidia`, which registers it as
`com.nvidia.usd.VM.BIND.001` and binds it to `MaterialOutOfScopeChecker`. A feature manifest references that
code. The unprefixed code is not bound to a rule in this repository.

## Description

Material bindings must be applied at the appropriate scope in the scene hierarchy. This ensures proper material assignment and inheritance throughout the scene.

When a material binding relationship is defined within a payload, it must target materials that exist within that payload's scope. Bindings to materials outside the payload scope break encapsulation and can cause issues with composition.

## Why is it required?
- A binding target outside the payload resolves to nothing when the payload is loaded on its own
- The material a prim renders with depends on what else is composed into the stage
- An asset that cannot be moved without its surrounding layers is not portable

## Examples

Both blocks are the payload layer, `payload.usda`, which a main layer composes under
`</World/Scene>`.

### Invalid: a binding whose target is outside the payload

```usd
def Xform "Root"
{
    def Mesh "Mesh" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </Material>
    }
}
```

`</Material>` is authored in the main layer, not here. Load this payload on its own and the
binding resolves to nothing.

### Valid: a binding whose target is inside the payload

```usd
def Xform "Root"
{
    def Material "Material"
    {
        token outputs:surface.connect = </Root/Material/Preview.outputs:surface>

        def Shader "Preview"
        {
            uniform token info:id = "UsdPreviewSurface"
            color3f inputs:diffuseColor = (0.18, 0.18, 0.18)
            token outputs:surface
        }
    }

    def Mesh "Mesh" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </Root/Material>
    }
}
```

## How to comply
- Move material definitions into the payload
- Update material bindings to reference materials within the payload scope
- Author material paths relative to the payload root

## For More Information
- [USD Payloads](https://openusd.org/release/api/usd_page_front.html#Usd_Payloads)
- [USD Material Binding](https://openusd.org/release/api/class_usd_shade_material_binding_a_p_i.html)