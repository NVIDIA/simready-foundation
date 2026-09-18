# materials-on-top-level-only

| Code     | RM.002 |
|----------|--------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

Materials must only be defined in the top-level Looks prim following USD best practices for material organization.

## Description

This requirement validates that all UsdShade.Material prims are direct children of the top-level Looks prim. Materials should be centrally organized in a dedicated Looks scope at the top level of the asset hierarchy, not scattered throughout the prim hierarchy.

This follows USD best practices for material organization and ensures consistent material management across different USD applications and workflows.

## Why is it required?

- Ensures materials are organized in a predictable, standard location
- Facilitates material discovery and management
- Follows USD best practices for asset organization
- Improves asset portability across different USD applications
- Makes material reuse and sharing more straightforward

## Examples

```usd
# Invalid: Material defined outside the top-level Looks prim
def Xform "MyAsset" (
    kind = "component"
)
{
    def Scope "Looks"
    {
        def Material "Material_01"
        {
            # This material is correctly placed
        }
    }
    
    def Xform "SomeGeometry"
    {
        def Material "Material_02"  # Invalid: Material not in top-level Looks
        {
            # This material should be in /MyAsset/Looks instead
        }
        
        def Mesh "mesh_01"
        {
            # Geometry...
        }
    }
}

# Valid: All materials in the top-level Looks prim
def Xform "MyAsset" (
    kind = "component"
)
{
    def Scope "Looks"
    {
        def Material "Material_01"
        {
            # Material definition...
        }
        
        def Material "Material_02"
        {
            # Material definition...
        }
    }
    
    def Xform "SomeGeometry"
    {
        def Mesh "mesh_01" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {
            # Geometry...
            rel material:binding = </MyAsset/Looks/Material_01>
        }
    }
}
```

## How to comply

1. Create a Scope prim named "Looks" as a direct child of the default prim
2. Define all Material prims as direct children of the Looks scope
3. Do not define Material prims anywhere else in the hierarchy
4. Use material bindings to reference materials from geometry prims
5. Ensure the Looks scope is at the top level: `/<DefaultPrim>/Looks`

