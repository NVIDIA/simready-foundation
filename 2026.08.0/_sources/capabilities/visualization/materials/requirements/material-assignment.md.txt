# material-assignment

| Code     | VM.MAT.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-mat-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`essential` |

## Summary

Each renderable GPrim must have a computed material bound to it

## Description

A GPrim is renderable here when its computed purpose is `default` or `render`, so proxies and
guides are not checked. A `GeomSubset` is reached through the GPrim that owns it.

- Every renderable GPrim MUST resolve a material, bound on the prim or inherited from an ancestor
- A GPrim with material-bind `GeomSubset` children is judged through them: each subset MUST
  resolve a material, and the GPrim's own binding is not checked separately
- The material MUST resolve at the `full` purpose, which reads `material:binding:full` and falls
  back to the all-purpose `material:binding`
- Bindings MUST be direct or inherited. Collection-based bindings (`material:binding:collection:*`)
  MUST NOT be used
- Binding strength SHOULD be left at the default. A `bindMaterialAs` override is reported as a
  warning, not a failure

## Why is it required?

- A material defines the surface appearance of the geometry it is bound to. Without one there is
  nothing to describe how the surface responds to light, so the asset cannot be used for appearance
  visualization or for simulating a visual sensor
- Geometry that resolves no material renders differently from one renderer to the next, since
  renderers differ in what they fall back to
- Several binding mechanisms competing on one prim make the resolution ambiguous
- A collection binding puts the assignment somewhere other than the prim it applies to, so the
  material a prim ends up with cannot be read off that prim
- A `bindMaterialAs` override lets an ancestor binding win over a closer one, so the resolved
  material no longer follows from namespace depth alone

## Purposes and render contexts

Render context selects which shader inside a material is used. One material may declare
`outputs:surface` (UsdPreviewSurface), `outputs:mtlx:surface` (OpenPBR) and `outputs:mdl:surface` at
once, and a renderer takes the context it supports, falling back to the universal output.

Binding purpose selects which material a prim binds to. `UsdShadeMaterialBindingAPI` defines `full`
as the highest-fidelity representation and `preview` as the lighter-weight one used where "latency
and speed are generally of greater concern".

A single material with several render-context outputs takes one all-purpose `material:binding`, and
each renderer resolves the shader it can use. Prefer this shape; it is what the shipped sample
content uses.

Purpose-specific bindings apply where an asset binds different materials per purpose: a shared
material bound once at the asset root for `preview` and inherited, alongside distinct OpenPBR or MDL
materials bound per prim at `full`. Both bindings resolve independently, so the preview
representation stays shared while fidelity materials remain per-part.

A purpose-specific binding displaces the all-purpose one at that purpose.

## Examples

### Valid: a mesh bound to a material in the same asset

```usd
def "MyAsset" (
    kind = "component"
)
{
    def Scope "Materials" () {
        def Material "mtl_default"
        {
            token outputs:surface.connect = </MyAsset/Materials/mtl_default/PreviewSurface.outputs:surface>
            token outputs:mtlx:surface.connect = </MyAsset/Materials/mtl_default/OpenPBR.outputs:out>

            def Shader "PreviewSurface"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0.18, 0.18, 0.18)
                token outputs:surface
            }

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.18, 0.18, 0.18)
                token outputs:out
            }
        }
    }

    def Scope "Geometry" () {
        def Mesh "Cube" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {
            rel material:binding = </MyAsset/Materials/mtl_default>
        }
    }
}
```

### Valid: separate preview and fidelity materials

```usd
def Xform "Asset" ( prepend apiSchemas = ["MaterialBindingAPI"] )
{
    # one shared material bound for preview across the whole asset, inherited below
    rel material:binding:preview = </Asset/Looks/mtl_shared>

    def Scope "Looks"
    {
        def Material "mtl_shared"
        {
            token outputs:surface.connect = </Asset/Looks/mtl_shared/Preview.outputs:surface>
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_shared/OpenPBR.outputs:out>

            def Shader "Preview"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0.18, 0.18, 0.18)
                token outputs:surface
            }

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.18, 0.18, 0.18)
                token outputs:out
            }
        }

        def Material "mtl_steel"
        {
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_steel/OpenPBR.outputs:out>

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.35, 0.36, 0.38)
                float inputs:base_metalness = 1
                float inputs:specular_roughness = 0.25
                token outputs:out
            }
        }

        def Material "mtl_rubber"
        {
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_rubber/OpenPBR.outputs:out>

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.05, 0.05, 0.05)
                float inputs:specular_roughness = 0.8
                token outputs:out
            }
        }
    }

    def Mesh "part_steel" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding:full = </Asset/Looks/mtl_steel>
    }

    def Mesh "part_rubber" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding:full = </Asset/Looks/mtl_rubber>
    }
}
```

