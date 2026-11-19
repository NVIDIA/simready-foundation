# display-opacity-values-specification

| Code     | DISP.003 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`disp-003` |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

Display opacity, where authored, must lie within its valid range and agree with its declared interpolation.

## Description

`primvars:displayOpacity` is a `float[]` primvar defined by `UsdGeomGprim` as the companion to `displayColor`. USD keeps the two separate so that "each can be independently overridden", so this requirement is stated independently of DISP.001 and DISP.002.

Authoring `displayOpacity` is not required. A prim that does not author it is treated as fully opaque, which is the common case for SimReady geometry.

Where `primvars:displayOpacity` is authored:

- The value MUST use the declared type, `float[]`. Neither a scalar `float` nor a precision variant such as `double[]` or `half[]` stands in for it, on the geometry or on an ancestor, on the same terms as DISP.002.
- Every element MUST be within `[0, 1]` and MUST be finite.
- The array length MUST agree with the primvar's declared interpolation and the topology of the prim, on the same terms as DISP.002.

Each term holds for every value the primvar resolves, as in DISP.002: the default time code where one is authored, and every authored time sample.

An opacity below `1.0` marks the surface non-opaque for consumers reading the primvar. Whether a given runtime renders that transparency depends on its render path, so an authored value below `1.0` states intent without guaranteeing appearance.

## Why is it required?

- A scalar value is invisible to a consumer that reads the declared `float[]`
- Out-of-range or non-finite opacity is handled inconsistently between consumers
- An array length that disagrees with the declared interpolation leaves the primvar unusable
- Opacity authored unintentionally, for example preserved from an export default, makes geometry disappear in paths that honour it

## Examples

### Valid: not authored, geometry is treated as fully opaque

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
        interpolation = "constant"
    )
}
```

### Valid: authored, in range

```usd
def Mesh "window"
{
    color3f[] primvars:displayColor = [(0.8, 0.85, 0.9)] (
        interpolation = "constant"
    )
    float[] primvars:displayOpacity = [0.25] (
        interpolation = "constant"
    )
}
```

### Invalid: opacity outside [0,1]

```usd
def Mesh "window"
{
    color3f[] primvars:displayColor = [(0.8, 0.85, 0.9)] (
        interpolation = "constant"
    )
    float[] primvars:displayOpacity = [1.5] (
        interpolation = "constant"
    )
}
```

Display colour is authored, so DISP.001 and DISP.002 are met and the opacity value is the only failure.

### Invalid: a scalar float, not the declared float[]

```usd
def Mesh "window"
{
    color3f[] primvars:displayColor = [(0.8, 0.85, 0.9)] (
        interpolation = "constant"
    )
    float primvars:displayOpacity = 0.25 (
        interpolation = "constant"
    )
}
```

The value is in range, but a consumer reading the declared type finds nothing.

### Invalid: double[], a precision variant of the declared float[]

```usd
def Mesh "window"
{
    color3f[] primvars:displayColor = [(0.8, 0.85, 0.9)] (
        interpolation = "constant"
    )
    double[] primvars:displayOpacity = [0.25] (
        interpolation = "constant"
    )
}
```

Reported on the geometry, as here, and on an ancestor alike.

## How to comply

- Leave `primvars:displayOpacity` unauthored for opaque geometry.
- Where authored, author it as `float[]` and not as `double[]` or `half[]`, keep each element within `[0, 1]`, and match the array length to the declared interpolation.

## For More Information

- [UsdGeomGprim](https://openusd.org/release/api/class_usd_geom_gprim.html)
- DISP.001 — display colour coverage
- DISP.002 — display colour values
