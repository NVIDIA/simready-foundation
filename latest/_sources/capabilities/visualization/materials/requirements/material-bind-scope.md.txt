# material-bind-scope

| Code     | VM.BIND.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-bind-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

Material bindings must use appropriate scope to ensure proper material assignment and inheritance.

## Description

Material bindings must be applied at the appropriate scope in the scene hierarchy. This ensures proper material assignment and inheritance throughout the scene.

When a material binding relationship is defined within a payload, it must target materials that exist within that payload's scope. Bindings to materials outside the payload scope break encapsulation and can cause issues with composition.

## Why is it required?
- Broken material references
- Composition issues
- Reduced asset portability
- Unreliable material assignments

## Examples

```usd
# Invalid setup:
# Main file (asset.usda):
def Xform "World"
{
    def Xform "Scene" (
        payload = @./payload.usda@  # Loads payload with mesh
    )
    {
    }

    def Material "Material"  # Material defined outside payload
    {
        # ... material definition ...
    }
}

# Payload file (payload.usda):
def Xform "Root"
{
    def Mesh "Mesh" (
        apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </Material>  # Invalid: References material outside payload scope
    }
}

# Valid setup:
# Payload file (payload.usda) should include its own materials or reference materials within its scope:
def Xform "Root"
{
    def Material "Material"
    {
        # ... material definition ...
    }

    def Mesh "Mesh" (
        apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </Root/Material>  # Valid: References material within payload scope
    }
}
```

## How to comply
- Move material definitions into the payload
- Update material bindings to reference materials within the payload scope
- Ensure material paths are relative to the payload root

## For More Information
- [USD Payloads](https://openusd.org/release/api/usd_page_front.html#Usd_Payloads)
- [USD Material Binding](https://openusd.org/release/api/class_usd_shade_material_binding_a_p_i.html)