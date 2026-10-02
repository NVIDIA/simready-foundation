# kilograms-per-unit

| Code     | UN.003 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`correctness` |

## Summary

Stage must specify kilogramsPerUnit to define the mass unit scale, if physics objects are present in the stage.

## Description

If there are physics objects in the stage, the stage must have a valid kilogramsPerUnit value specified to define the mass unit scale.

## Why is it required?

- Mass-based physics simulations require defined units
- Inertial calculations depend on correct mass units

## Examples

```usd
# Invalid: No kilogramsPerUnit specified
#usda 1.0
(
    metersPerUnit = 0.01
)

# Valid: kilogramsPerUnit specified
#usda 1.0
(
    metersPerUnit = 0.01
    kilogramsPerUnit = 0.001
)
```

## How to comply

- Set stage kilogramsPerUnit value
- Common values:
  - 1.0 for kilograms
  - 0.001 for grams

## Related Requirements

- [physics-rigid-bodies](/capabilities/physics_bodies/physics_bodies.md)

## For More Information

- [USD Phyiscs Documentation](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_units)
- [USD Physics Stage Metrics API Documentation](https://openusd.org/dev/api/usd_physics_2metrics_8h.html)