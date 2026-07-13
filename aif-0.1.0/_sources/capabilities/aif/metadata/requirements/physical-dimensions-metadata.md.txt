# physical-dimensions-metadata

| Code     | AM.004 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-004` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

The default prim must have all seven physical dimension attributes: `aif:core:height`, `aif:core:width`, `aif:core:depth`, `aif:core:weight`, `aif:core:overallGeometryDimensions`, `aif:core:installationClearance`, and `aif:core:accessibilityRequirement`.

## Description

Physical dimension metadata enables simulation runtimes to reason about equipment placement, clearance requirements, and spatial constraints in the data center layout without needing to inspect geometry directly.

## Why is it required?

- Enables automated space planning and collision detection
- `installationClearance` and `accessibilityRequirement` are needed for maintenance simulation
- `overallGeometryDimensions` provides a machine-readable bounding box independent of geometry

## Attributes

| Attribute | Type | Unit | Description |
|-----------|------|------|-------------|
| `aif:core:height` | float | mm | Equipment height |
| `aif:core:width` | float | mm | Equipment width |
| `aif:core:depth` | float | mm | Equipment depth |
| `aif:core:weight` | float | kg | Equipment weight |
| `aif:core:overallGeometryDimensions` | float3 | mm | Bounding box (W×D×H) |
| `aif:core:installationClearance` | float | mm | Required installation clearance |
| `aif:core:accessibilityRequirement` | float | mm | Required service clearance |

## Examples

```usda
def Xform "CW375" {
    float aif:core:height = 2000.0
    float aif:core:width = 600.0
    float aif:core:depth = 800.0
    float aif:core:weight = 450.0
    float3 aif:core:overallGeometryDimensions = (600.0, 800.0, 2000.0)
    float aif:core:installationClearance = 600.0
    float aif:core:accessibilityRequirement = 1000.0
}
```

## How to comply

Set all seven attributes on the default prim of the `*Properties.usda` sublayer with values from the equipment datasheet. All linear dimensions are in millimeters (mm); weight is in kilograms (kg).

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before these attributes can be set
- AM.002 `asset-class-required`: required alongside dimension attributes for full equipment characterization

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
