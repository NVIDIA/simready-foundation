# upaxis-z

| Code     | UN.006 |
|----------|-----------|  
| Validator| {oav-validator-latest-link}`un-006` |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`essential` |

## Summary

Stage must specify upAxis = "Z" to define the orientation of the stage

## Description

The stage must have upAxis = "Z" specified to define the Z-up orientation of the stage.  Map based, physics based, and digital twin based simulation can all benefit from establishing a defacto Up direction. Z maybe non-standard to some, but it makes a lot of sense when factoring in real world coordinates.  (i.e. mapping coordinates are: lat, lng, height | x,y,z)

## Examples

```usd
# Invalid: No upAxis specified
#usda 1.0
(
)

# Invalid: Y-up specified
#usda 1.0
(
    upAxis = "Y"
)

# Valid: Z-up specified
#usda 1.0
(
    upAxis = "Z"
)
```

## How to comply

- Set stage upAxis value to "Z"
- This ensures Z-up orientation for the stage

## Related Requirements

- [corrective-transforms](/capabilities/core/units/requirements/corrective-transforms)

## For More Information

- [USD Upaxis Documentation](https://openusd.org/dev/api/group___usd_geom_up_axis__group.html) 
- [Omniverse Upaxis Documentation](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/units.html)