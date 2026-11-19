# render-product-ordered-vars

| Code     | RP.002 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

A RenderProduct prim must have an `orderedVars` relationship containing at least one valid UsdRender.Var prim.

## Examples

```usd
# Invalid: RenderProduct with no orderedVars relationship
def RenderProduct "RenderProduct"
{
    rel camera = </World/RGB_Camera>
    int2 resolution = (1920, 1080)
}

# Valid: RenderProduct with orderedVars referencing at least one RenderVar
def RenderVar "RgbRenderVar"
{
    token sourceName = "rgb"
    token dataType = "color3f"
}

def RenderProduct "RenderProduct"
{
    rel camera = </World/RGB_Camera>
    int2 resolution = (1920, 1080)
    rel orderedVars = [</Render/RgbRenderVar>]
}
```

## How to comply

- Add an `orderedVars` relationship to every `RenderProduct` prim.
- The relationship must target at least one `RenderVar` prim that exists in the stage.
