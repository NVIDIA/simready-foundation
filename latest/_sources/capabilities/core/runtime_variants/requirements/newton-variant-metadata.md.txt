# newton-variant-metadata

| Code     | RV.006 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The `Newton` variant set must be documented in `customLayerData.SimReady_Metadata.Variants.Physics.Newton`, declaring its `prim`, `variantSetName`, and `activateOption`.

## Description

When an asset authors the `Newton` variant set (see [newton-variant-set](newton-variant-set) `RV.004`), the root layer must carry a matching descriptor so tooling can discover and activate the variant without traversing composition. The descriptor lives at:

`customLayerData` → `SimReady_Metadata` → `Variants` → `Physics` → `Newton`

The `Newton` entry is a dictionary with:

- `prim` (string): the prim path that owns the variant set (the asset root, e.g. `/RootNode`).
- `variantSetName` (string): the variant set name, `Newton`.
- `activateOption` (string): the option that turns Newton on, i.e. `Enabled`.

The `variantSetName` must name a variant set that actually exists on the referenced `prim`.

## Why is it required?

- Lets pipelines enumerate and activate Newton from metadata alone, without opening and traversing variants.
- Keeps the declared runtime contract (metadata) and the composed structure (variant set) in sync and cross-checkable.
- Provides a stable, machine-readable description of which prim and option activate Newton.

## Examples

```usd
# Valid: metadata documents the Newton variant set
customLayerData = {
    dictionary SimReady_Metadata = {
        dictionary Variants = {
            dictionary Physics = {
                dictionary Newton = {
                    string prim = "/RootNode"
                    string variantSetName = "Newton"
                    string activateOption = "Enabled"
                }
            }
        }
    }
}

# Invalid: Newton variant set authored but no Newton metadata entry
                dictionary Physics = {
                }

# Invalid: entry missing required keys
                dictionary Newton = {
                    string prim = "/RootNode"
                }
```

## How to comply

- Add a `Variants` dictionary under `SimReady_Metadata` in the root layer's `customLayerData`.
- Under `Variants.Physics`, add a `Newton` dictionary.
- Set `prim` to the default prim path, `variantSetName` to `Newton`, and `activateOption` to `Enabled`.
- Ensure the `variantSetName`/`prim` pair points at a real variant set.

## Related Requirements

- [newton-variant-set](newton-variant-set) (RV.004)
- [metadata-whitelist](../../sim_ready/requirements/metadata-whitelist.md) (SR.001)

## For More Information

- [USD Metadata and Custom Data](https://openusd.org/release/api/class_sdf_layer.html)
