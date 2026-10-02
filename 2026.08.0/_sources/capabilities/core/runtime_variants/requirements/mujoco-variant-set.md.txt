# mujoco-variant-set

| Code     | RV.007 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The asset's default prim must expose a `MuJoCo` physics runtime variant set with `Disabled` and `Enabled` options, defaulting to `Disabled`.

## Description

An asset that supports the MuJoCo runtime must declare it on the asset root (the stage `defaultPrim`) using a USD variant set named exactly `MuJoCo`. The default prim must:

- Declare a variant set named `MuJoCo`.
- Provide at least the options `Disabled` and `Enabled` in that variant set.
- Select `Disabled` as the authored default.

The `Disabled` option represents the neutral/base asset (no MuJoCo payload composed). The `Enabled` option composes the MuJoCo payload layer (see [mujoco-runtime-payload](mujoco-runtime-payload) `RV.008`). Defaulting to `Disabled` keeps the neutral asset the out-of-the-box state, so a consumer opts into MuJoCo explicitly rather than inheriting MuJoCo schemas by accident.

This requirement covers only the MuJoCo variant set. PhysX and Newton runtime variant sets are covered by their own requirements and features.

## Why is it required?

- Lets a single asset serve both neutral and MuJoCo consumers without duplicating the asset.
- Keeps MuJoCo-specific schemas and attributes out of the base asset so the neutral form stays portable.
- Makes MuJoCo selection explicit and discoverable through a standard USD variant set.
- Establishes a predictable variant-set name (`MuJoCo`) that validators and runtimes can rely on.

## Examples

```usd
# Valid: default prim declares a MuJoCo variant set defaulting to Disabled
def Xform "RootNode" (
    kind = "component"
    prepend variantSets = ["MuJoCo"]
    variants = {
        string MuJoCo = "Disabled"
    }
)
{
    variantSet "MuJoCo" = {
        "Disabled" {
        }
        "Enabled" (
            prepend payload = @../runnables/physics/mujoco.usd@
        ) {
        }
    }
}

# Invalid: MuJoCo variant set present but defaults to Enabled
def Xform "RootNode" (
    prepend variantSets = ["MuJoCo"]
    variants = {
        string MuJoCo = "Enabled"
    }
)
{
    # ...
}

# Invalid: missing the Enabled option
    variantSet "MuJoCo" = {
        "Disabled" {
        }
    }
```

## How to comply

- On the stage `defaultPrim`, add a variant set named exactly `MuJoCo`.
- Give it at least a `Disabled` and an `Enabled` variant.
- Author the default variant selection as `Disabled`.
- Compose the MuJoCo payload from the `Enabled` variant (see `RV.008`), and leave `Disabled` free of runtime payloads.

## Related Requirements

- [mujoco-runtime-payload](mujoco-runtime-payload) (RV.008)
- [mujoco-variant-metadata](mujoco-variant-metadata) (RV.009)

## For More Information

- [USD VariantSets](https://openusd.org/release/glossary.html#usdglossary-variantset)
- [USD Variant Selection](https://openusd.org/release/glossary.html#usdglossary-variantselection)
