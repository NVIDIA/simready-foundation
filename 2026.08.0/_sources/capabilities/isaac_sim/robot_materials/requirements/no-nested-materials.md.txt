# no-nested-materials

| Code     | RM.001 |
|----------|--------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Materials must not contain nested materials to avoid unexpected rendering behavior.

## Description

This requirement validates that UsdShade.Material prims don't have child prims that are also materials. Nested materials can cause unexpected rendering behavior and are not supported in many USD-based renderers and simulation environments.

Materials should be organized as direct children of the Looks scope, without any hierarchical nesting of material prims within other material prims.

## Why is it required?

- Prevents unexpected rendering behavior when materials contain nested materials
- Ensures compatibility with USD-based renderers and simulation environments
- Follows USD best practices for material organization
- Avoids ambiguity in material binding resolution

## Examples

```usd
# Invalid: Material with nested material
def Scope "Looks"
{
    def Material "ParentMaterial"
    {
        # Material shaders and properties...
        
        def Material "NestedMaterial"  # Invalid: Nested material
        {
            # This nested material causes issues
        }
    }
}

# Valid: Materials as direct children of Looks
def Scope "Looks"
{
    def Material "Material_01"
    {
        # Material shaders and properties...
    }
    
    def Material "Material_02"
    {
        # Material shaders and properties...
    }
}
```

## How to comply

- Ensure all Material prims are direct children of the Looks scope
- Do not nest Material prims inside other Material prims
- Organize materials in a flat hierarchy under the Looks scope
- Use proper material binding to reference materials from geometry

