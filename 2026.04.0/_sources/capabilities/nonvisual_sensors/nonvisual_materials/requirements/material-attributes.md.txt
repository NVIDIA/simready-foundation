# material-attributes

| Code     | NVM.001 |
|----------|---------|
| Validator| {oav-validator-latest-link}`nvm-001` |
| Compatibility | {compatibility}`rtx`  |
| Tags     | {tag}`essential` |

## Summary

Materials must specify additional "non-visual" material attributes

## Description

Every geometry prim with a computed purpose of "render" or "default" must have non-visual material attributes assigned per visual material assigned. This includes the `omni:simready:nonvisual:attributes` attribute which is a token array containing additional material properties that affect sensor response.

## Why is it required?

- Enables accurate sensor simulation (radar, lidar, thermal imaging)
- Provides material properties that affect sensor response
- Required for non-visual sensor compatibility

## Examples

```usd
# Invalid: Missing non-visual attributes
def Material "BasicMaterial" {
    token outputs:surface.connect = </BasicMaterial/Surface.outputs:surface>
    
    def Shader "Surface" {
        uniform token info:id = "UsdPreviewSurface"
        # Missing omni:simready:nonvisual:attributes
    }
}

# Valid: With non-visual attributes
def Material "SensorMaterial" {
    token outputs:surface.connect = </SensorMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "metal"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["emissive", "retroreflective"]
    
    def Shader "Surface" {
        uniform token info:id = "UsdPreviewSurface"
    }
}
```

## How to comply

Add the `omni:simready:nonvisual:attributes` attribute to materials bound to geometry prims. The attribute should be a token array containing valid values from the allowed list.

## For More Information

- [Non-Visual Materials Capability](../capability-nonvisual_materials.md)
- [Material Base Requirement](material-base.md)
- [Material Coating Requirement](material-coating.md)
