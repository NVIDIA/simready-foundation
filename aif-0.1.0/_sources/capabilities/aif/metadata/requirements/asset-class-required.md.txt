# asset-class-required

| Code     | AM.002 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-002` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

The default prim in the properties sublayer must have an `aif:core:assetClass` attribute identifying the equipment type.

## Description

`aif:core:assetClass` is the fundamental discriminator used by downstream tools and validators to determine which equipment-specific schema applies to an asset. Without it, equipment class template validation (AM.007) and cross-domain checks (TC.002, EL.004) cannot function.

## Why is it required?

- Enables automatic schema selection for AM.007 template compliance
- Required by thermal cooling (TC) and electrical (EL) validators to determine applicable checks
- Allows pipelines to route assets to the correct processing workflow

## Examples

```usda
def Xform "CW375" {
    string aif:core:assetClass = "CDU"
}
```

Valid values: `CDU`, `CRAH`, `UPS`, `compute rack` (or `GB300`, `gb300_rack`, `gb300 rack`)

## How to comply

Set `aif:core:assetClass` on the default prim of the `*Properties.usda` sublayer to the appropriate equipment class string.

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before this attribute can be set
- AM.007 `equipment-class-template-compliance`: uses `aif:core:assetClass` to select the equipment schema
- TC.002 `thermal-cooling-connection-points`: uses `aif:core:assetClass` to determine required piping types
- EL.004 `electrical-connection-points`: uses `aif:core:assetClass` to determine required electrical connections

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
