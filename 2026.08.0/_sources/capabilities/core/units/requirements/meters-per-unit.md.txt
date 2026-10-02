# meters-per-unit

| Code     | UN.002 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`un-002` |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`essential` |

## Summary

Stage must specify metersPerUnit to define the linear unit scale

## Description

The stage must have a valid metersPerUnit value specified to define the linear unit scale for all geometry in the stage.

## Why is it required?

- Corrective transforms can only be created if units are defined
- Physics simulations require correct physical dimensions

## Examples

```usd
# Invalid: No metersPerUnit specified
#usda 1.0
(
)

# Valid: metersPerUnit specified
#usda 1.0
(
    metersPerUnit = 0.01
)
```

## How to comply

- Set stage metersPerUnit value
- Common values:
  - 1.0 for meters
  - 0.01 for centimeters
  - 0.001 for millimeters

## Related Requirements

- [corrective-transforms](/capabilities/core/units/requirements/corrective-transforms)

## For More Information

- [Omniverse Units Documentation](https://docs.omniverse.nvidia.com/usd/latest/learn-openusd/independent/units.html)
- [USD Stage Metrics API Documentation](https://openusd.org/dev/api/group___usd_geom_linear_units__group.html) 

