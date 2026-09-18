# newton-variant-set

| Code     | RV.004 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The asset's default prim must expose a `Newton` physics runtime variant set with `Disabled` and `Enabled` options, defaulting to `Disabled`.

## Description

An asset that supports the Newton runtime must declare it on the asset root (the stage `defaultPrim`) using a USD variant set named exactly `Newton`. The default prim must:

- Declare a variant set named `Newton`.
- Provide at least the options `Disabled` and `Enabled` in that variant set.
- Select `Disabled` as the authored default.

The `Disabled` option represents the neutral/base asset (no Newton payload composed). The `Enabled` option composes the Newton payload layer (see [newton-runtime-payload](newton-runtime-payload) `RV.005`). Defaulting to `Disabled` keeps the neutral asset the out-of-the-box state, so a consumer opts into Newton explicitly rather than inheriting Newton schemas by accident.

This requirement covers only the Newton variant set. PhysX and MuJoCo runtime variant sets are covered by their own requirements and features.

## Why is it required?

- Lets a single asset serve both neutral and Newton consumers without duplicating the asset.
- Keeps Newton-specific schemas and attributes out of the base asset so the neutral form stays portable.
- Makes Newton selection explicit and discoverable through a standard USD variant set.
- Establishes a predictable variant-set name (`Newton`) that validators and runtimes can rely on.

## Examples

```usd
# Valid: default prim declares a Newton variant set defaulting to Disabled
def Xform "RootNode" (
    kind = "component"
    prepend variantSets = ["Newton"]
    variants = {
        string Newton = "Disabled"
    }
)
{
    variantSet "Newton" = {
        "Disabled" {
        }
        "Enabled" (
            prepend payload = @../runnables/physics/newton.usd@
        ) {
        }
    }
}

# Invalid: Newton variant set present but defaults to Enabled
def Xform "RootNode" (
    prepend variantSets = ["Newton"]
    variants = {
        string Newton = "Enabled"
    }
)
{
    # ...
}

# Invalid: missing the Enabled option
    variantSet "Newton" = {
        "Disabled" {
        }
    }
```

## How to comply

- On the stage `defaultPrim`, add a variant set named exactly `Newton`.
- Give it at least a `Disabled` and an `Enabled` variant.
- Author the default variant selection as `Disabled`.
- Compose the Newton payload from the `Enabled` variant (see `RV.005`), and leave `Disabled` free of runtime payloads.

## Related Requirements

- [newton-runtime-payload](newton-runtime-payload) (RV.005)
- [newton-variant-metadata](newton-variant-metadata) (RV.006)

## For More Information

- [USD VariantSets](https://openusd.org/release/glossary.html#usdglossary-variantset)
- [USD Variant Selection](https://openusd.org/release/glossary.html#usdglossary-variantselection)
