# material-coating

| Code     | NVM.003 |
|----------|---------|
| Validator| {oav-validator-latest-link}`nvm-003` |
| Compatibility | {compatibility}`rtx`  |
| Tags     | {tag}`correctness` |

## Summary

Materials must specify surface coating

## Description

Every geometry prim with a computed purpose of "render" or "default" must have the `omni:simready:nonvisual:coating` attribute assigned per visual material assigned. This attribute specifies the surface coating that affects sensor response.

## Why is it required?

- Enables accurate sensor simulation based on surface properties
- Provides consistent coating classification for sensor systems
- Required for non-visual sensor compatibility

## Examples

```usd
# Invalid: Missing coating specification
def Material "IncompleteMaterial" {
    token outputs:surface.connect = </IncompleteMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "steel"
    token[] omni:simready:nonvisual:attributes = ["emissive"]
    # Missing omni:simready:nonvisual:coating
}

# Valid: With coating specification
def Material "CompleteMaterial" {
    token outputs:surface.connect = </CompleteMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "steel"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["emissive"]
}
```

## How to comply

Add the `omni:simready:nonvisual:coating` attribute to materials bound to geometry prims. The attribute should be a token with a valid value from the allowed list ("none", "paint", "clearcoat", "paint_clearcoat").

## For More Information

- [Non-Visual Materials Capability](../capability-nonvisual_materials.md)
- [Material Base Requirement](material-base.md)
- [Material Attributes Requirement](material-attributes.md)
