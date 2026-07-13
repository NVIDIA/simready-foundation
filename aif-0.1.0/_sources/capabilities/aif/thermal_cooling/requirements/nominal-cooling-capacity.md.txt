# nominal-cooling-capacity

| Code     | TC.001 |
|----------|--------|
| Validator| {oav-validator-latest-link}`tc-001` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

CDUs and CRAHs must declare `aif:spec:nominalCoolingCapacity`: the rated cooling capacity of the unit.

## Description

`aif:spec:nominalCoolingCapacity` is the single cross-class thermal attribute shared by both CDU and CRAH equipment. While each class has many other thermal attributes validated by AM.007, this attribute is isolated here because it is the primary sizing parameter used by facility planning and thermal simulation tools.

## Why is it required?

- Primary input for data center cooling capacity planning
- Used by thermal simulation runtimes to model heat extraction rates
- Both CDU and CRAH share this attribute, making it a cross-class requirement

## Applies to

Equipment with `aif:core:assetClass` = `CDU` or `CRAH`.

## Examples

```usda
def Xform "CW375" {
    float aif:spec:nominalCoolingCapacity = 375.0
}
```

Value in kW.

## How to comply

Set `aif:spec:nominalCoolingCapacity` on the default prim of the `*Properties.usda` sublayer with the rated cooling capacity from the equipment datasheet.

## Related requirements

- AM.007 `equipment-class-template-compliance`: validates the full CDU/CRAH attribute set; TC.001 isolates this one attribute for finer-grained reporting
- AM.002 `asset-class-required`: `aif:core:assetClass` must be set for this validator to identify cooling equipment
- TC.002 `thermal-cooling-connection-points`: verifies that piping connection points match the cooling metadata

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
