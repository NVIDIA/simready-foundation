# newton-sdf-attributes

| Code     | NEWTON.COL.002 |
|----------|----------------|
| Validator| NewtonSDFAttributesChecker |
| Compatibility | {compatibility}`Newton` |
| Tags     | {tag}`essential` |

## Summary

Authored Newton SDF attributes must be valid.

## Description

A `UsdGeom.Gprim` prim with `NewtonSDFCollisionAPI` may author Newton SDF attributes to configure SDF collision, port PhysX SDF settings, or opt into hydroelastic contact. Newton can apply schema defaults for unauthored SDF attributes, so this requirement validates authored values rather than requiring every tuning value to be present.

When authored, the following attributes must use valid values:

- `newton:contactMargin`
- `newton:contactGap`
- `newton:sdfMaxResolution`
- `newton:sdfNarrowBandInner`
- `newton:sdfNarrowBandOuter`
- `newton:sdfPadding`
- `newton:sdfTextureFormat`
- `newton:sdfTargetVoxelSize`
- `newton:hydroelasticEnabled`
- `newton:hydroelasticStiffness`

The numeric values must be valid for SDF generation: contact distances and padding must be non-negative, maximum resolution must be a positive integer divisible by 8, target voxel size must be positive, and the narrow-band inner value must be less than the narrow-band outer value when both are authored. Valid SDF texture formats are `uint8`, `uint16`, and `float32`. If `newton:hydroelasticStiffness` is authored, it must be positive; authoring it alone does not enable hydroelastic contact.

`newton:hydroelasticEnabled`, when authored, must be a boolean. Newton requires an SDF source at parse time when hydroelastic contact is enabled, so a prim with `newton:hydroelasticEnabled = true` should also author an SDF source (`newton:sdfMaxResolution` or `newton:sdfTargetVoxelSize`). A mesh may instead carry an attached `mesh.sdf`, which cannot be detected from USD authoring, so a missing SDF source is reported as a warning rather than a failure.

## Why is it required?

Newton uses these attributes to configure the SDF collider that participates in contact generation. Invalid values can produce missing collision, unstable contact behavior, or an SDF representation that differs from the intended source collision settings.

## Examples

```usd
# Valid: Newton SDF API with no authored tuning values; Newton applies schema defaults
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["NewtonSDFCollisionAPI"]
)
{
}
```

```usd
# Invalid: authored Newton SDF values are malformed
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["NewtonSDFCollisionAPI"]
)
{
    float newton:contactMargin = -0.002
    uniform int newton:sdfMaxResolution = 250
    uniform token newton:sdfTextureFormat = "rgba8"
}
```

```usd
# Valid: Newton SDF API with authored Newton SDF attributes
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["NewtonSDFCollisionAPI"]
)
{
    float newton:contactMargin = 0.002
    float newton:contactGap = 0.003
    uniform int newton:sdfMaxResolution = 256
    uniform float newton:sdfNarrowBandInner = -0.02
    uniform float newton:sdfNarrowBandOuter = 0.02
    uniform float newton:sdfPadding = 0.02
    uniform token newton:sdfTextureFormat = "uint16"
}
```

```usd
# Valid: Newton SDF collider with hydroelastic contact enabled
def Mesh "CollisionMesh" (
    prepend apiSchemas = ["NewtonSDFCollisionAPI"]
)
{
    uniform int newton:sdfMaxResolution = 256
    bool newton:hydroelasticEnabled = true
    float newton:hydroelasticStiffness = 10000000
}
```

## How to comply

When Newton SDF attributes are authored, keep contact distances and padding non-negative, use a positive SDF maximum resolution divisible by 8, use valid texture format tokens, and ensure `newton:sdfNarrowBandInner < newton:sdfNarrowBandOuter` when both bands are authored. When opting into hydroelastic contact (`newton:hydroelasticEnabled = true`), author an SDF source (`newton:sdfMaxResolution` or `newton:sdfTargetVoxelSize`) unless the mesh carries an attached `mesh.sdf`. Leave tuning attributes unauthored when Newton schema defaults should apply.

## For More Information

- [Newton USD parsing documentation](https://github.com/newton-physics/newton/blob/main/docs/concepts/usd_parsing.rst)
- Newton collision concepts: `docs/concepts/collisions.rst`
