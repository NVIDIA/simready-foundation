# usdgeom-mesh-primvar-indexing

| Code     | VG.009 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vg-009` |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Use indexed primvars when values are repeated

## Description

When primvar values are repeated multiple times, they should be stored in an indexed format. Indexed primvars allow efficient reuse of values and reduce memory usage.

## Why is it required?
- Higher memory usage
- Larger file sizes
- Slower file loading

## Examples

```usd
# Not recommended: Unindexed primvars with repeated values
def Mesh "UnindexedMesh" {
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, 4, 5, 6, 7]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), 
                       (0,0,1), (1,0,1), (1,1,1), (0,1,1)]
    
    # Unindexed UVs with repeated values
    texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1),  # First face
                               (0,0), (1,0), (1,1), (0,1)]    # Second face repeats same UVs
}

# Recommended: Indexed primvars
def Mesh "IndexedMesh" {
    int[] faceVertexCounts = [4, 4]
    int[] faceVertexIndices = [0, 1, 2, 3, 4, 5, 6, 7]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), 
                       (0,0,1), (1,0,1), (1,1,1), (0,1,1)]
    
    # Indexed UVs reuse values
    texCoord2f[] primvars:st = [(0,0), (1,0), (1,1), (0,1)]
    int[] primvars:st:indices = [0, 1, 2, 3, 0, 1, 2, 3]
}
```

## How to comply
- Enable primvar indexing in export settings
- Use indexed primvars for repeated values
- Convert unindexed primvars to indexed format
- Scene Optimizer - Index Primvars

## For More Information
- [USD Primvar Documentation](https://openusd.org/release/api/class_usd_geom_primvar.html) 