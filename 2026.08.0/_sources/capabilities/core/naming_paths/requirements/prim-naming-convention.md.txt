# prim-naming-convention

| Code     | NP.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`np-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |

## Summary

Prims shall follow consistent naming conventions

## Description

All prims in a USD asset shall follow consistent naming conventions to ensure readability, maintainability, and compatibility across different tools and platforms. This includes using appropriate prefixes, avoiding special characters, and following camelCase or snake_case conventions consistently.

## Why is it required?

- Ensures consistent asset structure across different environments
- Improves readability and maintainability of USD files
- Prevents issues with tools that have specific naming requirements
- Facilitates automated processing and validation

## Examples

```usd
# Valid: Consistent camelCase naming
def Xform "chairBase" (
    doc = "Base of the chair"
)
{
    def Mesh "seatMesh" (
        doc = "Mesh for the seat"
    )
    {
    }
    
    def Mesh "backrestMesh" (
        doc = "Mesh for the backrest"
    )
    {
    }
}

# Valid: Consistent snake_case naming
def Xform "chair_base" (
    doc = "Base of the chair"
)
{
    def Mesh "seat_mesh" (
        doc = "Mesh for the seat"
    )
    {
    }
    
    def Mesh "backrest_mesh" (
        doc = "Mesh for the backrest"
    )
    {
    }
}

# Invalid: Inconsistent naming
def Xform "chairBase" (
    doc = "Base of the chair"
)
{
    def Mesh "seat_mesh" (  # Mixed camelCase and snake_case
        doc = "Mesh for the seat"
    )
    {
    }
    
    def Mesh "BackrestMesh" (  # Inconsistent capitalization
        doc = "Mesh for the backrest"
    )
    {
    }
}

# Invalid: Special characters and spaces
def Xform "chair base!" (  # Contains space and special character
    doc = "Base of the chair"
)
{
    def Mesh "seat@mesh" (  # Contains special character
        doc = "Mesh for the seat"
    )
    {
    }
}
```

## How to comply

- Choose either camelCase or snake_case and use it consistently throughout the asset
- Use descriptive names that clearly indicate the prim's purpose
- Avoid spaces, special characters, and reserved keywords
- Use appropriate prefixes for different prim types (e.g., "mesh_", "material_", "light_")
- Keep names concise but descriptive
- Follow USD naming conventions for built-in prim types

## For More Information

- [USD Schema Naming Conventions](https://openusd.org/release/api/class_usd_schema_base.html)
- [USD Best Practices - Naming](https://openusd.org/release/tut_usd_best_practices.html#naming)
