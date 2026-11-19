# Variation discovery metadata

| Code | AV.001 |
|---|---|
| Validator | VariationDiscoveryMetadataChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`metadata` |

## Summary

Every advertised variation variant set MUST be declared under
`customLayerData.SimReady_Metadata.Variants.<Category>.<VariantSetName>` with its
owning prim, category, default option, and impact class.

## Description

Author the entry on the root layer's `customLayerData`:

```text
SimReady_Metadata
  Variants
    <Category>
      <VariantSetName>
        prim           = "/<DefaultPrimPath>"   # prim that owns the variant set
        variantSetName = "<VariantSetName>"      # equals the dictionary key
        category       = "<Category>"            # equals the parent key
        default        = "<OptionName>"          # one of the set's options
        impactClass    = "visual-only" | "simulation-affecting"
```

The `prim` MUST resolve to a valid prim that actually owns a variant set named
`variantSetName`. `category` MUST equal the parent category key and MUST NOT be
the reserved `Physics` category, which `runtime_variants` owns. `default` MUST
name an option that the variant set declares and MUST equal the authored default
selection (`AV.002`). `impactClass` MUST be one of the two class tokens and MUST
tell the truth about what the options change (`AV.007`).

Both the master set (`<Category>`) and every per-part set (`<Category>_<part>`)
that an asset exposes MUST have their own entry. A variant set that is authored
on the prim but absent from the metadata, or a metadata entry with no matching
variant set, fails.

## Why

A consumer discovers an asset's variations by reading one well-known metadata
block instead of walking every prim for variant sets. The impact class lets a
scenario loader decide whether re-selecting an option is a pure visual swap or a
change that touches simulation.

## Examples

Valid:

```usd
#usda 1.0
(
    defaultPrim = "RootNode"
    customLayerData = {
        dictionary SimReady_Metadata = {
            dictionary Variants = {
                dictionary Representation = {
                    dictionary Representation = {
                        string prim = "/RootNode"
                        string variantSetName = "Representation"
                        string category = "Representation"
                        string default = "Mesh"
                        string impactClass = "visual-only"
                    }
                }
            }
        }
    }
)
```

Invalid: an entry under `Variants.Physics` (reserved), a `prim` that does not own
the named set, a `default` that is not one of the set's options, or an
`impactClass` outside `{visual-only, simulation-affecting}`.

## How to comply

Author one metadata entry per variation variant set as you author the set itself.
Keep `variantSetName`, `category`, and `default` in agreement with the USD
variant set and its authored default selection.

## Related requirements and references

`AV.002` owns variant-set location and the authored default; `AV.007` owns impact
class honesty; `AV.008` owns conditional presence. `RV.003`/`RV.006`/`RV.009`
own the parallel `Variants.Physics` metadata for physics runtimes.
