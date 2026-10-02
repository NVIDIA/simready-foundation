# mujoco-runtime-payload

| Code     | RV.008 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The `MuJoCo` variant set's `Enabled` option must compose its runtime layer with an anchored `prepend payload` that resolves to `./runnables/physics/mujoco.usd(a)`.

## Description

When the `MuJoCo` variant set (see [mujoco-variant-set](mujoco-variant-set) `RV.007`) selects its `Enabled` option, that option must bring in the MuJoCo-specific data through a USD `payload` arc, and the payload must:

- Use an anchored relative asset path (beginning with `./` or `../`) that stays within the asset root, consistent with [anchored-asset-paths](../../atomic_asset/requirements/anchored-asset-paths.md) (AA.001).
- Resolve to a file inside the asset's `runnables/physics/` directory.
- Use `mujoco` as the payload file stem: `mujoco.usd` or `mujoco.usda`.

The `.usd` and `.usda` file formats are interchangeable; either extension is acceptable. Only the `Enabled` variant composes the MuJoCo payload; the `Disabled` variant must not compose a MuJoCo payload layer.

## Why is it required?

- Guarantees a predictable, discoverable location for the MuJoCo payload.
- Keeps the MuJoCo layer separated from the neutral asset and from other runtimes, one file per runtime.
- Preserves portability by requiring anchored paths that resolve within the asset root.
- Aligns the on-disk layout with the variant contract so `Enabled` reliably means "MuJoCo payload composed."

## Examples

```usd
# Valid: Enabled variant prepends an anchored payload under runnables/physics/
    variantSet "MuJoCo" = {
        "Disabled" {
        }
        "Enabled" (
            prepend payload = @../runnables/physics/mujoco.usd@
        ) {
        }
    }

# Invalid: payload not under runnables/physics/
    variantSet "MuJoCo" = {
        "Enabled" (
            prepend payload = @../payloads/mujoco.usd@
        ) {
        }
    }

# Invalid: wrong file stem
    variantSet "MuJoCo" = {
        "Enabled" (
            prepend payload = @../runnables/physics/mjc.usd@
        ) {
        }
    }
```

## How to comply

- Author the MuJoCo payload from within the `Enabled` variant of the `MuJoCo` variant set.
- Store the MuJoCo layer at `runnables/physics/mujoco.usd` (or `.usda`) relative to the asset root.
- Use an anchored relative path (`./` or `../`) for the payload.
- Do not compose a MuJoCo payload from the `Disabled` variant.

## Related Requirements

- [mujoco-variant-set](mujoco-variant-set) (RV.007)
- [anchored-asset-paths](../../atomic_asset/requirements/anchored-asset-paths.md) (AA.001)
- [asset-folder-structure](../../naming_paths/requirements/asset-folder-structure.md) (NP.005)

## For More Information

- [USD References and Payloads](https://openusd.org/dev/api/usd_page_front.html#usd_references_and_payloads)
