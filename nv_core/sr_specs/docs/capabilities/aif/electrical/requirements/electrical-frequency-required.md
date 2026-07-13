# electrical-frequency-required

| Code     | EL.003 |
|----------|--------|
| Validator| {oav-validator-latest-link}`el-003` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

AC-powered equipment must declare its input frequency. The attribute name varies by equipment class.

## Description

Input frequency specifies whether the equipment operates on 50 Hz or 60 Hz power, which varies by region. Together with EL.001 (voltage) and EL.002 (power rating), it fully characterizes the AC electrical input requirements.

## Why is it required?

- Required for verifying regional electrical compatibility in facility models
- Used by electrical simulation runtimes to validate power source compatibility
- 50 Hz vs. 60 Hz incompatibility is a hard constraint that cannot be discovered without this attribute

## Attribute Mapping

| Equipment Class | Attribute |
|----------------|-----------|
| CDU | `aif:spec:frequency` |
| CRAH | `aif:spec:electricalFrequency` |
| UPS | `aif:spec:electricalInputFrequency` |

## Applies to

Equipment with `aif:core:assetClass` = `CDU`, `CRAH`, or `UPS`.

## Examples

```usda
# CDU (50 Hz)
def Xform "CW375" {
    float aif:spec:frequency = 50.0
}

# CRAH (60 Hz)
def Xform "CRAH500" {
    float aif:spec:electricalFrequency = 60.0
}

# UPS (50 Hz)
def Xform "UPS5000" {
    float aif:spec:electricalInputFrequency = 50.0
}
```

## How to comply

Set the appropriate attribute for your equipment class on the default prim of the `*Properties.usda` sublayer, using the value from the equipment datasheet in Hz (typically 50 or 60).

## Related requirements

- EL.001 `nominal-voltage-required`: required alongside frequency for complete electrical characterization
- EL.002 `power-rating-required`: required alongside frequency for complete electrical characterization
- AM.007 `equipment-class-template-compliance`: validates the full electrical attribute set
- AM.002 `asset-class-required`: `aif:core:assetClass` must be set for the validator to select the correct attribute name

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
