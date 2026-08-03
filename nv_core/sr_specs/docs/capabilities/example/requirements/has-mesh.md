# has-mesh

| Code     | EX.001 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

The asset must contain at least one mesh prim under the default prim.

## Description

This example requirement shows the common pattern of turning a small
authoring rule into both documentation and a generated Python enum. The
corresponding validator registers `cap.ExampleRequirements.EX_001` and
reports that generated requirement when no `UsdGeom.Mesh` prim is found
below the stage default prim.

## Example

```usd
# Valid: default prim contains a mesh
def Xform "Asset"
{
    def Mesh "Body"
    {
    }
}
```

## How to comply

Set a default prim for the stage and author at least one `UsdGeom.Mesh`
within that prim's hierarchy.
