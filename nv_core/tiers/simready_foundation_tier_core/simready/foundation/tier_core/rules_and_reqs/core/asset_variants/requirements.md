# Asset Variants Requirements

Discovery metadata lives under
`customLayerData.SimReady_Metadata.Variants.<Category>.<VariantSetName>`, mirroring
the `Variants.Physics` shape used by `runtime_variants`. Each entry carries
`prim`, `variantSetName`, `category`, `default`, and `impactClass`. The variant
sets themselves are native USD variant sets on the asset's default prim.

```{requirements-table}
```

```{toctree}
:maxdepth: 1
:hidden:

requirements/variation-discovery-metadata
requirements/variant-set-location
requirements/option-composability
requirements/section-purity-isolation
requirements/visual-envelope-invariant
requirements/collision-envelope-invariant
requirements/impact-class-honesty
requirements/conditional-presence
requirements/authored-physical-properties
requirements/variation-stability
```
