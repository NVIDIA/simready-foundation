# material-mdl-source-asset

| Code     | VM.MDL.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-mdl-001` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

An MDL shader's `info:mdl:sourceAsset` must name an existing `.mdl` file by an anchored path.

## Description

The subject is a `Shader` prim inside a `Material` whose `info:implementationSource` is
`sourceAsset`. Such a shader takes its implementation from an MDL module on disk, and
`info:mdl:sourceAsset` is the path to that module. A shader that does not declare
`sourceAsset` is outside this requirement.

The path must:

1. Be authored on the shader
2. Be non-empty
3. End in `.mdl`
4. Start with `./` or `../`, or be absolute
5. Resolve to a file that exists

A path that is neither anchored nor absolute is resolved through the MDL search path, so which module it names depends on how the runtime is configured. An absolute path resolves deterministically and is not reported here; [`AA.001`](/capabilities/core/atomic_asset/requirements/anchored-asset-paths) covers it as a portability matter for every asset reference.

Conditions 3 to 5 are read independently, so one path can be reported under more than one of
them.

### Modules the runtime ships

Conditions 4 and 5 do not apply to an MDL module the runtime ships and resolves for itself —
`OmniPBR.mdl`, `OmniGlass.mdl`, `OmniSurface.mdl` and the rest of that set, including the
`nvidia/core_definitions.mdl` prefixed form. A reference to one is authored as the bare module
name deliberately.

Kit ties an MDL module's identity to its location on disk, so a copy inside the asset is a
different module rather than the same one packaged. The module therefore stays where the
runtime installed it, and the asset names it rather than shipping it. Anchoring such a
reference makes it a layer-relative asset path that USD resolves against the referencing
layer, where nothing is present: `./OmniPBR.mdl` in an asset that does not contain
`OmniPBR.mdl` resolves to nothing at all. The two conditions cannot both be met, which is why
neither is asked.

The set is matched by module name, case-insensitively, so a project-local copy at an explicit
path is treated the same way — that copy cannot be relocated into the asset and remain the
same module.

## Why is it required?
- Broken material references
- Non-portable assets
- Inconsistent rendering

## Examples

The attribute sits on the `Shader` prim, alongside `info:implementationSource` and the
`subIdentifier` naming the material inside the module. It is not prim metadata on the
`Material`.

### Valid: a relative path to a module that is there

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        token outputs:out
    }
}
```

### Invalid: the shader declares `sourceAsset` and authors no path

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        token outputs:out
    }
}
```

### Invalid: the attribute is authored but the path is empty

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        token outputs:out
    }
}
```

`@@` is an authored asset path with nothing in it, which USD resolves to an empty
`Sdf.AssetPath`, not to an absent opinion. The shader declares it resolves through a source
asset and then names none, so nothing loads.

### Invalid: no `.mdl` extension

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/OmniPBR@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        token outputs:out
    }
}
```

This path is reported twice: once for the extension, and once because no file resolves at it.

### Invalid: a path resolved through the MDL search path

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @materials/OmniPBR/OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        token outputs:out
    }
}
```

The module is at the path given, so this is reported for the prefix alone.

### Invalid: the module is not there

```usd
def Material "opaque__metal__bracket"
{
    token outputs:mdl:surface.connect = </opaque__metal__bracket/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./materials/OmniPBR/Unknown.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        token outputs:out
    }
}

# Valid: Parent-relative path to existing MDL
def Material "ValidParentRelative" (
    info:mdl:sourceAsset = @../source_assets/OmniPBR.mdl@
)
{
}
```

## How to comply
- Author `info:mdl:sourceAsset` on every shader that declares `info:implementationSource = "sourceAsset"`
- Give it a path ending in `.mdl`
- Anchor the path with `./` or `../`, so it resolves against the referencing layer rather than the MDL search path
- Leave a module the runtime ships named as it is, and do not package a copy of it
- Ship the module at that path

## For More Information
- [USD Material Documentation](https://openusd.org/release/api/usd_shade_page_front.html) 
- [MDL Search Path](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/mdl_search_path.html)
- [USD Resolver Documentation](https://docs.omniverse.nvidia.com/kit/docs/usd_resolver/latest/docs/resolver-details.html)
