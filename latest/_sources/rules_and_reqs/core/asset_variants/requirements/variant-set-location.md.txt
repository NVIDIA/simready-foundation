# Variant set location and default

| Code | AV.002 |
|---|---|
| Validator | VariationVariantSetChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` {tag}`composition` |

## Summary

A variation variant set MUST live on the asset's default (root) prim, declare at
least two options, and author a valid default selection that names one of those
options.

## Description

The asset MUST have a valid `defaultPrim`. Every variation variant set — the
master set `<Category>` and each per-part set `<Category>_<part>` — MUST be
authored on that default prim, not on an interior prim. This mirrors the
physics-runtime convention where `runtime_variants` sets live on the default
prim.

Each set MUST declare two or more options (a single-option scope carries no
variant set; see `AV.008`). The root layer MUST author a default variant
selection that names one of the set's declared options, and that selection MUST
equal the `default` recorded in the discovery metadata (`AV.001`).

A per-part set switches exactly one part; the master set switches all parts of
the category at once by authoring child selections only (`AV.004`). When a
same-category master set is present and authors its own default, a per-part set
MAY omit its root default selection: the master's default drives the per-part
selection, so the asset still composes to a known default state. The per-part
set still records its resulting default option in the `AV.001` metadata, and a
consumer overrides a single part by authoring a stronger per-part selection,
which wins over the master's child selection. For the master's child selections
to take effect, the master set MUST be ordered before the per-part-bearing sets
in the prim's `variantSets` (earlier variant sets compose stronger). The
validator enforces this: when a per-part set omits its root default and relies
on a master, it composes each master option and fails the requirement if the
per-part selection does not change across them, catching a weaker-ordered,
inert master.

## Why

Placing every variation switch on the root prim gives a consumer a single prim
to inspect and drive, and a valid authored default guarantees the asset composes
to a known, complete state when no selection is made.

## Examples

Valid:

```usd
#usda 1.0
(
    defaultPrim = "RootNode"
)
def Xform "RootNode" (
    variants = {
        string Representation = "Mesh"
    }
    prepend variantSets = ["Representation"]
)
{
    variantSet "Representation" = {
        "Mesh" { }
        "GaussianSplat" { }
    }
}
```

Invalid: a variation set authored on an interior prim rather than the default
prim; a set with only one option; a missing or out-of-range default selection.

## How to comply

Author the variant set on the default prim, give it at least two options, and set
the default selection on the root layer to one of them. Keep the default in sync
with `AV.001` metadata.

## Related requirements and references

`AV.001` owns the discovery metadata; `AV.004` owns master/per-part composition
and section purity; `AV.008` owns the two-option threshold. `VG.025` owns
root/origin conventions and `HI.001` the single default prim.
