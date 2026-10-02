# material-preview-surface-present

| Code     | VM.PS.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-ps-002` |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

A renderable GPrim's material must connect a UsdPreviewSurface on `outputs:surface`.

## Description

A renderable GPrim resolves a material binding at the `full` purpose. That material MUST
connect `outputs:surface`.

`outputs:surface` is the universal render context, the surface a consumer gets when it names
no context. The universal context is the last entry in USD's resolution order, so a material
with nothing connected there does not fall through to its MaterialX or MDL surface. The
consumer gets the renderer's default material.

`com.nvidia.usd.VM.PS.001` governs how a UsdPreviewSurface is authored, and reports nothing
about an asset that has none, because it inspects a shader that is not there. A profile
requiring the preview surface lists both codes.

A GPrim that resolves no material at all is reported by `VM.MAT.001`.

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

- UsdPreviewSurface is the surface every OpenUSD consumer can evaluate. An asset without one
  renders on the consumer's default material wherever MDL and MaterialX are unavailable
- A feature built only from requirements that inspect a surface when they find one passes an
  asset that has no such surface. `FET_006_STANDARD` then states nothing a consumer can act
  on, and a library searching validation results cannot use it to find the assets it can
  render

## Examples

### Valid: a bound material connects the universal terminal

```usd
def Material "Chrome"
{
    token outputs:surface.connect = </World/Looks/Chrome/Preview.outputs:surface>
    token outputs:mtlx:surface.connect = </World/Looks/Chrome/OpenPBR.outputs:out>

    def Shader "Preview"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
        float inputs:metallic = 1
        float inputs:roughness = 0.2
        token outputs:surface
    }
}
```

### Invalid: OpenPBR alone

```usd
def Material "Chrome"
{
    token outputs:mtlx:surface.connect = </World/Looks/Chrome/OpenPBR.outputs:out>
}
```

A consumer without MaterialX gets its own default material for every GPrim this is bound to.

## For more information

- [UsdPreviewSurface Specification](https://openusd.org/release/spec_usdpreviewsurface.html)
- [MaterialBindingAPI](https://openusd.org/dev/api/class_usd_shade_material_binding_a_p_i.html)

## How to comply

Connect a `UsdPreviewSurface` shader to the `Material` prim's `outputs:surface`. The name of
the shader output it connects to is unconstrained.
