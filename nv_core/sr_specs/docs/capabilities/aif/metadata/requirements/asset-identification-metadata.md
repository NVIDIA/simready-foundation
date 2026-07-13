# asset-identification-metadata

| Code     | AM.003 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-003` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

The default prim must have `aif:core:manufacturer`, `aif:core:modelNumber`, and `aif:core:assetVersion` attributes.

## Description

These three attributes uniquely identify the specific physical product that the digital twin represents. Together they form the provenance of the asset: who made it, which product it is, and which revision of the digital twin this is.

## Why is it required?

- `manufacturer` and `modelNumber` together identify the real-world equipment product
- `assetVersion` tracks the revision of the digital twin itself (separate from product version)
- Required for asset library management and downstream tooling lookups

## Examples

```usda
def Xform "CW375" {
    string aif:core:manufacturer = "Vertiv"
    string aif:core:modelNumber = "CW375KW"
    string aif:core:assetVersion = "1.0.0"
}
```

## How to comply

Set all three attributes on the default prim of the `*Properties.usda` sublayer with the manufacturer name, model number, and semantic version string of the digital twin.

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before these attributes can be set
- AM.002 `asset-class-required`: required alongside identification attributes to fully describe the asset
- AM.006 `asset-description-required`: complements identification with a human-readable description

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
