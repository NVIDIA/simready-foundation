# material-final-surface

| Code     | VM.PBR.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-pbr-001` |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

A renderable GPrim's material must provide a physically based final surface.

## Description

A renderable GPrim resolves a material binding at the `full` purpose. That material MUST
connect an **OpenPBR** surface on `outputs:mtlx:surface` — a shader whose `info:id` is
`ND_open_pbr_surface_surfaceshader`. No other MaterialX surface node is accepted on that
terminal.

An MDL surface does not satisfy this. `outputs:mdl:surface` is `VM.MDL.003`, and a profile
that accepts either lists both. Requiring OpenPBR here is what lets a consumer read a
`FET_006_OPENPBR` pass as "this asset has OpenPBR" — a feature a material can satisfy without
having the surface the feature is named for cannot answer that question. Where a material has
both an OpenPBR and an MDL surface, the two SHOULD represent the same appearance.

The constraint is the terminal on the `Material`. The name of the shader output it connects
to is unconstrained: `outputs:out` and `outputs:surface` are both conformant.

The UsdPreviewSurface preview is a separate feature, `com.nvidia.usd.VM.PS.001`. A profile
that requires both lists both.

### Two subjects, and why

The requirement is written for two shapes of asset.

**An asset with geometry.** The subject is the geometry a final render draws: a GPrim whose
computed purpose is `default` or `render`, and the material it resolves at the `full` purpose.
Every such material MUST connect the terminal. Proxy and guide geometry, materials bound only
through `material:binding:preview`, unused entries in `/Looks`, and friction-only physics
materials are all outside the subject, so no exception has to be written for them.

**An asset that is a material.** A material library publishes `Material` prims and no geometry
to bind them to. Against the first subject such an asset has nothing to judge, so the
requirement would report nothing and the feature would state nothing a consumer could act on.
Where the stage has no geometry a final render would draw, the subject becomes the `Material`
prims, and at least one of them MUST connect the terminal.

The second branch asks for one rather than all, because an asset with no geometry gives no way
to say which of its materials a consumer will use. On an asset with geometry the first branch
is the stronger statement and the second does not run — so an unused material carrying the
terminal can never stand in for a bound material that lacks it.

`VG.MESH.001` uses the same stage-level shape to require that a stage contains at least one
mesh.

## Why is it required?

Without an OpenPBR final surface an asset produces:

- Inconsistent appearance across RTX, USDView, and other OpenPBR-capable runtimes
- Content that resolves only under MDL, which prevents renderer-independent rendering
- Manual material repair before the asset is usable for camera or perception simulation

## Examples

### Valid: an OpenPBR (MaterialX) final surface

```usd
def Xform "Bracket" ( kind = "component" )
{
    def Mesh "Geo" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding = </Bracket/mtl_bracket>
    }

    def Material "mtl_bracket"
    {
        token outputs:mtlx:surface.connect = </Bracket/mtl_bracket/OpenPBR.outputs:out>

        def Shader "OpenPBR"
        {
            uniform token info:id = "ND_open_pbr_surface_surfaceshader"
            color3f inputs:base_color = (0.4, 0.4, 0.42)
            float inputs:base_metalness = 1
            float inputs:specular_roughness = 0.35
            token outputs:out
        }
    }
}
```

### Invalid: an MDL final surface alone

```usd
def Xform "Bracket" ( kind = "component" )
{
    def Mesh "Geo" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding = </Bracket/mtl_bracket>
    }

    def Material "mtl_bracket"
    {
        token outputs:mdl:surface.connect = </Bracket/mtl_bracket/OmniPBR.outputs:out>

        def Shader "OmniPBR"
        {
            uniform token info:implementationSource = "sourceAsset"
            uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
            uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
            token outputs:out
        }
    }
}
```

An MDL surface satisfies `VM.MDL.003`, not this requirement. A profile that accepts either
lists both codes.

### Invalid: the bound material has only a preview surface

```usd
def Xform "Bracket" ( kind = "component" )
{
    def Mesh "Geo" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding = </Bracket/mtl_bracket>
    }

    def Material "mtl_bracket"
    {
        token outputs:surface.connect = </Bracket/mtl_bracket/Preview.outputs:surface>

        def Shader "Preview"
        {
            uniform token info:id = "UsdPreviewSurface"
            color3f inputs:diffuseColor = (0.4, 0.4, 0.42)
            token outputs:surface
        }
    }
}
```

### Invalid: the mtlx surface is a MaterialX node other than OpenPBR

```usd
def Xform "Bracket" ( kind = "component" )
{
    def Mesh "Geo" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding = </Bracket/mtl_bracket>
    }

    def Material "mtl_bracket"
    {
        token outputs:mtlx:surface.connect = </Bracket/mtl_bracket/StandardSurface.outputs:out>

        def Shader "StandardSurface"
        {
            uniform token info:id = "ND_standard_surface_surfaceshader"
            color3f inputs:base_color = (0.4, 0.4, 0.42)
            token outputs:out
        }
    }
}
```

`standard_surface` is physically based and widely implemented. It is reported because the id
on `outputs:mtlx:surface` is compared against `ND_open_pbr_surface_surfaceshader` alone.

### Valid: an asset that is a material, with no geometry

```usd
#usda 1.0

def Material "Aging_Copper"
{
    token outputs:surface.connect = </Aging_Copper/Preview.outputs:surface>
    token outputs:mtlx:surface.connect = </Aging_Copper/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        token outputs:out
    }

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        token outputs:surface
    }
}
```

A material library publishes files of this shape. There is no geometry to resolve a binding
from, so the requirement is judged against the `Material` prims themselves.

## How to comply
- Connect a final surface: OpenPBR on `outputs:mtlx:surface`, or an MDL surface on `outputs:mdl:surface` during migration.
- Give a final surface to every material the asset renders with, meaning every material a renderable GPrim resolves at `full`. A material bound only for `preview`, and one nothing binds, are outside this.
- For new assets, use OpenPBR and the SimReady reference presets (PhysicalAI-SimReady-Materials).

## For More Information
- [OpenPBR Surface specification](https://academysoftwarefoundation.github.io/OpenPBR/)
- [OpenUSD, MaterialX, and OpenPBR](https://developer.nvidia.com/blog/unlock-seamless-material-interchange-for-virtual-worlds-with-openusd-materialx-and-openpbr/)
- `com.nvidia.usd.VM.PS.001` — UsdPreviewSurface preview output, defined by `usd-validation-nvidia`
