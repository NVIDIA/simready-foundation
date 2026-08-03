# semantic-label-capability

| Code     | SL.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`sl-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`essential` |


## Summary

All geometry prims must be semantically labeled.

## Description

All renderable geometry (gprims with the computed purpose of "render" or "default") must have semantic labels to enable ground truth generation. Labels can be inherited from ancestor prims or bound materials.

At least one of the following should have an application of the SemanticsLabelsAPI.

- The renderable geometric primitive
- Ancestors of the renderable geometric primitive
- The renderable geometric primitive's computed bound full material
- Ancestors of the renderable geometric primitive's computed bound full material
- All elements of renderable geometric primitive through `GeomSubset` membership

## Why is it required?

- Ground truth validation requires semantic labels
- ML training data incomplete without semantic labels

## Examples

```usd
# Invalid: No semantic labels
def Mesh "UnlabeledCube" {
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, ...]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
}

# Valid: Labeled with Wikidata Q-Code
def Xform "Vehicle" (
    prepend apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
)
{
    token[] semantics:labels:wikidata_qcode = ["Q42889"]
    
    def Mesh "Body" {
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 2, 3, ...]
        point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), ...]
    }

        # Wheel is labeled via its bound material
        def Mesh "Wheel" (
            apiSchemas = ["MaterialBindingAPI"]
        )
        {
            rel material:binding = </Vehicle/WheelMaterial>
        }

    def Material "WheelMaterial" (
        prepend apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
    )
    {
        token[] semantics:labels:wikidata_qcode = ["Q12341517"]
    }
}
```

## How to comply

- Add semantic labels to geometry or parent prims
- Apply labels through bound materials

## For More Information

- [USD Semantics Documentation](https://openusd.org/release/api/usd_semantics_page_front.html)
- [Wikidata](https://www.wikidata.org)
