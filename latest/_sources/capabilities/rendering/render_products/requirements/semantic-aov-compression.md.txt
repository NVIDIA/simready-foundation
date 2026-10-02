# semantic-aov-compression

| Code     | RP.004 |
|----------|--------|
| Tags     | {tag}`correctness` |

## Summary

RenderVar prims whose `sourceName` starts with "semantic" must use BLOSC compression.

## Examples

```usd
# Invalid: semantic RenderVar without BLOSC compression
def RenderVar "SemanticVar"
{
    token sourceName = "semanticSegmentation"
    token dataType = "uint"
    # No compression attributes — defaults to uncompressed
}

# Invalid: semantic RenderVar with a non-BLOSC compression format
def RenderVar "SemanticVar"
{
    token sourceName = "semanticSegmentation"
    token dataType = "uint"
    uniform token srtx:compression:type = "hevc"
}

# Valid: semantic RenderVar with BLOSC compression
def RenderVar "SemanticVar"
{
    token sourceName = "semanticSegmentation"
    token dataType = "uint"
    uniform token srtx:compression:type = "blosc" (
        allowedTokens = ["hevc", "h264", "av1", "blosc"]
    )
}
```

## How to comply

- For any `RenderVar` whose `sourceName` begins with `"semantic"`, set `srtx:compression:type = "blosc"`.
- Non-semantic `RenderVar` prims (e.g. `"LdrColor"`, `"DepthLinearized"`) are not affected by this requirement.