Both meshes resolve a material at the `full` purpose, so both satisfy this requirement.
[`VM.PBR.001`](/capabilities/visualization/materials/requirements/material-final-surface) judges
whatever a renderable GPrim resolves at `full`, which here is `mtl_steel` and `mtl_rubber`;
`mtl_shared` is bound only for `preview` and a `full` computation never returns it.

### Invalid: a renderable mesh with no binding

```usd
def "MyAsset" (
    kind = "component"
)
{
    def Mesh "Cube"
    {
        # no material:binding here or on any ancestor
    }
}
```

### Invalid: a material-bind subset that resolves no material

```usd
def Xform "Asset" ()
{
    def Scope "Looks"
    {
        def Material "mtl_steel"
        {
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_steel/OpenPBR.outputs:out>

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.35, 0.36, 0.38)
                float inputs:base_metalness = 1
                token outputs:out
            }
        }
    }

    def Mesh "part"
    {
        uniform token subsetFamily:materialBind:familyType = "partition"

        def GeomSubset "faces_steel" ( prepend apiSchemas = ["MaterialBindingAPI"] )
        {
            uniform token elementType = "face"
            uniform token familyName = "materialBind"
            int[] indices = [0, 1]
            rel material:binding = </Asset/Looks/mtl_steel>
        }

        def GeomSubset "faces_rubber"
        {
            uniform token elementType = "face"
            uniform token familyName = "materialBind"
            int[] indices = [2, 3]
        }
    }
}
```

`faces_rubber` is reported. Once a GPrim has material-bind subsets, each subset has to resolve a
material, and `part` binds nothing for `faces_rubber` to inherit.

### Invalid: a collection-based binding

```usd
def Xform "Root" ( prepend apiSchemas = ["MaterialBindingAPI"] )
{
    # reported: a collection-based binding
    rel material:binding:collection:full:metals = [
        </Root/Looks/mtl_steel>, </Root.collection:metals> ]

    def Scope "Looks"
    {
        def Material "mtl_steel"
        {
            token outputs:mtlx:surface.connect = </Root/Looks/mtl_steel/OpenPBR.outputs:out>

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.35, 0.36, 0.38)
                float inputs:base_metalness = 1
                token outputs:out
            }
        }
    }

    def Mesh "part" ( prepend apiSchemas = ["MaterialBindingAPI"] )
    {
        rel material:binding = </Root/Looks/mtl_steel>
    }
}
```

The collection binding is authored on an ancestor `Xform`, which is where one is normally placed. It
has to be on a defined prim to be reached: an `over` with no corresponding `def` is not visited by
the traversal, so a collection binding authored on one is not reported.

A collection binding does resolve: `UsdShadeMaterialBindingAPI.ComputeBoundMaterial` follows one, in
core USD 25.11 and 26.08 alike. It is still not permitted, because it lives on an ancestor and names
its members through a `UsdCollectionAPI` include/exclude expression, so answering which material a
mesh uses means resolving that expression against the composed stage, and a layer added downstream
can change the answer without touching either the mesh or the material.

### Invalid: a binding strength override, reported as a warning

```usd
def Xform "Asset" ( prepend apiSchemas = ["MaterialBindingAPI"] )
{
    rel material:binding = </Asset/Looks/mtl_steel> (
        bindMaterialAs = "strongerThanDescendants"
    )

    def Scope "Looks"
    {
        def Material "mtl_steel"
        {
            token outputs:mtlx:surface.connect = </Asset/Looks/mtl_steel/OpenPBR.outputs:out>

            def Shader "OpenPBR"
            {
                uniform token info:id = "ND_open_pbr_surface_surfaceshader"
                color3f inputs:base_color = (0.35, 0.36, 0.38)
                float inputs:base_metalness = 1
                token outputs:out
            }
        }
    }

    def Mesh "part"
    {
    }
}
```

`part` inherits the binding and resolves a material, so the only finding is the strength override on
`/Asset`. The requirement states this as a SHOULD, so it is raised at warning severity.

## For more information

- [MaterialBindingAPI](https://openusd.org/dev/api/class_usd_shade_material_binding_a_p_i.html)
- [UsdPreviewSurface Specification](https://openusd.org/release/spec_usdpreviewsurface.html)

## How to comply

- Use the MaterialBindingAPI to assign materials to geometry, directly or on an ancestor.
- Bind through `material:binding` or `material:binding:full`; do not use collection-based bindings.
- Where a GPrim has material-bind `GeomSubset` children, bind each subset, or bind the GPrim
  itself so that a subset authoring no binding of its own inherits it.
- Leave binding strength at the default unless there is a reason to override it.
- Where an asset binds different materials per purpose, bind every renderable prim for the `full`
  purpose as well as the `preview` purpose.
