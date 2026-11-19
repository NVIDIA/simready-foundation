# generic-model-output-compression

| Code     | RP.006 |
|----------|--------|
| Tags     | {tag}`correctness` |

## Summary

`RenderVar` prims with `sourceName = "GenericModelOutput"` should use BLOSC compression (`srtx:compression:type = "blosc"`).

## Description

`GenericModelOutput` carries LiDAR point cloud data — per-point XYZ coordinates, intensity scalars, timestamps, and flags stored as typed numeric arrays. This data is non-visual and high-precision. Video codecs (`hevc`, `h264`, `av1`) are lossy and designed for perceptual colour fidelity; they degrade or corrupt numeric precision data. BLOSC is a lossless codec designed for numeric array data and preserves all values exactly.

Per the RTX Sensor API documentation: *"blosc is suited for non-visual data such as LiDAR pointclouds."*

This rule is a warning rather than a failure because some pipeline configurations may have specific reasons to omit or override compression. However, using a lossy codec on `GenericModelOutput` will corrupt point cloud data in ways that are difficult to diagnose.

## Why is it required?

Lossy video compression applied to a LiDAR point cloud buffer corrupts the floating-point coordinate and intensity values. Unlike colour images where minor compression artefacts are visually acceptable, point cloud data corruption directly affects downstream perception, mapping, and obstacle-detection algorithms that consume the output.

## Examples

```usd
# Valid: BLOSC compression on GenericModelOutput
def RenderVar "GenericModelOutput"
{
    uniform string sourceName = "GenericModelOutput"
    uniform string srtx:compression:type = "blosc"
}

# Should be corrected: lossy codec on point cloud data
def RenderVar "GenericModelOutput"
{
    uniform string sourceName = "GenericModelOutput"
    uniform string srtx:compression:type = "hevc"
}

# Acceptable: no compression attribute (omitted)
def RenderVar "GenericModelOutput"
{
    uniform string sourceName = "GenericModelOutput"
}
```

## How to comply

Set `srtx:compression:type = "blosc"` on any `RenderVar` prim whose `sourceName` is `"GenericModelOutput"`. If no compression attribute is present, consider adding `blosc` for best output fidelity.
