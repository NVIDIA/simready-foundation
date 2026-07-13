# power-rating-required

| Code     | EL.002 |
|----------|--------|
| Validator| {oav-validator-latest-link}`el-002` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

AC-powered equipment must declare its power rating. The attribute name varies by equipment class.

## Description

Power rating is the primary load specification used by data center power capacity planning tools. The attribute name differs across equipment classes. See the note below.

## Why is it required?

- Required for power capacity planning and load balancing in facility models
- Used by electrical simulation runtimes to model power draw
- Together with EL.001 (voltage) and EL.003 (frequency), fully characterizes the AC electrical input

## Attribute Mapping

| Equipment Class | Attribute |
|----------------|-----------|
| CDU | `aif:spec:powerRating` |
| CRAH | `aif:spec:electricalPowerRating` |
| UPS | `aif:spec:upsRating` |

## Applies to

Equipment with `aif:core:assetClass` = `CDU`, `CRAH`, or `UPS`.

## Note on naming inconsistency

The UPS uses `upsRating` (rated kVA/kW output capacity) rather than an input power rating, reflecting the different role of UPS in the power chain.

## Examples

```usda
# CDU
def Xform "CW375" {
    float aif:spec:powerRating = 15.0
}

# CRAH
def Xform "CRAH500" {
    float aif:spec:electricalPowerRating = 12.0
}

# UPS
def Xform "UPS5000" {
    float aif:spec:upsRating = 500.0
}
```

## How to comply

Set the appropriate attribute for your equipment class on the default prim of the `*Properties.usda` sublayer, using the value from the equipment datasheet in kW (or kVA for UPS `upsRating`).

## Related requirements

- EL.001 `nominal-voltage-required`: required alongside power rating for complete electrical characterization
- EL.003 `electrical-frequency-required`: required alongside power rating for complete electrical characterization
- AM.007 `equipment-class-template-compliance`: validates the full electrical attribute set
- AM.002 `asset-class-required`: `aif:core:assetClass` must be set for the validator to select the correct attribute name

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
