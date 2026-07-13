# properties-sublayer-required

| Code     | AM.001 |
|----------|--------|
| Validator| {oav-validator-latest-link}`am-001` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

The USD stage must include a sublayer with "properties" in its filename (e.g., `AssetName_Properties.usda`) and that sublayer must specify a `defaultPrim`.

## Description

AIF equipment assets store all metadata attributes in a dedicated properties sublayer, separate from the geometry. This sublayer is the single source of truth for all `aif:core:*` and `aif:spec:*` attributes on the asset.

## Why is it required?

- Separates metadata from geometry, enabling independent authoring and version control
- Allows tooling to update metadata without touching geometry files
- Provides a predictable location for all AIF attribute data

## Examples

```text
# Valid: root layer includes a properties sublayer
subLayers = [
    @./CW375_Properties.usda@,
    @./CW375_Geometry.usda@
]
```

## How to comply

1. Create a `<AssetName>_Properties.usda` file with AIF metadata attributes on the root prim
2. Add it as a sublayer in your main USD stage file
3. Ensure the properties layer specifies a `defaultPrim`

## Related requirements

- AM.002 `asset-class-required`: reads from the same properties sublayer
- AM.003 `asset-identification-metadata`: reads from the same properties sublayer
- AM.007 `equipment-class-template-compliance`: reads from the same properties sublayer

## For More Information

- [USD Sublayers](https://openusd.org/release/glossary.html#usdglossary-sublayers)
