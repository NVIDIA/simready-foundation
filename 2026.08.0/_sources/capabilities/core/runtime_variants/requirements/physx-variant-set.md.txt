# physx-variant-set

| Code     | RV.001 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The asset's default prim must expose a `PhysX` physics runtime variant set with `Disabled` and `Enabled` options, defaulting to `Disabled`.

## Description

An asset that supports the PhysX runtime must declare it on the asset root (the stage `defaultPrim`) using a USD variant set named exactly `PhysX`. The default prim must:

- Declare a variant set named `PhysX`.
- Provide at least the options `Disabled` and `Enabled` in that variant set.
- Select `Disabled` as the authored default.

The `Disabled` option represents the neutral/base asset (no PhysX payload composed). The `Enabled` option composes the PhysX payload layer (see [physx-runtime-payload](physx-runtime-payload) `RV.002`). Defaulting to `Disabled` keeps the neutral asset the out-of-the-box state, so a consumer opts into PhysX explicitly rather than inheriting PhysX schemas by accident.

This requirement covers only the PhysX variant set. Newton and MuJoCo runtime variant sets are covered by their own requirements and features.

## Why is it required?

- Lets a single asset serve both neutral and PhysX consumers without duplicating the asset.
- Keeps PhysX-specific schemas and attributes out of the base asset so the neutral form stays portable.
- Makes PhysX selection explicit and discoverable through a standard USD variant set.
- Establishes a predictable variant-set name (`PhysX`) that validators and runtimes can rely on.

## Examples

```usd
# Valid: default prim declares a PhysX variant set defaulting to Disabled
def Xform "RootNode" (
    kind = "component"
    prepend variantSets = ["PhysX"]
    variants = {
        string PhysX = "Disabled"
    }
)
{
    variantSet "PhysX" = {
        "Disabled" {
        }
        "Enabled" (
            prepend payload = @../runnables/physics/physx.usd@
        ) {
        }
    }
}

# Invalid: PhysX variant set present but defaults to Enabled
def Xform "RootNode" (
    prepend variantSets = ["PhysX"]
    variants = {
        string PhysX = "Enabled"
    }
)
{
    # ...
}

# Invalid: missing the Enabled option
    variantSet "PhysX" = {
        "Disabled" {
        }
    }
```

## How to comply

- On the stage `defaultPrim`, add a variant set named exactly `PhysX`.
- Give it at least a `Disabled` and an `Enabled` variant.
- Author the default variant selection as `Disabled`.
- Compose the PhysX payload from the `Enabled` variant (see `RV.002`), and leave `Disabled` free of runtime payloads.

## Related Requirements

- [physx-runtime-payload](physx-runtime-payload) (RV.002)
- [physx-variant-metadata](physx-variant-metadata) (RV.003)

## For More Information

- [USD VariantSets](https://openusd.org/release/glossary.html#usdglossary-variantset)
- [USD Variant Selection](https://openusd.org/release/glossary.html#usdglossary-variantselection)
