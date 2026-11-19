# render-product-camera

| Code     | RP.001 |
|----------|--------|
| Tags     | {tag}`essential` |

## Summary

A RenderProduct prim must have a `camera` relationship targeting a valid prim.

## Examples

```usd
# Invalid: RenderProduct with no camera relationship
def RenderProduct "RenderProduct"
{
    token aspectRatioConformPolicy = "expandAperture"
    int2 resolution = (1920, 1080)
}

# Valid: RenderProduct with camera relationship targeting a Camera prim
def Camera "RGB_Camera"
{
    float focalLength = 18.147562
}

def RenderProduct "RenderProduct"
{
    token aspectRatioConformPolicy = "expandAperture"
    int2 resolution = (1920, 1080)
    rel camera = </World/RGB_Camera>
}
```

## How to comply

- Add a `camera` relationship to every `RenderProduct` prim.
- The relationship must target an existing `Camera` or `OmniLidar` prim in the stage.
