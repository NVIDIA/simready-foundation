# corrective-transforms

| Code     | UN.004 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`correctness` |

## Summary

Must apply corrective transforms for different units

## Description

When composing assets with different linear units, corrective transformations must be applied to ensure correct scaling.

## Why is it required?

- Prevents incorrect scaling when composing assets

## Examples

```usd
# Invalid: No corrective transform for different units
#usda 1.0
(
    metersPerUnit = 0.01  # Stage in centimeters
)

def Xform "Reference" (
    references = @asset_in_meters.usd@  # Asset in meters
)
{
}

# Valid: Compensating transform applied
#usda 1.0
(
    metersPerUnit = 0.01  # Stage in centimeters
)

def Xform "Reference" (
    references = @asset_in_meters.usd@  # Asset in meters
)
{
    double3 xformOp:scale = (100, 100, 100)
    uniform token[] xformOpOrder = ["xformOp:scale"]
}
```

## How to comply

- Manually apply appropriate scale transformations
- In Omniverse, use the [Stage Metrics Extension](https://docs.omniverse.nvidia.com/extensions/latest/ext_metrics_assembler.html) or [Edit Stage Metrics Operation in Omniverse Scene Optimizer](https://docs.omniverse.nvidia.com/extensions/latest/ext_scene-optimizer/operations.html#edit-stage-metrics)

## For More Information

- [USD Stage Metrics Documentation](https://openusd.org/release/api/usd_page_front.html#UsdGeomStageMetrics) 