# newton-runtime-payload

| Code     | RV.005 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The `Newton` variant set's `Enabled` option must compose its runtime layer with an anchored `prepend payload` that resolves to `./runnables/physics/newton.usd(a)`.

## Description

When the `Newton` variant set (see [newton-variant-set](newton-variant-set) `RV.004`) selects its `Enabled` option, that option must bring in the Newton-specific data through a USD `payload` arc, and the payload must:

- Use an anchored relative asset path (beginning with `./` or `../`) that stays within the asset root, consistent with [anchored-asset-paths](../../atomic_asset/requirements/anchored-asset-paths.md) (AA.001).
- Resolve to a file inside the asset's `runnables/physics/` directory.
- Use `newton` as the payload file stem: `newton.usd` or `newton.usda`.

The `.usd` and `.usda` file formats are interchangeable; either extension is acceptable. Only the `Enabled` variant composes the Newton payload; the `Disabled` variant must not compose a Newton payload layer.

## Why is it required?

- Guarantees a predictable, discoverable location for the Newton payload.
- Keeps the Newton layer separated from the neutral asset and from other runtimes, one file per runtime.
- Preserves portability by requiring anchored paths that resolve within the asset root.
- Aligns the on-disk layout with the variant contract so `Enabled` reliably means "Newton payload composed."

## Examples

```usd
# Valid: Enabled variant prepends an anchored payload under runnables/physics/
    variantSet "Newton" = {
        "Disabled" {
        }
        "Enabled" (
            prepend payload = @../runnables/physics/newton.usd@
        ) {
        }
    }

# Invalid: payload not under runnables/physics/
    variantSet "Newton" = {
        "Enabled" (
            prepend payload = @../payloads/newton.usd@
        ) {
        }
    }

# Invalid: wrong file stem
    variantSet "Newton" = {
        "Enabled" (
            prepend payload = @../runnables/physics/mjc.usd@
        ) {
        }
    }
```

## How to comply

- Author the Newton payload from within the `Enabled` variant of the `Newton` variant set.
- Store the Newton layer at `runnables/physics/newton.usd` (or `.usda`) relative to the asset root.
- Use an anchored relative path (`./` or `../`) for the payload.
- Do not compose a Newton payload from the `Disabled` variant.

## Related Requirements

- [newton-variant-set](newton-variant-set) (RV.004)
- [anchored-asset-paths](../../atomic_asset/requirements/anchored-asset-paths.md) (AA.001)
- [asset-folder-structure](../../naming_paths/requirements/asset-folder-structure.md) (NP.005)

## For More Information

- [USD References and Payloads](https://openusd.org/dev/api/usd_page_front.html#usd_references_and_payloads)
