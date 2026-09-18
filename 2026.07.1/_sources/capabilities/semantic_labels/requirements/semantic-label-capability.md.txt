# semantic-label-capability

| Code     | SL.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sl-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |


## Summary

All renderable geometry must be semantically labeled.

## Description

All renderable geometry (gprims with the computed purpose of "render" or "default") must have semantic labels to enable ground truth generation. Labels can be inherited from ancestor prims or bound materials, consistent with the `SemanticsLabelsAPI` inheritance model (a prim inherits the labels of its ancestors).

At least one of the following must carry a `SemanticsLabelsAPI` label — the schema applied with at least one authored label value (the schema applied with no value does not satisfy this requirement):

- The renderable geometric primitive
- Ancestors of the renderable geometric primitive
- The renderable geometric primitive's computed bound full material
- Ancestors of the renderable geometric primitive's computed bound full material
- All elements of renderable geometric primitive through `GeomSubset` membership

### Scope

This requirement is evaluated over the stage's `defaultPrim` and its descendants — the published content of an asset. Prims outside the `defaultPrim` subtree are not checked. A missing `defaultPrim` is not reported by this requirement; it is a stage-metadata requirement enforced by the core profile, and if it is absent that check fails independently.

## Why is it required?

- Ground truth validation requires semantic labels
- ML training data incomplete without semantic labels

## Examples

This requirement is taxonomy-agnostic, so the examples use a generic `class` taxonomy.
(NVIDIA's Omniverse asset libraries use the Wikidata `wikidata_qcode` taxonomy — see SL.QCODE.001.)

```usd
# Invalid: No semantic labels
def Mesh "UnlabeledCube" {
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, ...]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
}

# Valid: a labeled ancestor labels its descendant geometry (label inheritance)
def Xform "OfficeBookshelf" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class"]
)
{
    token[] semantics:labels:class = ["furniture", "bookcase"]

    # Inherits "furniture", "bookcase" from the ancestor Xform -- no label needed here
    def Mesh "Frame" {
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 2, 3, ...]
        point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
    }

    # Labeled via its bound material
    def Mesh "Shelf" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        rel material:binding = </OfficeBookshelf/ShelfMaterial>
    }

    def Material "ShelfMaterial" (
        prepend apiSchemas = ["SemanticsLabelsAPI:class"]
    )
    {
        token[] semantics:labels:class = ["wood"]
    }
}
```

## How to comply

- Add semantic labels to geometry or parent prims
- Apply labels through bound materials

## For More Information

- [USD Semantics Documentation](https://openusd.org/release/api/usd_semantics_page_front.html)
- [Wikidata](https://www.wikidata.org)
