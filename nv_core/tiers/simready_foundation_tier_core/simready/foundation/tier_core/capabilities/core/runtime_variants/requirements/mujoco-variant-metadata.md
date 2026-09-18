# mujoco-variant-metadata

| Code     | RV.009 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The `MuJoCo` variant set must be documented in `customLayerData.SimReady_Metadata.Variants.Physics.MuJoCo`, declaring its `prim`, `variantSetName`, and `activateOption`.

## Description

When an asset authors the `MuJoCo` variant set (see [mujoco-variant-set](mujoco-variant-set) `RV.007`), the root layer must carry a matching descriptor so tooling can discover and activate the variant without traversing composition. The descriptor lives at:

`customLayerData` → `SimReady_Metadata` → `Variants` → `Physics` → `MuJoCo`

The `MuJoCo` entry is a dictionary with:

- `prim` (string): the prim path that owns the variant set (the asset root, e.g. `/RootNode`).
- `variantSetName` (string): the variant set name, `MuJoCo`.
- `activateOption` (string): the option that turns MuJoCo on, i.e. `Enabled`.

The `variantSetName` must name a variant set that actually exists on the referenced `prim`.

## Why is it required?

- Lets pipelines enumerate and activate MuJoCo from metadata alone, without opening and traversing variants.
- Keeps the declared runtime contract (metadata) and the composed structure (variant set) in sync and cross-checkable.
- Provides a stable, machine-readable description of which prim and option activate MuJoCo.

## Examples

```usd
# Valid: metadata documents the MuJoCo variant set
customLayerData = {
    dictionary SimReady_Metadata = {
        dictionary Variants = {
            dictionary Physics = {
                dictionary MuJoCo = {
                    string prim = "/RootNode"
                    string variantSetName = "MuJoCo"
                    string activateOption = "Enabled"
                }
            }
        }
    }
}

# Invalid: MuJoCo variant set authored but no MuJoCo metadata entry
                dictionary Physics = {
                }

# Invalid: entry missing required keys
                dictionary MuJoCo = {
                    string prim = "/RootNode"
                }
```

## How to comply

- Add a `Variants` dictionary under `SimReady_Metadata` in the root layer's `customLayerData`.
- Under `Variants.Physics`, add a `MuJoCo` dictionary.
- Set `prim` to the default prim path, `variantSetName` to `MuJoCo`, and `activateOption` to `Enabled`.
- Ensure the `variantSetName`/`prim` pair points at a real variant set.

## Related Requirements

- [mujoco-variant-set](mujoco-variant-set) (RV.007)
- [metadata-whitelist](../../sim_ready/requirements/metadata-whitelist.md) (SR.001)

## For More Information

- [USD Metadata and Custom Data](https://openusd.org/release/api/class_sdf_layer.html)
