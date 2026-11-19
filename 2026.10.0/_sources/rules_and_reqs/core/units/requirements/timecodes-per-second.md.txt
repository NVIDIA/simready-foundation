# timecodes-per-second

| Code     | UN.005 |
|----------|-----------|
| Validator|  |
| Compatibility | {compatibility}`core-usd`  |
| Tags     | {tag}`correctness` |

## Summary

Stage must specify timeCodesPerSecond, if timesamples are present in the stage.

## Description

The stage must have a valid timeCodesPerSecond value specified to define the time scale for all animated content in the stage.

## Why is it required?

- USD resolves timesample differences when composing layers with different timecodes. This is not possible if timeCodesPerSecond is unspecified and differs from the default value 24, leading to incorrect results
- Default value of 24 may not be appropriate

## Examples

```usd
# Invalid: No timeCodesPerSecond specified
#usda 1.0
(
    metersPerUnit = 0.01
    kilogramsPerUnit = 1.0
)

# Valid: timeCodesPerSecond specified
#usda 1.0
(
    metersPerUnit = 0.01
    kilogramsPerUnit = 1.0
    timeCodesPerSecond = 30
)
```

## How to comply

- Set stage timeCodesPerSecond value
- Common values:
  - 24 for film
  - 30 for video
  - 60 for high frame rate

## For More Information

- [USD Units Documentation](https://openusd.org/release/api/usd_page_front.html#UsdGeomMetrics) 