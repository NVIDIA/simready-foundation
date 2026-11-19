# asset-description-required

| Code     | AM.006 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-006` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

The default prim must have `aif:core:assetDescription` and `aif:core:connectsToModelDocumentation` attributes.

## Description

Human-readable description and a link to external documentation ensure that asset consumers, both human and automated, can understand what the asset represents and find authoritative reference material.

## Why is it required?

- `assetDescription` provides a plain-language summary for asset library UIs and search
- `connectsToModelDocumentation` links to the manufacturer's product page or datasheet for authoritative specifications
- Together they make the digital twin self-documenting

## Examples

```usda
def Xform "Generic_CRAH" {
    string aif:core:assetDescription = "Generic chilled-water Computer Room Air Handler (CRAH), 105 kW nominal cooling capacity"
    string aif:core:connectsToModelDocumentation = "https://example.com/generic-crah/datasheet"
}
```

## How to comply

Set both attributes on the default prim. The documentation URL should point to the manufacturer's product page or technical datasheet.

## Related requirements

- AM.001 `properties-sublayer-required`: the properties sublayer must exist before these attributes can be set
- AM.003 `asset-identification-metadata`: complements identification attributes with a human-readable description

## For More Information

- [USD Custom Attributes](https://openusd.org/release/glossary.html#usdglossary-attribute)
