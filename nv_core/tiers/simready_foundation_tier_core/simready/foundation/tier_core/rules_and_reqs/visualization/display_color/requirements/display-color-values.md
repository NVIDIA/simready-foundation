# display-color-values-specification

| Code     | DISP.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`disp-002` |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

Authored display colour values must lie within the range a consumer can interpret.

## Description

Every element of a resolved `primvars:displayColor` array MUST have each of its three components within `[0, 1]`, and MUST be finite. Values outside that range, and non-finite values, are clamped or rejected differently between consumers.

A resolved `primvars:displayColor` MUST use the type `UsdGeomGprim` declares for it, `color3f[]`. Where it is authored makes no difference: the requirement applies to the value the geometry resolves, at whatever depth it was authored.

USD reports neither of the two ways to miss the declared type. A scalar: nothing constrains the type on a prim that is not a GPrim, so a scalar `color3f` authored on an enclosing `Xform` loads and is inherited by the geometry below it, and a scalar authored on the geometry itself is not converted to the declared array either. A precision variant: `color3d[]` and `half3[]` load as authored on an ancestor, and on the geometry itself the schema pins the attribute's declared type to `color3f[]` while the value keeps the precision it was written with. In each case a consumer reading the declared type gets an array it did not ask for, or none at all.

The array length MUST agree with the primvar's declared interpolation and the topology of the prim it is authored on. `constant` takes a single element on any GPrim, and `vertex` takes one per point on any point-based GPrim. The remaining counts follow each schema: on a mesh, `uniform` takes one element per face, `varying` one per point and `faceVarying` one per face-vertex, while `UsdGeomBasisCurves` counts `uniform` per curve and `varying` per segment endpoint, which depend on its `type`, `basis` and `wrap`.

An indexed primvar holds one index for each element the interpolation calls for, so the counts above apply to its index array. Its value array may be any length, and every index MUST fall within it.

A primvar that declares no interpolation is `constant`, so authoring the declaration is not required. The examples on this page and on DISP.001 and DISP.003 state it anyway, which keeps the expected element count readable without knowing the default.

These terms apply to every value the primvar resolves, not only its first. A primvar with no time samples resolves one value, at the default time code. A primvar with time samples resolves one value at each sample, and each is checked for range, finiteness and element count; where such a primvar has no default value, nothing resolves at the default time code and its samples are all there is to check. An indexed primvar's index array has time samples of its own, read at the same time code as the values it indexes.

### Colour space

`displayColor` values are interpreted in a colour space, and USD resolves that colour space in this order:

1. The `colorSpace` metadata authored on the attribute itself (`UsdAttribute::SetColorSpace()`).
2. `UsdColorSpaceAPI` applied to the prim that owns the attribute.
3. `UsdColorSpaceAPI` on the nearest ancestor that authors one.
4. The default, when none of the above is authored.

The default is **Linear Rec.709**, token `lin_rec709_scene`: Rec.709 primaries per ITU-R BT.709, a D65 white point, and a linear transfer function. An asset that authors no colour space anywhere is therefore not ambiguous; its display colours are linear Rec.709 by definition.

Authoring a colour space is not required by this specification. A validator MUST NOT fail an asset for the absence of one, because the default is well defined and most content relies on it. Where a colour space is authored, it is expected to be a token USD recognises.

The practical consequence for authoring is that display colour values are **linear**, not sRGB-encoded. A mid grey of `0.5` in linear Rec.709 is a considerably lighter value than a `0.5` picked from an sRGB colour picker. Values transferred directly from an sRGB source without conversion will read as too bright.

### Guidance

Display colour is most useful when it approximates the albedo a viewer would expect for the material class the object represents. Values taken unmodified from CAD, where colour often encodes part or system identity instead of appearance, are permitted and usually worth revisiting.

No plausibility band is set, and none is planned. Rec.709 weights blue at 0.0722, so a saturated navy computes a lower luminance than charcoal, and no threshold separates an implausibly dark value from a legitimately saturated one. A band would also reject the CAD identity colours this requirement permits.

Authoring an explicit colour space is worthwhile for content that will be exchanged between pipelines with different conventions. The OpenUSD colour guide recommends applying a production-wide default on a prim and referencing it onto asset roots, which `UsdColorSpaceAPI` inheritance then applies to the geometry beneath.

Values at or near zero across all three components render the object indistinguishable from unlit background in some low-fidelity paths. This is permitted -- a black object is legitimate -- and is a common artifact of an unconfigured export.

## Why is it required?

- A value that is not the declared array type is invisible to a consumer that asks for it
- Out-of-range components are clamped by some consumers and rejected by others
- Non-finite values propagate into render output
- An array length that disagrees with the declared interpolation leaves the primvar unusable

## Examples

### Valid: constant interpolation, one element, components in range

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
        interpolation = "constant"
    )
}
```

### Valid: no colour space authored, so values are linear Rec.709 by default

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(0.216, 0.216, 0.216)] (
        interpolation = "constant"
    )
}
```

### Valid: colour space authored explicitly on the attribute

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(0.216, 0.216, 0.216)] (
        colorSpace = "lin_rec709_scene"
        interpolation = "constant"
    )
}
```

### Invalid: component outside [0,1]

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(1.8, 0.4, 0.42)] (
        interpolation = "constant"
    )
}
```

### Invalid: constant interpolation declared, two elements authored

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(0.4, 0.4, 0.42), (0.1, 0.1, 0.1)] (
        interpolation = "constant"
    )
}
```

### Invalid: a scalar color3f, not the declared color3f[]

```usd
def Xform "Assembly"
{
    color3f primvars:displayColor = (0.4, 0.4, 0.42) (
        interpolation = "constant"
    )

    def Mesh "bracket"
    {
    }
}
```

Authored on an Xform, where no schema constrains the type, and inherited by the mesh below.

### Invalid: color3d[], a precision variant of the declared color3f[]

```usd
def Xform "Assembly"
{
    color3d[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
        interpolation = "constant"
    )

    def Mesh "bracket"
    {
    }
}
```

Reported whether it is authored on an ancestor, as here, or on the geometry itself.

### Invalid: out of range at the second time sample

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
        interpolation = "constant"
    )
    color3f[] primvars:displayColor.timeSamples = {
        0: [(0.4, 0.4, 0.42)],
        5: [(0.4, 9.5, 0.42)],
    }
}
```

Conforming at the default time code and at the first sample. Every sample is checked, so this is a failure.

## How to comply

- Author the value as `color3f[]`, including on an ancestor `Xform`, where no schema enforces the type. `color3d[]` and `half3[]` do not stand in for it.
- Keep each component within `[0, 1]`.
- Match the array length to the declared interpolation and the prim's topology.
- Author values in linear Rec.709, or author a `colorSpace` declaring another space. Convert values taken from an sRGB colour picker before authoring them.

## For More Information

- [UsdGeomGprim](https://openusd.org/release/api/class_usd_geom_gprim.html)
- [UsdGeomPrimvar interpolation](https://openusd.org/release/api/class_usd_geom_primvar.html)
- [Color User's Guide](https://openusd.org/release/user_guides/color_user_guide.html)
- [UsdColorSpaceAPI](https://openusd.org/release/api/class_usd_color_space_a_p_i.html)
- DISP.001 — display colour coverage
- DISP.003 — display opacity values
