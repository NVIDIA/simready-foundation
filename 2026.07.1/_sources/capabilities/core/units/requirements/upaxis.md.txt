# upaxis

| Code     | UN.001 |
|----------|-----------|  
| Validator| {oav-validator-latest-link}`un-001` |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`essential` |

## Summary

Stage must specify upAxis to define the orientation of the stage

## Description

The stage must have a valid upAxis value specified to define the orientation of the stage.

## Why is it required?

- Camera orientation and navigation is dependent on upAxis
- Asset assembly orientation is dependent on upAxis
- Corrective transforms can only be created if upAxis is defined

## Examples

```usd
# Invalid: No upAxis specified
#usda 1.0
(
)

# Valid: upAxis specified
#usda 1.0
(
    upAxis = "Z"
)
```

## How to comply

- Set stage upAxis value
- Common values:
  - Y
  - Z

## Related Requirements

- [corrective-transforms](/capabilities/core/units/requirements/corrective-transforms)

## For More Information

- [USD Upaxis Documentation](https://openusd.org/dev/api/group___usd_geom_up_axis__group.html) 
- [Omniverse Upaxis Documentation](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/units.html)