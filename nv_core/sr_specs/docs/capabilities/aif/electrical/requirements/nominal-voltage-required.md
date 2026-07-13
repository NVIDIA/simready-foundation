# nominal-voltage-required

| Code     | EL.001 |
|----------|--------|
| Validator| {oav-validator-latest-link}`el-001` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

AC-powered equipment must declare its nominal input voltage. The attribute name varies by equipment class.

## Description

Nominal input voltage is the primary electrical specification used by data center power planning tools. The attribute name differs across equipment classes due to upstream CSV template inconsistencies. See the note below.

## Why is it required?

- Required for power capacity planning and electrical compatibility checks in facility models
- Used by electrical simulation runtimes to validate that the facility's power supply matches the equipment's rated voltage
- Without this attribute, validators cannot determine whether AC-powered equipment is compatible with the facility's electrical infrastructure

## Attribute Mapping

| Equipment Class | Attribute |
|----------------|-----------|
| CDU | `aif:spec:nominalVoltage` |
| CRAH | `aif:spec:electricalNominalVoltage` |
| UPS | `aif:spec:electricalInputVoltage` |

## Applies to

Equipment with `aif:core:assetClass` = `CDU`, `CRAH`, or `UPS`. Compute Rack equipment (e.g. GB300) is excluded because it uses DC power profiles, not AC parameters.

## Note on naming inconsistency

Electrical attribute names are not yet harmonized across equipment classes. Until upstream CSV templates are updated to a single naming convention, validators must use the per-class mapping table above.

## Examples

```usda
# CDU
def Xform "CW375" {
    float aif:spec:nominalVoltage = 400.0
}

# CRAH
def Xform "CRAH500" {
    float aif:spec:electricalNominalVoltage = 480.0
}

# UPS
def Xform "UPS5000" {
    float aif:spec:electricalInputVoltage = 480.0
}
```

## How to comply

Set the appropriate attribute for your equipment class on the default prim of the `*Properties.usda` sublayer, using the value from the equipment datasheet in volts (V).

## Related requirements

- AM.007 `equipment-class-template-compliance`: validates the full electrical attribute set; EL.001 isolates this attribute for finer-grained reporting
- AM.002 `asset-class-required`: `aif:core:assetClass` must be set for the validator to select the correct attribute name
- EL.002 `power-rating-required`: required alongside voltage for complete electrical characterization
- EL.003 `electrical-frequency-required`: required alongside voltage for complete electrical characterization
- EL.004 `electrical-connection-points`: verifies that the electrical connection is represented as geometry

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
