# material-shader-inputs

| Code     | VM.BIND.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-bind-002` |
| Compatibility | {compatibility}`Open USD`  |
| Tags     | {tag}`correctness` |

## Summary

Shader inputs must use the type their specification declares and hold a finite value.

## Description

Every authored shader input MUST hold the type its specification declares, and MUST NOT hold a
NaN or an Infinity in any component.

The specification is the MDL module named by `info:mdl:sourceAsset`, or the definition
`info:id` resolves to.

**Types.** Against an `info:id` definition the comparison is on the underlying `Tf.Type`, so
`color3f` and `float3` are the same type.

**Finiteness.** This applies to any input with floating-point components, not only inputs typed
`float`. A vector, color, matrix or array is flattened and each component tested, so a NaN in
one channel of a `float3` normal is reported against that component. Booleans and integers are
exempt: neither can hold a non-finite value.

The value is read wherever the constant is authored. An input connected to an interface input
on the enclosing `Material` is followed to that interface input, and the report names the
attribute holding the value.

Comparing an MDL input against its module needs a runtime that can parse MDL. Where that
runtime is absent, the type comparison is skipped for MDL shaders. Finiteness still applies,
and shaders identified by `info:id` are still compared against their definition.

### Finiteness and range

A non-finite value is not out of range, so the two questions are separate and one authored
value produces one finding.

| Question | Owned by |
|---|---|
| Is the value finite? | this requirement, on every numeric input of every shader |
| Is a finite value inside its physical range? | `VM.PBR.002`, on the OpenPBR surface inputs it bounds |

`VM.PBR.002` skips a non-finite value, so an authored `nan` on `base_weight` is reported once,
here.

A type the OpenPBR nodedef does not declare is reported here and by `VM.PBR.003`. Either
requirement can be enabled without the other.

## Why is it required?

- A type the shader definition does not declare produces incorrect visual output, or a runtime
  error in a simulation environment
- A NaN or an Infinity breaks rendering
- Types matching the declaration let a material move between tools without re-authoring

## Examples

### Valid: every input has its declared type and a finite value

```usd
def Material "ValidPreview"
{
    token outputs:surface.connect = </ValidPreview/Surface.outputs:surface>

    def Shader "Surface"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
        float inputs:metallic = 0.0
        float inputs:roughness = 0.5
        token outputs:surface
    }
}
```

### Valid: an MDL shader with the asset and float types its module declares

```usd
def Material "ValidMdl"
{
    token outputs:mdl:surface.connect = </ValidMdl/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        asset inputs:diffuse_texture = @./textures/bracket_basecolor.png@
        float inputs:metallic_constant = 1.0
        float inputs:reflection_roughness_constant = 0.5
        token outputs:out
    }
}
```

### Invalid: an input with a type its declaration does not allow

`roughness` is declared `float` by `UsdPreviewSurface` and authored here as a color.

```usd
def Material "WrongType"
{
    token outputs:surface.connect = </WrongType/Surface.outputs:surface>

    def Shader "Surface"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
        color3f inputs:roughness = (0.5, 0.5, 0.5)
        token outputs:surface
    }
}
```

### Invalid: a NaN reaching the surface through the material interface

The constant sits on the `Material`, one connection away from the input it applies to. The finding
names both the shader input and the interface input the value came from.

```usd
def Material "NonFinite"
{
    float inputs:roughness = nan

    token outputs:surface.connect = </NonFinite/Surface.outputs:surface>

    def Shader "Surface"
    {
        uniform token info:id = "UsdPreviewSurface"
        color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
        float inputs:roughness.connect = </NonFinite.inputs:roughness>
        token outputs:surface
    }
}
```

### Invalid: a NaN in one component of a vector input

```usd
def Material "NonFiniteNormal"
{
    token outputs:mtlx:surface.connect = </NonFiniteNormal/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float3 inputs:geometry_normal = (0, nan, 1)
        token outputs:out
    }
}
```

### Invalid: a NaN on an MDL shader input

```usd
def Material "NonFiniteMdl"
{
    token outputs:mdl:surface.connect = </NonFiniteMdl/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./OmniPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "OmniPBR"
        float inputs:reflection_roughness_constant = nan
        token outputs:out
    }
}
```

### Invalid: an MDL source asset with no value

Nothing names the module, so there is no specification to compare the inputs against.

```usd
def Material "EmptyMdl"
{
    token outputs:mdl:surface.connect = </EmptyMdl/Shader.outputs:out>

    def Shader "Shader"
    {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @@
        token outputs:out
    }
}
```

## How to comply

### MDL shaders
- Use the USD type each parameter is declared with in the MDL module, such as `asset`, `float` or
  `color3f`
- Point `info:mdl:sourceAsset` at the `.mdl` file and author
  `info:mdl:sourceAsset:subIdentifier`

### Built-in shaders
- Use the types the shader's specification declares, such as the UsdPreviewSurface specification for
  `UsdPreviewSurface` and the MaterialX nodedef for an `ND_*` id

### Both
- Author a finite value on every numeric input, including each component of a vector or color, and
  wherever the constant is authored — an interface input on the `Material` is checked as the shader
  input's own value would be
- Keep OpenPBR surface values inside the bounds
  [`VM.PBR.002`](/capabilities/visualization/materials/requirements/material-pbr-parameter-ranges)
  sets

## For More Information
- [VM.PBR.002 — OpenPBR parameter ranges](/capabilities/visualization/materials/requirements/material-pbr-parameter-ranges)
- [VM.PBR.003 — shading network structure](/capabilities/visualization/materials/requirements/material-shading-network-structure)
- [USD Shader Documentation](https://openusd.org/release/api/class_usd_shade_shader.html)
- [UsdPreviewSurface Specification](https://openusd.org/release/spec_usdpreviewsurface.html)
- [MDL Specification](https://www.nvidia.com/en-us/design-visualization/technologies/material-definition-language/)
- [USD Value Types](https://openusd.org/release/api/sdf_page_front.html#sdf_value_types)
