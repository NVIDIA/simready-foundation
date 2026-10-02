# material-shading-network-structure

| Code     | VM.PBR.003 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-pbr-003` |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

Shader ids must name a declared node, connections must have an existing target, and the material must connect a surface terminal.

## Description

Each visual `UsdShade.Material` MUST satisfy the following, for every `UsdShade.Shader` in its namespace:

- The shader's `info:id` MUST resolve to a declared shader node. `UsdPreviewSurface`, `UsdUVTexture`, `UsdTransform2d` and the `UsdPrimvarReader_*` ids are accepted without MaterialX discovery resolving them. A shader whose implementation source is `sourceAsset` names its implementation with `info:mdl:sourceAsset` and a `subIdentifier` instead of a registry id, and is covered by [`VM.MDL.001`](/capabilities/visualization/materials/requirements/material-mdl-source-asset).
- Every connected input MUST reference an existing source prim and output. A connection whose target is absent (a dangling connection) MUST NOT be present.
- An authored input's value type MUST match the type declared by the nodedef for that input. Types are compared by their underlying `Tf.Type`, so `color3f`, `vector3f` and `normal3f` are treated as the same underlying `GfVec3f`.
- The material MUST author and connect a surface terminal, and any authored terminal MUST NOT be connected to a missing target.

A `UsdShade.Material` that applies `PhysicsMaterialAPI` and authors no surface output in any
render context has no shading network, and this requirement does not apply to it. A material
with both a physics schema and a surface output is a visual material and is subject to it in
full.

An authored type the nodedef does not declare is reported here and by `VM.BIND.002`. Either
requirement can be enabled without the other.

These requirements name nodedefs as **MaterialX 1.39 or later** spells them, which
`requirements.txt` sets as the floor. 1.39 renamed nodedefs: `ND_normalmap` became
`ND_normalmap_float`, so an id that names a node under one version names nothing under the other.


## Why is it required?

- Shader ids that resolve to nothing render as an undefined node, with per-renderer fallback behaviour
- Dangling connections leave inputs silently at their default value
- A type mismatch between an authored input and its nodedef is handled inconsistently across backends
- A material with no connected surface terminal has nothing for a render context to bind to

## Examples

### Valid: a declared id, an existing connection target, and a connected terminal

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "Tex"
    {
        uniform token info:id = "ND_image_color3"
        asset inputs:file = @./textures/bracket_basecolor.png@
        color3f outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket/Tex.outputs:out>
        token outputs:out
    }
}
```

### Invalid: an id that resolves to no nodedef

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "Tex"
    {
        uniform token info:id = "ND_not_a_real_nodedef"
        color3f outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket/Tex.outputs:out>
        token outputs:out
    }
}
```

### Invalid: an input connected to a prim that is not in the material

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket/Missing.outputs:out>
        token outputs:out
    }
}
```

### Invalid: an authored type the nodedef does not declare

The OpenPBR nodedef declares `base_color` as a color.

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float inputs:base_color = 0.35
        token outputs:out
    }
}
```

### Invalid: no surface terminal in any render context

The network is well formed and nothing connects it to the material.

```usd
def Material "mtl_bracket"
{
    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color = (0.35, 0.36, 0.38)
        token outputs:out
    }
}
```

### Invalid: a surface terminal connected to a missing shader

The terminal names `Surface`; the shader is called `OpenPBR`.

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/Surface.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color = (0.35, 0.36, 0.38)
        token outputs:out
    }
}
```

## Guidance

MaterialX defines a large node library and backends differ in which nodes they implement, so a conservative node choice travels furthest. The following are widely implemented and are recommended:

| Group | Nodes |
|---|---|
| Texture | `image`, `tiledimage` |
| Geometric and primvar readers | `texcoord`, `normal`, `tangent`, `position`, `geompropvalue` |
| Normal mapping | `normalmap` |
| Maths | `add`, `subtract`, `multiply`, `divide`, `mix`, `clamp`, `remap`, `power` |
| Color and channels | `constant`, `convert`, `combine2`, `combine3`, `separate2`, `separate3` |
| Surface | `open_pbr_surface` |

SimReady does not restrict the specification to this list. Nodes outside it are permitted, and may not survive a round trip through every renderer.

`standard_surface` is widely implemented, but `VM.PBR.001` accepts only
`ND_open_pbr_surface_surfaceshader` on `outputs:mtlx:surface`. Author `open_pbr_surface`.

### Exposing material parameters

Expose the parameters a consumer would want to change as `inputs:*` on the `Material` prim, connected down to the shader inputs they drive. A consumer can then retarget the look without opening the network.

#### Valid: the two parameters a consumer would retarget, exposed on the material interface

```usd
def Material "mtl_bracket"
{
    color3f inputs:base_color = (0.32, 0.31, 0.3)
    float inputs:specular_roughness = 0.4

    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color.connect = </mtl_bracket.inputs:base_color>
        float inputs:specular_roughness.connect = </mtl_bracket.inputs:specular_roughness>
        token outputs:out
    }
}
```

Use the surface specification's own parameter names, flat and unprefixed: `base_color`, not a renamed equivalent. Where several materials share a look, define the interface once on a class the materials `inherits` and author only values on the leaves. That is what the Physical AI SimReady Materials library does: every material in it authors `inputs:*` on the Material prim and nothing else, against a shared base class with 65 interface inputs.

Two idioms apply, and a material should pick one per parameter and stay with it. An interface input authored with a value overrides whatever the shader holds. An interface input created without a value leaves the shader's own value in control and exists only as a hook for a consumer to author into.

This is a SimReady convention. `UsdShade` permits and illustrates material interfaces but does not require or recommend them.

## How to comply

- Author shader ids that name a node declared in the target USD environment.
- Remove connections whose source prim or output no longer exists.
- Match authored input types to the nodedef.
- Connect a surface terminal on the material.

## For More Information

- [UsdShade](https://openusd.org/release/api/usd_shade_page_front.html)
- [MaterialX](https://materialx.org/)
- [`VM.PBR.001`](/capabilities/visualization/materials/requirements/material-final-surface) — the material's final surface
- [`VM.PBR.002`](/capabilities/visualization/materials/requirements/material-pbr-parameter-ranges) — OpenPBR parameter ranges
