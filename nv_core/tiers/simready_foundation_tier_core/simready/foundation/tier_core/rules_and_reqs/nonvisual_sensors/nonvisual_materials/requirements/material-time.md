# material-time

| Code     | NVM.006 |
|----------|---------|
| Validator| {oav-validator-latest-link}`nvm-006` |
| Compatibility | {compatibility}`rtx`  |
| Tags     | {tag}`correctness` |

## Summary

Properties must not be time-varying

## Description

Non-visual material attributes must not contain time samples. These attributes should have static values that don't change over time, as sensor simulation typically requires consistent material properties.

## Why is it required?

- Ensures consistent sensor simulation behavior
- Prevents unexpected changes in material properties during simulation
- Required for non-visual sensor compatibility

## Examples

```usd
# Invalid: Time-varying non-visual attributes
def Material "TimeVaryingMaterial" {
    token outputs:surface.connect = </TimeVaryingMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "steel"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["emissive"]
    
    # Invalid: Time-varying attributes
    token omni:simready:nonvisual:base.timeSamples = {
        0: "steel",
        1: "plastic",  # This will cause validation failure
        2: "glass"
    }
}

# Valid: Static non-visual attributes
def Material "StaticMaterial" {
    token outputs:surface.connect = </StaticMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "steel"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["emissive"]
    # All attributes have static values - no time samples
}
```

## How to comply

Ensure that all non-visual material attributes (`omni:simready:nonvisual:base`, `omni:simready:nonvisual:coating`, `omni:simready:nonvisual:attributes`) have static values without time samples.

## For More Information

- [Non-Visual Materials Capability](../capability-nonvisual_materials.md)
- [Material Base Requirement](material-base.md)
- [Material Coating Requirement](material-coating.md)
