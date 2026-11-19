# default-prim

| Code     | TMP.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The stage must declare a valid `defaultPrim` so consumers can resolve the asset
root.

## Description

Template smoke validation requires a stage-level `defaultPrim`. Without it,
downstream tooling cannot reliably identify the asset root for composition,
physics, and packaging follow-up checks.

## Why is it required?

- Gives consumers a stable asset root to open and compose
- Provides a minimal executable gate for an additive tier example
- Avoids silent failures when later features assume a default prim

## Examples

```usd
# Invalid: no defaultPrim
def Xform "MyAsset" {
}

# Valid: defaultPrim points at the asset root
#usda 1.0
(
    defaultPrim = "MyAsset"
)

def Xform "MyAsset" {
}
```

## How to comply

- Author `defaultPrim` on the stage root layer
- Point `defaultPrim` at the intended asset root Xform (or equivalent root prim)
