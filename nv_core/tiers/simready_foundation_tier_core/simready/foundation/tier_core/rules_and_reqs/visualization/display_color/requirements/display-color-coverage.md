# display-color-coverage-specification

| Code     | DISP.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`disp-001` |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

Every renderable geometry prim must resolve a display colour, authored on the prim or inherited from an ancestor.

## Description

Each `UsdGeom.Gprim` whose computed purpose is `default` or `render` MUST resolve a value for `primvars:displayColor`.

The value MAY be authored on the prim, or inherited from an ancestor. `UsdGeomPrimvarsAPI` inherits primvars down namespace, so an asset that authors one display colour on an enclosing `Xform` or `Scope` satisfies this requirement for the geometry beneath it. Only primvars with authored, non-blocked, constant interpolation values are inheritable, so an inherited display colour is by definition constant across the prims that inherit it.

Conformance is determined from the resolved value, using `UsdGeomPrimvarsAPI.FindPrimvarWithInheritance("displayColor")` or an equivalent traversal. A check for a directly authored primvar on each Gprim would reject assets that author the colour once on an ancestor, which is valid.

Prims whose computed purpose is `guide` or `proxy` are out of scope, as are non-geometry imageables such as `UsdGeom.PointInstancer`. Authoring a display colour on those is permitted.

### Guidance

A resolved display colour still renders through whatever fallback material the consumer supplies, and those differ between renderers. SimReady nominates a default material for it: an OpenPBR surface driven by primvar readers. In MaterialX, `ND_geompropvalue_color3` with its `geomprop` input set to `displayColor` connects to `base_color` on `ND_open_pbr_surface_surfaceshader`, and `ND_geompropvalue_float` with `geomprop` set to `displayOpacity` connects to `geometry_opacity`.

One material serves a whole asset. The readers evaluate against the geometry the material is bound to, so each prim keeps its own colour and opacity.

Give the opacity reader `inputs:default = 1.0`. `ND_geompropvalue_float` defaults that input to zero, zero opacity is invisible, and DISP.003 leaves `displayOpacity` unauthored on most SimReady geometry, so an opacity reader left at its own default makes that geometry disappear. `ND_open_pbr_surface_surfaceshader` already defaults `geometry_opacity` to `1.0`, so connecting the reader without a default is worse than not connecting it at all. The colour reader's `inputs:default` matters less, since DISP.001 requires every renderable prim to resolve a colour, but zero there is black.

The colour reader applies no conversion. A display colour in the linear Rec.709 default described in DISP.002 reaches `base_color` unchanged, which is the common case. A `colorSpace` authored on the attribute is not applied either: DISP.002 permits one, and this material renders the values unchanged whichever space they declare. Content that authors a non-default colour space needs a conversion this material does not supply.

### Valid: a fallback material that reads display colour and opacity

```usd
def Xform "Assembly"
{
    def Scope "Looks"
    {
        def Material "DisplayColorDefault"
        {
            token outputs:mtlx:surface.connect = </Assembly/Looks/DisplayColorDefault/Surface.outputs:out>

            def Shader "DisplayColorReader"
            {
                uniform token info:id = "ND_geompropvalue_color3"
                string inputs:geomprop = "displayColor"
                color3f inputs:default = (0.18, 0.18, 0.18)
                color3f outputs:out
            }

            def Shader "DisplayOpacityReader"
            {
                uniform token info:id = "ND_geompropvalue_float"
                string inputs:geomprop = "displayOpacity"
                float inputs:default = 1.0
                float outputs:out
            }

            def Shader "Surface"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color.connect = </Assembly/Looks/DisplayColorDefault/DisplayColorReader.outputs:out>
                float inputs:geometry_opacity.connect = </Assembly/Looks/DisplayColorDefault/DisplayOpacityReader.outputs:out>
                token outputs:out
            }
        }
    }

    def Mesh "bracket" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )
        rel material:binding = </Assembly/Looks/DisplayColorDefault>
    }
}
```

The material is a default. Geometry whose bound material declares its own base colour keeps that colour, and geometry with no material bound falls back to the consumer's own display-colour handling. That fallback need not cover opacity; Kit's RTX default material reads display colour and has no opacity term. This requirement governs whether the primvar resolves; the material above is what renders it.

This is a SimReady convention. Neither OpenUSD nor MaterialX nominates a material for display colour.

## Why is it required?

- Geometry with no resolvable display colour falls back to a renderer-specific default, so the same asset reads differently between consumers
- Low-fidelity and non-ray-traced paths have no material to fall back to

## Examples

### Valid: authored on the Gprim

```usd
def Mesh "bracket"
{
    color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
        interpolation = "constant"
    )
}
```

### Valid: authored once on an ancestor, inherited by the geometry below

```usd
def Xform "Assembly"
{
    color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
        interpolation = "constant"
    )

    def Mesh "bracket"
    {
    }
}
```

### Invalid: renderable mesh with no display colour on it or any ancestor

```usd
def Mesh "bracket"
{
}
```

## How to comply

- Author `primvars:displayColor` on renderable geometry, or once on a common ancestor with constant interpolation.
- Where an ancestor authors the value, leave the descendants unauthored and let inheritance supply it.

## For More Information

- [UsdGeomGprim](https://openusd.org/release/api/class_usd_geom_gprim.html)
- [UsdGeomPrimvarsAPI](https://openusd.org/release/api/class_usd_geom_primvars_a_p_i.html)
- [OpenPBR Surface specification](https://academysoftwarefoundation.github.io/OpenPBR/)
- [MaterialX specification](https://materialx.org/Specification.html)
- DISP.002 — display colour values
- DISP.003 — display opacity values
