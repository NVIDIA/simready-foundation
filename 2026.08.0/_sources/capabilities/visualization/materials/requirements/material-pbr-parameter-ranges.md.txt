# material-pbr-parameter-ranges

| Code     | VM.PBR.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`vm-pbr-002` |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

OpenPBR input attributes must hold values within their defined min/max.

## Description

On every OpenPBR surface, these input attributes MUST hold a value within the min/max given:

| Min/max | Input attributes |
|---|---|
| [0, 1] | `base_weight`, `base_metalness`, `base_diffuse_roughness`, `specular_weight`, `specular_roughness`, `specular_roughness_anisotropy`, `transmission_weight`, `subsurface_weight`, `coat_weight`, `coat_roughness`, `coat_roughness_anisotropy`, `coat_darkening`, `thin_film_weight`, `fuzz_weight`, `fuzz_roughness`, `geometry_opacity` |
| Each component in [0, 1], linear | `base_color`, `specular_color`, `transmission_color`, `subsurface_color`, `coat_color`, `fuzz_color`, `emission_color` |
| [1.0, 3.0] | `specular_ior`, `coat_ior` |
| >= 0 | `emission_luminance` |

OpenPBR input attributes which are not listed in this table do not have min/max values.
`thin_film_thickness`, `thin_film_ior`, `transmission_depth`, `subsurface_radius` and the
dispersion and scatter attributes hold physical quantities with no defined limit.
`geometry_normal`, `geometry_tangent` and the coat equivalents hold direction vectors.
`geometry_thin_walled` is a boolean.

An input attribute the resolved OpenPBR nodedef does not declare is not checked.

The authored value is resolved through the connection. Where a surface shader input is
connected to an interface input on the `Material`, the min/max applies to the value authored on
that interface input. An input attribute connected to a shader output has no authored value;
the min/max applies to the value the shading network computes.

A NaN or an Infinity is not out of range, so it is not checked here. `VM.BIND.002` reports it,
on every numeric input attribute of every shader.

Authored values SHOULD also suit the material class, `base_metalness = 0` for dielectrics and
`1` for metals. This requirement does not constrain that.

### Refractive index

An index below 1.0 is below vacuum. The upper bound of 3.0 covers the dielectrics a scene
realistically contains, up to diamond at 2.42 and moissanite at 2.65.

Materials with a higher real index are conductors: silicon at 3.42, germanium at 4.00. A
conductor's response is not a refraction term, so raising `specular_ior` to the published figure
misrepresents it. Set `base_metalness = 1` and use `base_color` for the response. Extreme
refraction is also expensive to path-trace, which matters for the synthetic camera data these
assets feed.

Typical values by material class. These are guidance, not constraints:

| Material class | `base_metalness` | Typical `specular_ior` |
|---|---|---|
| Air, vacuum | 0 | 1.00 |
| Water, oils | 0 | 1.33 – 1.45 |
| Plastics, resins | 0 | 1.46 – 1.60 |
| Standard glass, optics | 0 | 1.49 – 1.65 |
| Flint and lead glass | 0 | 1.66 – 1.85 |
| Gemstones (diamond, moissanite) | 0 | 2.42 – 2.65 |
| Semiconductors, metals | 1 | not applicable; use `base_color` |

## Why is it required?
- Values outside the min/max produce non-physical renders
- Unbounded values break domain randomization (Replicator) and yield invalid training data
- Silent clamping hides authoring errors

## Examples

### Valid: an in-range dielectric

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color = (0.35, 0.36, 0.38)
        float inputs:base_metalness = 0
        float inputs:specular_roughness = 0.4
        float inputs:specular_ior = 1.5
        token outputs:out
    }
}
```

### Valid: the same silicon authored as a conductor

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color = (0.35, 0.36, 0.38)
        float inputs:base_metalness = 1
        float inputs:specular_roughness = 0.2
        token outputs:out
    }
}
```

### Valid: a surface input driven by a texture

`specular_roughness` resolves to a shader output, so there is no authored constant to range check.

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "RoughnessTex"
    {
        uniform token info:id = "ND_image_float"
        asset inputs:file = @./textures/bracket_roughness.png@
        float outputs:out
    }

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float inputs:specular_roughness.connect = </mtl_bracket/RoughnessTex.outputs:out>
        token outputs:out
    }
}
```

### Invalid: a unit-range input outside [0, 1]

Both inputs are reported, one for being above 1 and one for being below 0.

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float inputs:base_metalness = 1.5
        float inputs:specular_roughness = -0.2
        token outputs:out
    }
}
```

### Invalid: a color component outside [0, 1]

The report names the component, not the whole color.

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        color3f inputs:base_color = (1.4, 0.36, 0.38)
        token outputs:out
    }
}
```

### Invalid: an out-of-range value authored on the material interface

The shader input holds no constant of its own, and the value it connects to is checked as though it
did.

```usd
def Material "mtl_bracket"
{
    float inputs:specular_roughness = 1.6

    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float inputs:specular_roughness.connect = </mtl_bracket.inputs:specular_roughness>
        token outputs:out
    }
}
```

### Invalid: silicon's real index authored as a dielectric refraction

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float inputs:base_metalness = 0
        float inputs:specular_ior = 3.42
        token outputs:out
    }
}
```

### Invalid: negative emission

```usd
def Material "mtl_bracket"
{
    token outputs:mtlx:surface.connect = </mtl_bracket/OpenPBR.outputs:out>

    def Shader "OpenPBR"
    {
        uniform token info:id = "ND_open_pbr_surface_surfaceshader"
        float inputs:emission_luminance = -50
        token outputs:out
    }
}
```

## How to comply
- Author values within the min/max in the table above.
- Author a material whose real-world index is above 3.0 as a conductor: set
  `base_metalness = 1` and express the response through `base_color` instead of raising
  `specular_ior`.
- Define domain-randomization ranges as subsets of these min/max values.

## For More Information
- [OpenPBR Surface specification](https://academysoftwarefoundation.github.io/OpenPBR/)
- [`VM.PBR.001`](/capabilities/visualization/materials/requirements/material-final-surface) —
  OpenPBR material output
- [`VM.BIND.002`](/capabilities/visualization/materials/requirements/material-shader-inputs) —
  shader input types and finiteness
