# material-mdl-surface-present

| Code     | VM.MDL.003 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-mdl-003` |
| Compatibility | {compatibility}`Omniverse` |
| Tags     | {tag}`correctness` |

## Summary

A renderable GPrim's material must connect an MDL surface on `outputs:mdl:surface`.

## Description

A renderable GPrim resolves a material binding at the `full` purpose. That material MUST
connect `outputs:mdl:surface`. The module is unconstrained: OmniPBR, OmniGlass and bespoke
modules all satisfy this.

`VM.MDL.001` governs an MDL shader's source asset and sub-identifier, and `VM.MDL.002` its
schema. Both report nothing about a material with no MDL shader, because they inspect a shader
that is not there. A profile requiring the MDL surface lists all three codes.

MDL is evaluated by Omniverse renderers. A profile requiring it states that its consumers need
OmniPBR behaviour; `VM.PS.002` and `VM.PBR.001` are the portable equivalents for the
UsdPreviewSurface preview and the OpenPBR final surface.

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

- An asset that declares MDL support without an MDL surface gives an Omniverse consumer
  nothing to evaluate, and it falls back to whichever other surface the material connects
- A feature built only from requirements that inspect a shader when they find one passes an
  asset that has no MDL surface, so `FET_006_MDL` states nothing a consumer can act on

## Examples

### Valid: a bound material connects the MDL terminal

```usd
def Material "Chrome"
{
    token outputs:surface.connect = </World/Looks/Chrome/Preview.outputs:surface>
    token outputs:mdl:surface.connect = </World/Looks/Chrome/Mdl.outputs:out>

    def Shader "Mdl"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        token outputs:out
    }
}
```

### Invalid: a preview surface alone

```usd
def Material "Chrome"
{
    token outputs:surface.connect = </World/Looks/Chrome/Preview.outputs:surface>
}
```

## For more information

- [MDL in Omniverse](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/materials.html)
- [MaterialBindingAPI](https://openusd.org/dev/api/class_usd_shade_material_binding_a_p_i.html)

## How to comply

Connect an MDL shader to the `Material` prim's `outputs:mdl:surface`. The name of the shader
output it connects to is unconstrained.
