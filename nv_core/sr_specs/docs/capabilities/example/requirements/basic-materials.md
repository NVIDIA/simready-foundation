# basic-materials

| Code     | EX.002 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

Each mesh must bind a material named `basic_material`.

## Description

This example requirement demonstrates using generated requirements for a
rule that inspects relationships between prims. The validator walks the
default prim hierarchy, computes the bound material for each mesh, and
reports `cap.ExampleRequirements.EX_002` when the material prim is not
named `basic_material`.

## Example

```usd
# Valid: the mesh is bound to a material named basic_material
def Xform "Asset"
{
    def Scope "Looks"
    {
        def Material "basic_material"
        {
        }
    }

    def Mesh "Body" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </Asset/Looks/basic_material>
    }
}
```

## How to comply

Bind each mesh to a `UsdShade.Material` prim named `basic_material`.
