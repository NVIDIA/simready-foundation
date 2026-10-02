# meters-per-unit-1

| Code     | UN.007 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`un-007` |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`essential` |

## Summary

Stage must specify metersPerUnit = 1.0 to define the linear unit scale

## Description

The stage must have metersPerUnit set to 1.0 to define the linear unit scale for all geometry in the stage. This ensures consistent unit representation across the stage.

## Examples

```usd
# Invalid: No metersPerUnit specified
#usda 1.0
(
)

# Invalid: metersPerUnit not set to 1.0
#usda 1.0
(
    metersPerUnit = 0.01
)

# Valid: metersPerUnit = 1.0
#usda 1.0
(
    metersPerUnit = 1.0
)
```

## How to comply

- Set stage metersPerUnit value to exactly 1.0
- This represents meters as the base unit
- All geometry and measurements in the stage will be interpreted in meters

## Related Requirements

- [corrective-transforms](/capabilities/core/units/requirements/corrective-transforms)

## For More Information

- [Omniverse Units Documentation](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/units.html)
- [USD Stage Metrics API Documentation](https://openusd.org/dev/api/group___usd_geom_linear_units__group.html) 

