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
def Xform "Generic_CDU" {
    string aif:core:assetClass = "CDU"
}
```

The value names an equipment class, not a product. A class is recognised when a
`config/aif-equipment-<class>.json` file declares a token matching it, so the set of
valid values grows with that directory rather than with this document. The classes
defined today are `CDU`, `CRAH`, `UPS` and `compute rack`.

Matching is case-insensitive and ignores surrounding whitespace, and a token may contain
spaces. Every token a class accepts is listed in its `assetClassTokens`.

The compute rack class also accepts `gb300`, `gb300 rack` and `gb300_rack`, which v0.1.0
published as valid values. They name a product rather than an equipment class and are kept
so assets authored against the published specification keep validating; a class file
repeats them under `legacyAssetClassTokens` to record why they are there. Author new assets
with the class name.

## How to comply

Set `aif:core:assetClass` on the default prim of the `*Properties.usda` sublayer to the appropriate equipment class string.

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before this attribute can be set
- AM.007 `equipment-class-template-compliance`: uses `aif:core:assetClass` to select the equipment schema
- TC.002 `thermal-cooling-connection-points`: uses `aif:core:assetClass` to determine required piping types
- EL.004 `electrical-connection-points`: uses `aif:core:assetClass` to determine required electrical connections

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
