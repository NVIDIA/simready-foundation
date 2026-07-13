# connection-points-composition

| Code     | CP.005 |
|----------|--------|
| Validator| {oav-validator-latest-link}`cp-005` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`essential` |

## Summary

Connection points must be saved as a separate `<AssetName>_ConnectionPoints.usd` file and composed into the main stage as a sublayer.

## Description

Separating connection point geometry into its own USD file allows the connection points to be versioned, updated, and replaced independently from the main geometry. The file is then composed into the main asset as a sublayer, making the connection points part of the final composed stage.

## Why is it required?

- Enables independent authoring and versioning of connection point geometry
- Allows tooling to extract, update, or replace connection points without touching geometry
- The `*_ConnectionPoints.usd` naming convention makes the sublayer identifiable by validators

## Examples

```usda
subLayers = [
    @./CW375_ConnectionPoints.usd@,
    @./CW375_Properties.usda@,
    @./CW375_Geometry.usd@
]
```

## How to comply

1. Author connection point geometry in a separate scene
2. Save as `<AssetName>_ConnectionPoints.usd` (e.g., `CW375_ConnectionPoints.usd`)
3. In your main asset file, add it as a sublayer in the order shown above

## Related requirements

- CP.001 `connectionpoints-scope-structure`: the `ConnectionPoints` scope must exist inside this sublayer
- CP.004 `connection-point-naming-convention`: prims inside the sublayer must follow the naming convention
- AM.001 `properties-sublayer-required`: the `*Properties.usda` sublayer follows the same composition pattern

## For More Information

- [USD Sublayers](https://openusd.org/release/glossary.html#usdglossary-sublayers)
