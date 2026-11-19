# render-var-source-name

| Code     | RP.003 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

A `RenderVar` prim must have a non-empty `sourceName` attribute.

## Examples

```usd
# Invalid: RenderVar with no sourceName attribute
def RenderVar "MyVar"
{
    token dataType = "color3f"
}

# Invalid: RenderVar with empty sourceName
def RenderVar "MyVar"
{
    token sourceName = ""
    token dataType = "color3f"
}

# Valid: RenderVar with a non-empty sourceName
def RenderVar "RgbVar"
{
    token sourceName = "rgb"
    token dataType = "color3f"
}

# Valid: RenderVar with a semantic AOV sourceName
def RenderVar "SemanticVar"
{
    token sourceName = "semanticSegmentation"
    token dataType = "uint"
}
```

## How to comply

- Set the `sourceName` attribute on every `RenderVar` prim to a non-empty string identifying the output type (e.g. `"rgb"`, `"depth"`, `"semanticSegmentation"`).
