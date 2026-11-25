# physical-dimensions-metadata-0.3

| Code | AM.009 |
|---|---|
| Validator | {oav-validator-latest-link}`am-009` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

The default prim of the Properties sublayer must have `aif:core:width`,
`aif:core:depth`, `aif:core:height`, `aif:core:weight`,
`aif:core:installationClearance` and `aif:core:accessibilityRequirement`.

## Description

Width, depth and height are the equipment dimensions for AIF 0.3. When migrating
from AIF 0.1 or 0.2, remove `aif:core:overallGeometryDimensions` from the
Properties sublayer and any layer that contributes it to the composed default
prim. AM.009 rejects a declaration of that property, including one without a value.

## Why is it required?

Layout tools use the three dimensions to place equipment. The clearance values
reserve room for installation and service. Using the scalar dimensions as the
source for extents lets authors maintain each measurement in one place.

## Examples

```usda
def Xform "Generic_CRAH" {
    float aif:core:width = 600
    float aif:core:depth = 800
    float aif:core:height = 2000
    float aif:core:weight = 450
    float aif:core:installationClearance = 600
    float aif:core:accessibilityRequirement = 1000
}
```

For this asset, the root-layer `asset_extents` is `(0.6, 0.8, 2.0)` in metres.
Omitting `aif:core:depth` fails AM.009.

## How to comply

Author all six attributes as `float` values from the equipment datasheet.
Use millimetres for dimensions and clearances and kilograms for weight.
Derive `asset_extents` in `(width, depth, height)` order by dividing each
scalar dimension by 1,000. [AM.008](equipment-class-template-compliance-0.3.md)
checks the USD types of the authored attributes.
