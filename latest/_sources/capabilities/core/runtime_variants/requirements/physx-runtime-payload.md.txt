# physx-runtime-payload

| Code     | RV.002 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The `PhysX` variant set's `Enabled` option must compose its runtime layer with an anchored `prepend payload` that resolves to `./runnables/physics/physx.usd(a)`.

## Description

When the `PhysX` variant set (see [physx-variant-set](physx-variant-set) `RV.001`) selects its `Enabled` option, that option must bring in the PhysX-specific data through a USD `payload` arc, and the payload must:

- Use an anchored relative asset path (beginning with `./` or `../`) that stays within the asset root, consistent with [anchored-asset-paths](../../atomic_asset/requirements/anchored-asset-paths.md) (AA.001).
- Resolve to a file inside the asset's `runnables/physics/` directory.
- Use `physx` as the payload file stem: `physx.usd` or `physx.usda`.

The `.usd` and `.usda` file formats are interchangeable; either extension is acceptable. Only the `Enabled` variant composes the PhysX payload; the `Disabled` variant must not compose a PhysX payload layer.

## Why is it required?

- Guarantees a predictable, discoverable location for the PhysX payload.
- Keeps the PhysX layer separated from the neutral asset and from other runtimes, one file per runtime.
- Preserves portability by requiring anchored paths that resolve within the asset root.
- Aligns the on-disk layout with the variant contract so `Enabled` reliably means "PhysX payload composed."

## Examples

```usd
# Valid: Enabled variant prepends an anchored payload under runnables/physics/
    variantSet "PhysX" = {
        "Disabled" {
        }
        "Enabled" (
            prepend payload = @../runnables/physics/physx.usd@
        ) {
        }
    }

# Invalid: payload not under runnables/physics/
    variantSet "PhysX" = {
        "Enabled" (
            prepend payload = @../payloads/physx.usd@
        ) {
        }
    }

# Invalid: wrong file stem
    variantSet "PhysX" = {
        "Enabled" (
            prepend payload = @../runnables/physics/rigidbody.usd@
        ) {
        }
    }
```

## How to comply

- Author the PhysX payload from within the `Enabled` variant of the `PhysX` variant set.
- Store the PhysX layer at `runnables/physics/physx.usd` (or `.usda`) relative to the asset root.
- Use an anchored relative path (`./` or `../`) for the payload.
- Do not compose a PhysX payload from the `Disabled` variant.

## Related Requirements

- [physx-variant-set](physx-variant-set) (RV.001)
- [anchored-asset-paths](../../atomic_asset/requirements/anchored-asset-paths.md) (AA.001)
- [asset-folder-structure](../../naming_paths/requirements/asset-folder-structure.md) (NP.005)

## For More Information

- [USD References and Payloads](https://openusd.org/dev/api/usd_page_front.html#usd_references_and_payloads)
